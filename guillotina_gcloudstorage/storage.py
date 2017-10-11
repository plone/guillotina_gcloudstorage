# -*- coding: utf-8 -*-
from aiohttp.web import StreamResponse
from aiohttp.web_exceptions import HTTPNotFound
from datetime import datetime
from datetime import timedelta
from dateutil.tz import tzlocal
from guillotina import app_settings
from guillotina import configure
from guillotina.browser import Response
from guillotina.component import getUtility
from guillotina.event import notify
from guillotina.files import BaseCloudFile
from guillotina.files import read_request_data
from guillotina.interfaces import IAbsoluteURL
from guillotina.interfaces import IApplication
from guillotina.interfaces import IFileManager
from guillotina.interfaces import IJSONToValue
from guillotina.interfaces import IRequest
from guillotina.interfaces import IResource
from guillotina.schema import Object
from guillotina.utils import get_current_request
from guillotina.utils import to_str
from guillotina_gcloudstorage.events import FinishGCloudUpload
from guillotina_gcloudstorage.events import InitialGCloudUpload
from guillotina_gcloudstorage.interfaces import IGCloudBlobStore
from guillotina_gcloudstorage.interfaces import IGCloudFile
from guillotina_gcloudstorage.interfaces import IGCloudFileField
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import quote_plus
from zope.interface import implementer

import aiohttp
import base64
import google.cloud.exceptions
import google.cloud.storage
import json
import logging
import uuid


log = logging.getLogger('guillotina_gcloudstorage')

MAX_SIZE = 1073741824

SCOPES = ['https://www.googleapis.com/auth/devstorage.read_write']
UPLOAD_URL = 'https://www.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=resumable'  # noqa
OBJECT_BASE_URL = 'https://www.googleapis.com/storage/v1/b'
CHUNK_SIZE = 524288
MAX_RETRIES = 5


class GoogleCloudException(Exception):
    pass


@configure.adapter(
    for_=(dict, IGCloudFileField),
    provides=IJSONToValue)
def dictfile_converter(value, field):
    return GCloudFile(**value)


@configure.adapter(
    for_=(IResource, IRequest, IGCloudFileField),
    provides=IFileManager)
class GCloudFileManager(object):

    def __init__(self, context, request, field):
        self.context = context
        self.request = request
        self.field = field

    async def upload(self):
        """In order to support TUS and IO upload.

        we need to provide an upload that concats the incoming
        """
        self.context._p_register()  # writing to object

        file = self.field.get(self.field.context or self.context)
        if not isinstance(file, GCloudFile):
            file = GCloudFile(content_type=self.request.content_type)
            self.field.set(self.field.context or self.context, file)
            # Its a long transaction, savepoint
            # trns = get_transaction(self.request)
            # XXX no savepoint support right now?
        if 'X-UPLOAD-MD5HASH' in self.request.headers:
            file._md5 = self.request.headers['X-UPLOAD-MD5HASH']
        else:
            file._md5 = None

        if 'X-UPLOAD-EXTENSION' in self.request.headers:
            file._extension = self.request.headers['X-UPLOAD-EXTENSION']
        else:
            file._extension = None

        if 'X-UPLOAD-SIZE' in self.request.headers:
            file._size = int(self.request.headers['X-UPLOAD-SIZE'])
        else:
            raise AttributeError('x-upload-size header needed')

        if 'X-UPLOAD-FILENAME' in self.request.headers:
            file.filename = self.request.headers['X-UPLOAD-FILENAME']
        elif 'X-UPLOAD-FILENAME-B64' in self.request.headers:
            file.filename = base64.b64decode(
                self.request.headers['X-UPLOAD-FILENAME-B64']).decode("utf-8")
        else:
            file.filename = uuid.uuid4().hex

        await file.init_upload(self.context)
        self.request._last_read_pos = 0
        data = await read_request_data(self.request, CHUNK_SIZE)

        count = 0
        while data:
            old_current_upload = file._current_upload
            resp = await file.append_data(data)
            readed_bytes = file._current_upload - old_current_upload

            data = data[readed_bytes:]

            bytes_to_read = readed_bytes

            if resp.status in [200, 201]:
                break
            if resp.status == 308:
                count = 0
                data = await read_request_data(self.request, bytes_to_read)

            else:
                count += 1
                if count > MAX_RETRIES:
                    raise AttributeError('MAX retries error')
        # Test resp and checksum to finish upload
        await file.finish_upload(self.context)

    async def tus_create(self):
        self.context._p_register()  # writing to object

        # This only happens in tus-java-client, redirect this POST to a PATCH
        if self.request.headers.get('X-HTTP-Method-Override') == 'PATCH':
            return await self.tus_patch()

        file = self.field.get(self.field.context or self.context)
        if not isinstance(file, GCloudFile):
            file = GCloudFile(content_type=self.request.content_type)
            self.field.set(self.field.context or self.context, file)
        if 'CONTENT-LENGTH' in self.request.headers:
            file._current_upload = int(self.request.headers['CONTENT-LENGTH'])
        else:
            file._current_upload = 0
        if 'UPLOAD-LENGTH' in self.request.headers:
            file._size = int(self.request.headers['UPLOAD-LENGTH'])
        else:
            raise AttributeError('We need upload-length header')

        if 'UPLOAD-MD5' in self.request.headers:
            file._md5 = self.request.headers['UPLOAD-MD5']

        if 'UPLOAD-EXTENSION' in self.request.headers:
            file._extension = self.request.headers['UPLOAD-EXTENSION']

        if 'TUS-RESUMABLE' not in self.request.headers:
            raise AttributeError('Its a TUS needs a TUS version')

        if 'UPLOAD-METADATA' not in self.request.headers:
            file.filename = uuid.uuid4().hex
        else:
            filename = self.request.headers['UPLOAD-METADATA']
            file.filename = base64.b64decode(filename.split()[1]).decode('utf-8')

        await file.init_upload(self.context)
        # Location will need to be adapted on aiohttp 1.1.x
        resp = Response(headers={
            'Location': IAbsoluteURL(self.context, self.request)() + '/@tusupload/' + self.field.__name__,  # noqa
            'Tus-Resumable': '1.0.0',
            'Access-Control-Expose-Headers': 'Location,Tus-Resumable'
        }, status=201)
        return resp

    async def tus_patch(self):
        self.context._p_register()  # writing to object
        file = self.field.get(self.field.context or self.context)
        if 'CONTENT-LENGTH' in self.request.headers:
            to_upload = int(self.request.headers['CONTENT-LENGTH'])
        else:
            raise AttributeError('No content-length header')

        if 'UPLOAD-OFFSET' in self.request.headers:
            file._current_upload = int(self.request.headers['UPLOAD-OFFSET'])
        else:
            raise AttributeError('No upload-offset header')

        self.request._last_read_pos = 0
        data = await read_request_data(self.request, to_upload)

        count = 0
        while data:
            old_current_upload = file._current_upload
            resp = await file.append_data(data)
            # The amount of bytes that are readed
            if resp.status in [200, 201]:
                # If we finish the current upload is the size of the file
                readed_bytes = file._current_upload - old_current_upload
            else:
                # When it comes from gcloud the current_upload is one number less
                readed_bytes = file._current_upload - old_current_upload + 1

            # Cut the data so there is only the needed data
            data = data[readed_bytes:]

            bytes_to_read = len(data)

            if resp.status in [200, 201]:
                # If we are finished lets close it
                await file.finish_upload(self.context)
                data = None

            if bytes_to_read == 0:
                # We could read all the info
                break

            if bytes_to_read < 262144:
                # There is no enough data to send to gcloud
                break

            if resp.status in [400]:
                # Some error
                break

            if resp.status == 308:
                # We continue resumable
                count = 0
                data = await read_request_data(self.request, bytes_to_read)

            else:
                count += 1
                if count > MAX_RETRIES:
                    raise AttributeError('MAX retries error')
        expiration = file._resumable_uri_date + timedelta(days=7)

        resp = Response(headers={
            'Upload-Offset': str(file.get_actual_size()),
            'Tus-Resumable': '1.0.0',
            'Upload-Expires': expiration.isoformat(),
            'Access-Control-Expose-Headers': 'Upload-Offset,Upload-Expires,Tus-Resumable'
        })
        return resp

    async def tus_head(self):
        file = self.field.get(self.field.context or self.context)
        if not isinstance(file, GCloudFile):
            raise KeyError('No file on this context')
        head_response = {
            'Upload-Offset': str(file.get_actual_size()),
            'Tus-Resumable': '1.0.0',
            'Access-Control-Expose-Headers': 'Upload-Offset,Upload-Length,Tus-Resumable'
        }
        if file.size:
            head_response['Upload-Length'] = str(file._size)
        resp = Response(headers=head_response)
        return resp

    async def tus_options(self):
        resp = Response(headers={
            'Tus-Resumable': '1.0.0',
            'Tus-Version': '1.0.0',
            'Tus-Max-Size': '1073741824',
            'Tus-Extension': 'creation,expiration'
        })
        return resp

    async def download(self, disposition=None):
        if disposition is None:
            disposition = self.request.GET.get('disposition', 'attachment')
        file = self.field.get(self.field.context or self.context)
        if not isinstance(file, GCloudFile) or file.uri is None:
            return HTTPNotFound(text='No file found')

        cors_renderer = app_settings['cors_renderer'](self.request)
        headers = await cors_renderer.get_headers()
        headers.update({
            'CONTENT-DISPOSITION': f'{disposition}; filename="%s"' % file.filename
        })

        download_resp = StreamResponse(headers=headers)
        download_resp.content_type = file.guess_content_type()
        if file.size:
            download_resp.content_length = file.size

        util = getUtility(IGCloudBlobStore)
        async with aiohttp.ClientSession() as session:
            url = '{}/{}/o/{}'.format(
                OBJECT_BASE_URL,
                await util.get_bucket_name(),
                quote_plus(file.uri)
            )
            async with session.get(
                    url, headers={
                        'AUTHORIZATION': 'Bearer %s' % await util.get_access_token()
                    }, params={
                        'alt': 'media'
                    }, timeout=-1) as api_resp:
                await download_resp.prepare(self.request)

                count = 0
                file_size = file.size or 0
                while True:
                    chunk = await api_resp.content.read(1024 * 1024)
                    if len(chunk) > 0:
                        count += len(chunk)
                        log.info("Download {}%.".format(int((count / file_size) * 100)))
                        download_resp.write(chunk)
                        await download_resp.drain()
                    else:
                        break

        return download_resp

    async def iter_data(self):
        file = self.field.get(self.field.context or self.context)
        if not isinstance(file, GCloudFile) or file.uri is None:
            raise AttributeError('No field value')

        util = getUtility(IGCloudBlobStore)
        async with aiohttp.ClientSession() as session:
            url = '{}/{}/o/{}'.format(
                OBJECT_BASE_URL,
                await util.get_bucket_name(),
                quote_plus(file.uri)
            )
            async with session.get(
                    url, headers={
                        'AUTHORIZATION': 'Bearer %s' % await util.get_access_token()
                    }, params={
                        'alt': 'media'
                    }, timeout=-1) as api_resp:
                while True:
                    chunk = await api_resp.content.read(1024 * 1024)
                    if len(chunk) > 0:
                        yield chunk
                    else:
                        break

    async def save_file(self, generator, content_type=None, size=None,
                        filename=None):
        self.context._p_register()  # writing to object

        file = self.field.get(self.field.context or self.context)
        if not isinstance(file, GCloudFile):
            file = GCloudFile(content_type=content_type)
            self.field.set(self.field.context or self.context, file)

        file._size = size
        if filename is None:
            filename = uuid.uuid4().hex
        file.filename = filename

        await file.init_upload(self.context)

        async for data in generator():
            await file.append_data(data)

        await file.finish_upload(self.context)
        return file


@implementer(IGCloudFile)
class GCloudFile(BaseCloudFile):
    """File stored in a GCloud, with a filename."""

    async def copy_cloud_file(self, new_uri):
        if self.uri is None:
            Exception('To rename a uri must be set on the object')
        util = getUtility(IGCloudBlobStore)
        async with aiohttp.ClientSession() as session:
            bucket_name = await util.get_bucket_name()
            url = '{}/{}/o/{}/copyTo/b/{}/o/{}'.format(
                OBJECT_BASE_URL,
                bucket_name,
                quote_plus(self.uri),
                bucket_name,
                quote_plus(new_uri)
            )
            async with session.post(
                    url, headers={
                        'AUTHORIZATION': 'Bearer %s' % await util.get_access_token(),
                        'Content-Type': 'application/json'
                    }) as resp:
                if resp.status == 404:
                    log.error(f'Could not rename file: {self.uri} to {new_uri}')
                data = await resp.json()
                assert data['name'] == new_uri

                old_uri = self.uri
                self._uri = new_uri
                return old_uri

    async def rename_cloud_file(self, new_uri):
        old_uri = await self.copy_cloud_file(new_uri)
        if old_uri:
            await self.delete_upload(old_uri)

    async def init_upload(self, context):
        """Init an upload.

        self._uload_file_id : temporal url to image beeing uploaded
        self._resumable_uri : uri to resumable upload
        self._uri : finished uploaded image
        """
        util = getUtility(IGCloudBlobStore)
        request = get_current_request()
        if hasattr(self, '_upload_file_id') and self._upload_file_id is not None:
            await self.delete_upload(self._upload_file_id)

        self._upload_file_id = self.generate_key(request, context)

        init_url = UPLOAD_URL.format(bucket=await util.get_bucket_name()) + '&name=' +\
            self._upload_file_id
        async with aiohttp.ClientSession() as session:

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
                        'AUTHORIZATION': 'Bearer %s' % await util.get_access_token(),
                        'X-Upload-Content-Type': to_str(self.content_type),
                        'X-Upload-Content-Length': str(self._size),
                        'Content-Type': 'application/json; charset=UTF-8',
                        'Content-Length': str(call_size)
                    },
                    data=metadata) as call:
                if call.status != 200:
                    text = await call.text()
                    raise GoogleCloudException(text)
                self._resumable_uri = call.headers['Location']

            self._current_upload = 0
            self._resumable_uri_date = datetime.now(tz=tzlocal())
            await notify(InitialGCloudUpload(context))

    async def append_data(self, data):
        async with aiohttp.ClientSession() as session:

            content_range = 'bytes {init}-{chunk}/{total}'.format(
                init=self._current_upload,
                chunk=self._current_upload + len(data) - 1,
                total=self._size)
            async with session.put(
                    self._resumable_uri,
                    headers={
                        'Content-Length': str(len(data)),
                        'Content-Type': to_str(self.content_type),
                        'Content-Range': content_range
                    },
                    data=data) as call:
                text = await call.text()  # noqa
                if call.status not in [200, 201, 308]:
                    log.error(text)
                # assert call.status in [200, 201, 308]
                if call.status == 308:
                    # gcloud sends a range position header, not a size so we append 1
                    self._current_upload = int(call.headers['Range'].split('-')[1]) + 1
                if call.status in [200, 201]:
                    self._current_upload = self._size
                return call

    def get_actual_size(self):
        return self._current_upload

    async def finish_upload(self, context):
        # It would be great to do on AfterCommit
        # Delete the old file and update the new uri
        if self.uri is not None:
            try:
                await self.delete_upload()
            except GoogleCloudException:
                log.warn(f'Could not delete existing google cloud file '
                         f'with uri: {self.uri}')
        self._uri = self._upload_file_id
        self._upload_file_id = None

        await notify(FinishGCloudUpload(context))

    async def delete_upload(self, uri=None):
        util = getUtility(IGCloudBlobStore)
        if uri is None:
            uri = self.uri
        if uri is not None:
            async with aiohttp.ClientSession() as session:
                url = '{}/{}/o/{}'.format(
                    OBJECT_BASE_URL,
                    await util.get_bucket_name(),
                    quote_plus(uri))
                async with session.delete(
                        url, headers={
                            'AUTHORIZATION': 'Bearer %s' % await util.get_access_token()
                        }) as resp:
                    try:
                        data = await resp.json()
                    except Exception:
                        data = {}
                        text = await resp.text()
                        log.error(f'Unknown error from google cloud: {text}, '
                                  f'status: {resp.status}')
                    if resp.status not in (200, 204, 404):
                        raise GoogleCloudException(json.dumps(data))
        else:
            raise AttributeError('No valid uri')


@implementer(IGCloudFileField)
class GCloudFileField(Object):
    """A NamedBlobFile field."""

    _type = GCloudFile
    schema = IGCloudFile

    def __init__(self, **kw):
        if 'schema' in kw:
            self.schema = kw.pop('schema')
        super(GCloudFileField, self).__init__(schema=self.schema, **kw)


# Configuration Utility

class GCloudBlobStore(object):

    def __init__(self, settings, loop=None):
        self._loop = loop
        self._json_credentials = settings['json_credentials']
        self._project = settings['project'] if 'project' in settings else None
        self._credentials = ServiceAccountCredentials.from_json_keyfile_name(
            self._json_credentials, SCOPES)
        self._bucket_name = settings['bucket']
        self._cached_buckets = []
        self._creation_access_token = datetime.now()

    def _get_access_token(self):
        access_token = self._credentials.get_access_token()
        self._creation_access_token = datetime.now()
        return access_token.access_token

    async def get_access_token(self):
        root = getUtility(IApplication, name='root')
        return await self._loop.run_in_executor(root.executor, self._get_access_token)

    def _get_or_create_bucket(self, bucket_name):
        client = google.cloud.storage.Client(
            project=self._project, credentials=self._credentials)
        try:
            bucket = client.get_bucket(bucket_name)  # noqa
        except google.cloud.exceptions.NotFound:
            bucket = client.create_bucket(bucket_name)
            log.warn('We needed to create bucket ' + bucket_name)
        return bucket

    async def get_bucket_name(self):
        request = get_current_request()
        if '.' in self._bucket_name:
            char_delimiter = '.'
        else:
            char_delimiter = '_'
        bucket_name = request._container_id.lower() + char_delimiter + self._bucket_name
        # we don't need to check every single time...
        if bucket_name in self._cached_buckets:
            return bucket_name

        root = getUtility(IApplication, name='root')
        await self._loop.run_in_executor(
            root.executor, self._get_or_create_bucket, bucket_name)

        self._cached_buckets.append(bucket_name)
        return bucket_name

    async def initialize(self, app=None):
        # No asyncio loop to run
        self.app = app

    async def iterate_bucket(self):
        req = get_current_request()
        async with aiohttp.ClientSession() as session:
            url = '{}/{}/o'.format(
                OBJECT_BASE_URL,
                await self.get_bucket_name())
            async with session.get(
                    url, headers={
                        'AUTHORIZATION': 'Bearer %s' % await self.get_access_token()
                    }, params={
                        'prefix': req._container_id + '/'
                    }) as resp:
                assert resp.status == 200
                data = await resp.json()
                if 'items' not in data:
                    return
                for item in data['items']:
                    yield item

            page_token = data.get('nextPageToken')
            while page_token is not None:
                async with session.get(
                        url, headers={
                            'AUTHORIZATION': 'Bearer %s' % await self.get_access_token()
                        }, params={
                            'prefix': req._container_id,
                            'pageToken': page_token
                        }) as resp:
                    data = await resp.json()
                    items = data.get('items', [])
                    if len(items) == 0:
                        break
                    for item in items:
                        yield item
                    page_token = data.get('nextPageToken')
