# -*- coding: utf-8 -*-
from gcloud import storage as gs
from zope.schema import Object
from pserver.gcloudstorage.interfaces import IGCloudFile
from pserver.gcloudstorage.interfaces import IGCloudFileField
from oauth2client.service_account import ServiceAccountCredentials
from zope.interface import implementer
from zope.component import getUtility
from persistent import Persistent
from zope.schema.fieldproperty import FieldProperty
from googleapiclient import http
from googleapiclient import errors
from zope.component import adapter
from plone.dexterity.interfaces import IDexterityContent
from plone.server.interfaces import IRequest
from plone.server.interfaces import IFileManager
from pserver.gcloudstorage.interfaces import IGCloudBlobStore
from pserver.gcloudstorage.events import InitialGCloudUpload
from pserver.gcloudstorage.events import FinishGCloudUpload
from plone.jsonserializer.interfaces import IJsonCompatible
from googleapiclient import discovery
from plone.server.transactions import get_current_request
from aiohttp.web import StreamResponse
from zope.event import notify
import mimetypes
import os
import gcloud
import logging
import uuid
import aiohttp
import asyncio
import json
from io import BytesIO

try:
    from oauth2client import util
except ImportError:
    from oauth2client import _helpers as util

log = logging.getLogger(__name__)

MAX_SIZE = 1073741824

SCOPES = ['https://www.googleapis.com/auth/devstorage.read_write']
UPLOAD_URL = 'https://www.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=resumable'
CHUNK_SIZE = 524288
MAX_RETRIES = 5


@adapter(IGCloudFile)
@implementer(IJsonCompatible)
def json_converter(value):
    if value is None:
        return value

    return {
        'filename': value.filename,
        'contenttype': value.contentType,
        'size': value.size
    }


@adapter(IDexterityContent, IRequest, IGCloudFileField)
@implementer(IFileManager)
class GCloudFileManager(object):

    def __init__(self, context, request, field):
        self.context = context
        self.request = request
        self.field = field

    async def upload(self):
        """ In order to support TUS and IO upload
        we need to provide an upload that concats the incoming
        """
        file = self.field.get(self.context)
        if file is None:
            file = GCloudFile(contentType=self.request.content_type)
            self.field.set(self.context, file)
        file._md5hash = self.request.headers['X-UPLOAD-MD5HASH']
        file._size = self.request.headers['X-UPLOAD-SIZE']
        file.filename = self.request.headers['X-UPLOAD-FILENAME']
        await file.initUpload(self.context)
        try:
            data = await self.request.content.readexactly(CHUNK_SIZE)
        except asyncio.IncompleteReadError as e:
            data = e.partial
        # while len(data) < CHUNK_SIZE:
        #     if self.request.content.is_eof():
        #         break
        #     data += await self.request.content.read(CHUNK_SIZE)
        count = 0
        while data:
            old_current_upload = file._current_upload
            resp = await file.appendData(data)
            readed_bytes = file._current_upload - old_current_upload

            data = data[readed_bytes:]

            bytes_to_read = readed_bytes

            if resp.status in [200, 201]:
                break
            if resp.status == 308:
                count = 0
                try:
                    data += await self.request.content.readexactly(bytes_to_read)
                except asyncio.IncompleteReadError as e:
                    data += e.partial
                # data = await self.request.content.read(CHUNK_SIZE)
                # while len(data) < CHUNK_SIZE + 1:
                #     if self.request.content.is_eof():
                #         break
                #     data += await self.request.content.read(CHUNK_SIZE)
            else:
                count += 1
                if count > MAX_RETRIES:
                    raise AttributeError('MAX retries error')
        # Test resp and checksum to finish upload
        await file.finishUpload(self.context)

    async def tus_post(self):
        """ FROM POST
        """
        pass

    async def tus_patch(self):
        """ FROM POST
        """
        pass

    async def tus_head(self):
        """ FROM POST
        """
        pass

    async def tus_options(self):
        """ FROM OPTIONS
        """
        pass

    async def download(self):
        file = self.field.get(self.context)
        if file is None:
            raise AttributeError('No field value')

        resp = StreamResponse(headers=aiohttp.MultiDict({
            'CONTENT-DISPOSITION': 'attachment; filename="%s"' % file.filename
        }))
        resp.content_type = file.contentType
        resp.content_length = file._size
        buf = BytesIO()
        downloader = await file.download(buf)
        await resp.prepare(self.request)
        # response.start(request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            print("Download {}%.".format(int(status.progress() * 100)))
            buf.seek(0)
            data = buf.read()
            resp.write(data)
            await resp.drain()
            buf.seek(0)
            buf.truncate()

        return resp


@implementer(IGCloudFile)
class GCloudFile(Persistent):
    """A file stored in a GCloud, with a filename"""

    filename = FieldProperty(IGCloudFile['filename'])

    def __init__(self, contentType='application/octet-stream',
                 filename=None):
        if (
            filename is not None and
            contentType in ('', 'application/octet-stream')
        ):
            contentType = get_contenttype(filename=filename)
        self.contentType = contentType

        if filename is not None:
            self.filename = filename

    async def initUpload(self, context):
        """
            self._uload_file_id : temporal url to image beeing uploaded
            self._resumable_uri : uri to resumable upload
            self._uri : finished uploaded image
        """

        util = getUtility(IGCloudBlobStore)
        request = get_current_request()
        if hasattr(self, '_upload_file_id') and self._upload_file_id is not None:
            req = util._service.objects().delete(
                bucket=util._bucket, object=self._upload_file_id)
            try:
                req.execute()
            except errors.HttpError:
                pass

        self._upload_file_id = request._site_id + '/' + uuid.uuid4().hex
        init_url = UPLOAD_URL.format(bucket=util._bucket) + '&name=' +\
            self._upload_file_id
        session = aiohttp.ClientSession()

        creator = ','.join([x.principal.id for x
                            in request.security.participations])
        metadata = json.dumps({
            'CREATOR': creator,
            'REQUEST': str(request),
            'NAME': self.filename
        })
        call_size = len(metadata)
        async with session.post(
                init_url,
                headers={
                    'AUTHORIZATION': 'Bearer %s' % util.access_token,
                    'X-Upload-Content-Type': self.contentType,
                    'X-Upload-Content-Length': self._size,
                    'Content-Type': 'application/json; charset=UTF-8',
                    'Content-Length': str(call_size)
                },
                data=metadata) as call:
            assert call.status == 200
            self._resumable_uri = call.headers['Location']
        session.close()
        self._current_upload = 0
        notify(InitialGCloudUpload(context))

    async def appendData(self, data):
        session = aiohttp.ClientSession()

        content_range = 'bytes {init}-{chunk}/{total}'.format(
            init=self._current_upload,
            chunk=self._current_upload + len(data) - 1,
            total=self._size)
        async with session.put(
                self._resumable_uri,
                headers={
                    'Content-Length': str(len(data)),
                    'Content-Type': self.contentType,
                    'Content-Range': content_range
                },
                data=data) as call:
            text = await call.text()
            assert call.status in [200, 201, 308]
            if call.status == 308:
                self._current_upload = int(call.headers['Range'].split('-')[1])
        session.close()
        return call

    async def finishUpload(self, context):
        util = getUtility(IGCloudBlobStore)
        # It would be great to do on AfterCommit
        if hasattr(self, '_uri') and self._uri is not None:
            req = util._service.objects().delete(
                bucket=util._bucket, object=self._uri)
            try:
                resp = req.execute()
            except errors.HttpError:
                pass
        self._uri = self._upload_file_id
        self._upload_file_id = None
        notify(FinishGCloudUpload(context))

    async def deleteUpload(self):
        if hasattr(self, '_uri') and self._uri is not None:
            req = util._service.objects().delete(
                bucket=util._bucket, object=self._uri)
            resp = req.execute()
            return resp
        else:
            raise AttributeError('No valid uri')

    async def download(self, buf):
        util = getUtility(IGCloudBlobStore)
        req = util._service.objects().get_media(
            bucket=util._bucket, object=self._uri)
        downloader = http.MediaIoBaseDownload(buf, req, chunksize=CHUNK_SIZE)
        return downloader

    def _setData(self, data):
        raise NotImplemented('Only specific upload permitted')

    def _getData(self):
        raise NotImplemented('Only specific download permitted')

    data = property(_getData, _setData)

    @property
    def size(self):
        if hasattr(self, '_size'):
            return self._size
        else:
            return None

    def getSize(self):
        return self.size


@implementer(IGCloudFileField)
class GCloudFileField(Object):
    """A NamedBlobFile field
    """

    _type = GCloudFile
    schema = IGCloudFile

    def __init__(self, **kw):
        if 'schema' in kw:
            self.schema = kw.pop('schema')
        super(GCloudFileField, self).__init__(schema=self.schema, **kw)


# Configuration Utility

class GCloudBlobStore(object):

    def __init__(self, settings):
        self._json_credentials = settings['json_credentials']
        self._credentials = ServiceAccountCredentials.from_json_keyfile_name(
            self._json_credentials, SCOPES)
        self._service = discovery.build(
            'storage', 'v1', credentials=self._credentials)
        self._bucket = settings['bucket']
        self._access_token = self._credentials.get_access_token()

    @property
    def access_token(self):
        if self._access_token.expires_in < 1:
            self._access_token = self._credentials.get_access_token()
        return self._access_token.access_token

    async def initialize(self, app=None):
        # No asyncio loop to run
        self.app = app
