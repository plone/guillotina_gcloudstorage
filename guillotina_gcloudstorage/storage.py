# -*- coding: utf-8 -*-
from datetime import datetime
from guillotina import configure
from guillotina.component import get_utility
from guillotina.exceptions import FileNotFoundException
from guillotina.files import BaseCloudFile
from guillotina.files.utils import generate_key
from guillotina.interfaces import IApplication
from guillotina.interfaces import IFileCleanup
from guillotina.interfaces import IFileStorageManager
from guillotina.interfaces import IJSONToValue
from guillotina.interfaces import IRequest
from guillotina.interfaces import IResource
from guillotina.response import HTTPNotFound
from guillotina.response import HTTPPreconditionFailed
from guillotina.schema import Object
from guillotina.utils import get_current_request
from guillotina.utils import to_str
from guillotina_gcloudstorage.interfaces import IGCloudBlobStore
from guillotina_gcloudstorage.interfaces import IGCloudFile
from guillotina_gcloudstorage.interfaces import IGCloudFileField
from oauth2client.service_account import ServiceAccountCredentials
from urllib.parse import quote_plus
from zope.interface import implementer

import aiohttp
import backoff
import google.cloud.exceptions
import google.cloud.storage
import json
import logging


class IGCloudFileStorageManager(IFileStorageManager):
    pass


log = logging.getLogger('guillotina_gcloudstorage')

MAX_SIZE = 1073741824

SCOPES = ['https://www.googleapis.com/auth/devstorage.read_write']
UPLOAD_URL = 'https://www.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=resumable'  # noqa
OBJECT_BASE_URL = 'https://www.googleapis.com/storage/v1/b'
CHUNK_SIZE = 524288
MAX_RETRIES = 5


class GoogleCloudException(Exception):
    pass


RETRIABLE_EXCEPTIONS = (
    GoogleCloudException,
    aiohttp.client_exceptions.ClientPayloadError
)


@configure.adapter(
    for_=(dict, IGCloudFileField),
    provides=IJSONToValue)
def dictfile_converter(value, field):
    return GCloudFile(**value)


@implementer(IGCloudFile)
class GCloudFile(BaseCloudFile):
    """File stored in a GCloud, with a filename."""


def _is_uploaded_file(file):
    return (file is not None and
            isinstance(file, GCloudFile) and
            file.uri is not None)


@configure.adapter(
    for_=(IResource, IRequest, IGCloudFileField),
    provides=IGCloudFileStorageManager)
class GCloudFileManager(object):

    file_class = GCloudFile

    def __init__(self, context, request, field):
        self.context = context
        self.request = request
        self.field = field

    def should_clean(self, file):
        cleanup = IFileCleanup(self.context, None)
        return cleanup is None or cleanup.should_clean(file=file, field=self.field)

    async def iter_data(self, uri=None):
        if uri is None:
            file = self.field.get(self.field.context or self.context)
            if not _is_uploaded_file(file):
                raise FileNotFoundException('Trying to iterate data with no file')
            else:
                uri = file.uri

        util = get_utility(IGCloudBlobStore)
        async with aiohttp.ClientSession() as session:
            url = '{}/{}/o/{}'.format(
                OBJECT_BASE_URL,
                await util.get_bucket_name(),
                quote_plus(uri)
            )
            async with session.get(
                    url, headers={
                        'AUTHORIZATION': 'Bearer %s' % await util.get_access_token()
                    }, params={
                        'alt': 'media'
                    }, timeout=-1) as api_resp:
                if api_resp.status != 200:
                    text = await api_resp.text()
                    raise GoogleCloudException(text)
                while True:
                    chunk = await api_resp.content.read(1024 * 1024)
                    if len(chunk) > 0:
                        yield chunk
                    else:
                        break

    @backoff.on_exception(backoff.expo, RETRIABLE_EXCEPTIONS, max_tries=4)
    async def start(self, dm):
        """Init an upload.

        _uload_file_id : temporal url to image beeing uploaded
        _resumable_uri : uri to resumable upload
        _uri : finished uploaded image
        """
        util = get_utility(IGCloudBlobStore)
        request = get_current_request()
        upload_file_id = dm.get('upload_file_id')
        if upload_file_id is not None:
            await self.delete_upload(upload_file_id)

        upload_file_id = generate_key(request, self.context)

        init_url = '{}&name={}'.format(
            UPLOAD_URL.format(bucket=await util.get_bucket_name()),
            quote_plus(upload_file_id))

        async with aiohttp.ClientSession() as session:

            creator = ','.join([x.principal.id for x
                                in request.security.participations])
            metadata = json.dumps({
                'CREATOR': creator,
                'REQUEST': str(request),
                'NAME': dm.get('filename')
            })
            call_size = len(metadata)
            async with session.post(
                    init_url,
                    headers={
                        'AUTHORIZATION': 'Bearer %s' % await util.get_access_token(),
                        'X-Upload-Content-Type': to_str(dm.content_type),
                        'X-Upload-Content-Length': str(dm.size),
                        'Content-Type': 'application/json; charset=UTF-8',
                        'Content-Length': str(call_size)
                    },
                    data=metadata) as call:
                if call.status != 200:
                    text = await call.text()
                    raise GoogleCloudException(text)
                resumable_uri = call.headers['Location']

            await dm.update(
                current_upload=0,
                resumable_uri=resumable_uri,
                upload_file_id=upload_file_id
            )

    async def delete_upload(self, uri):
        util = get_utility(IGCloudBlobStore)
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

    async def _append(self, dm, data, offset):
        if dm.size:
            size = dm.size
        else:
            # assuming size will come eventually
            size = '*'
        async with aiohttp.ClientSession() as session:
            content_range = 'bytes {init}-{chunk}/{total}'.format(
                init=offset,
                chunk=offset + len(data) - 1,
                total=size)
            async with session.put(
                    dm.get('resumable_uri'),
                    headers={
                        'Content-Length': str(len(data)),
                        'Content-Type': to_str(dm.content_type),
                        'Content-Range': content_range
                    },
                    data=data) as call:
                text = await call.text()  # noqa
                if call.status not in [200, 201, 308]:
                    log.error(text)
                return call

    async def append(self, dm, iterable, offset) -> int:
        count = 0
        async for chunk in iterable:
            resp = await self._append(dm, chunk, offset)
            size = len(chunk)
            count += size
            offset += len(chunk)

            if resp.status == 308:
                # verify we're on track with google's resumable api...
                range_header = resp.headers['Range']
                if offset - 1 != int(range_header.split('-')[-1]):
                    # range header is the byte range google has received,
                    # which is different from the total size--off by one
                    raise HTTPPreconditionFailed(content={
                        "reason": f'Guillotina and google cloud storage offsets do not match. '
                                  f'Google: {range_header}, TUS(offset): {offset}'
                    })
            elif resp.status in [200, 201]:
                # file manager will double check offsets and sizes match
                break
        return count

    async def finish(self, dm):
        file = self.field.get(self.field.context or self.context)
        if _is_uploaded_file(file):
            if self.should_clean(file):
                try:
                    await self.delete_upload(file.uri)
                except GoogleCloudException as e:
                    log.warn(f'Could not delete existing google cloud file '
                             f'with uri: {file.uri}: {e}')
        await dm.update(
            uri=dm.get('upload_file_id'),
            upload_file_id=None
        )

    async def copy(self, to_storage_manager, to_dm):
        file = self.field.get(self.field.context or self.context)
        if not _is_uploaded_file(file):
            raise HTTPNotFound(content={
                "reason": 'To copy a uri must be set on the object'
            })
        new_uri = generate_key(self.request, self.context)

        util = get_utility(IGCloudBlobStore)
        async with aiohttp.ClientSession() as session:
            bucket_name = await util.get_bucket_name()
            url = '{}/{}/o/{}/copyTo/b/{}/o/{}'.format(
                OBJECT_BASE_URL,
                bucket_name,
                quote_plus(file.uri),
                bucket_name,
                quote_plus(new_uri)
            )
            async with session.post(
                    url, headers={
                        'AUTHORIZATION': 'Bearer %s' % await util.get_access_token(),
                        'Content-Type': 'application/json'
                    }) as resp:
                if resp.status == 404:
                    text = await resp.text()
                    reason = f'Could not copy file: {file.uri} to {new_uri}:404: {text}'
                    log.error(reason)
                    raise HTTPNotFound(content={
                        "reason": reason
                    })
                else:
                    data = await resp.json()
                    assert data['name'] == new_uri
                    await to_dm.finish(
                        values={
                            'content_type': data['contentType'],
                            'size': int(data['size']),
                            'uri': new_uri,
                            'filename': file.filename or 'unknown'
                        }
                    )


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
        return self._get_access_token()

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

        root = get_utility(IApplication, name='root')
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
