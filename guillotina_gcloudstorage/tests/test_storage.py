from guillotina.component import get_utility
from guillotina.exceptions import UnRetryableRequestError
from guillotina.files import FileManager
from guillotina.files import MAX_REQUEST_CACHE_SIZE
from guillotina.files.adapter import DBDataManager
from guillotina.files.utils import generate_key
from guillotina.tests.utils import create_content
from guillotina.tests.utils import login
from guillotina_gcloudstorage.interfaces import IGCloudBlobStore
from guillotina_gcloudstorage.storage import CHUNK_SIZE
from guillotina_gcloudstorage.storage import GCloudFileField
from guillotina_gcloudstorage.storage import GCloudFileManager
from guillotina_gcloudstorage.storage import OBJECT_BASE_URL
from guillotina_gcloudstorage.storage import UPLOAD_URL
from hashlib import md5
from urllib.parse import quote_plus
from zope.interface import Interface

import aiohttp
import base64
import pytest


_test_gif = base64.b64decode('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')  # noqa


class FakeContentReader:

    def __init__(self, file_data=_test_gif):
        self._file_data = file_data
        self._pointer = 0

    async def readexactly(self, size):
        data = self._file_data[self._pointer:self._pointer + size]
        self._pointer += len(data)
        return data

    def seek(self, pos):
        self._pointer = pos


class IContent(Interface):
    file = GCloudFileField()


async def test_get_storage_object(dummy_request):
    request = dummy_request  # noqa
    request._container_id = 'test-container'
    util = get_utility(IGCloudBlobStore)
    assert await util.get_access_token() is not None
    assert await util.get_bucket_name() is not None


async def _cleanup():
    util = get_utility(IGCloudBlobStore)
    async for item in util.iterate_bucket():
        async with aiohttp.ClientSession() as session:
            url = '{}/{}/o/{}'.format(
                OBJECT_BASE_URL,
                await util.get_bucket_name(),
                quote_plus(item['name']))
            resp = await session.delete(url, headers={
                'AUTHORIZATION': 'Bearer %s' % await util.get_access_token()
            })
            await resp.json()
            assert resp.status in (200, 204, 404)


async def get_all_objects():
    util = get_utility(IGCloudBlobStore)
    items = []
    async for item in util.iterate_bucket():
        items.append(item)
    return items


async def test_store_file_in_cloud(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    await _cleanup()

    request.headers.update({
        'Content-Type': 'image/gif',
        'X-UPLOAD-MD5HASH': md5(_test_gif).hexdigest(),
        'X-UPLOAD-EXTENSION': 'gif',
        'X-UPLOAD-SIZE': len(_test_gif),
        'X-UPLOAD-FILENAME': 'test.gif'
    })
    request._payload = FakeContentReader()

    ob = create_content()
    ob.file = None
    mng = FileManager(ob, request, IContent['file'].bind(ob))
    await mng.upload()
    assert getattr(ob.file, 'upload_file_id', None) is None
    assert ob.file.uri is not None

    assert ob.file.content_type == 'image/gif'
    assert ob.file.filename == 'test.gif'
    assert ob.file._size == len(_test_gif)
    assert ob.file.md5 is not None

    assert(len(await get_all_objects()) == 1)
    gmng = GCloudFileManager(ob, request, IContent['file'].bind(ob))
    await gmng.delete_upload(ob.file.uri)
    assert len(await get_all_objects()) == 0


async def test_store_file_deletes_already_started(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    await _cleanup()

    request.headers.update({
        'Content-Type': 'image/gif',
        'X-UPLOAD-MD5HASH': md5(_test_gif).hexdigest(),
        'X-UPLOAD-EXTENSION': 'gif',
        'X-UPLOAD-SIZE': len(_test_gif),
        'X-UPLOAD-FILENAME': 'test.gif'
    })
    request._payload = FakeContentReader()

    ob = create_content()
    ob.file = None
    mng = FileManager(ob, request, IContent['file'].bind(ob))
    await mng.upload()
    assert getattr(ob.file, 'upload_file_id', None) is None
    assert ob.file.uri is not None

    items = await get_all_objects()
    assert len(items) == 1
    assert items[0]['name'] == ob.file.uri

    original = ob.file._uri
    ob.__uploads__ = {
        'file': {
            # like it is in middle of upload so it deletes existing
            'upload_file_id': ob.file.uri
        }
    }

    request._payload = FakeContentReader()
    request._cache_data = b''
    request._last_read_pos = 0

    await mng.upload()

    assert ob.file.upload_file_id is None
    assert ob.file.uri != original

    assert len(await get_all_objects()) == 1
    gmng = GCloudFileManager(ob, request, IContent['file'].bind(ob))
    await gmng.delete_upload(ob.file.uri)
    assert len(await get_all_objects()) == 0


async def test_store_file_when_request_retry_happens(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    await _cleanup()

    request.headers.update({
        'Content-Type': 'image/gif',
        'X-UPLOAD-MD5HASH': md5(_test_gif).hexdigest(),
        'X-UPLOAD-EXTENSION': 'gif',
        'X-UPLOAD-SIZE': len(_test_gif),
        'X-UPLOAD-FILENAME': 'test.gif'
    })
    request._payload = FakeContentReader()

    ob = create_content()
    ob.file = None
    mng = FileManager(ob, request, IContent['file'].bind(ob))
    await mng.upload()
    assert ob.file.upload_file_id is None
    assert ob.file.uri is not None

    items = await get_all_objects()
    assert len(items) == 1
    assert items[0]['name'] == ob.file.uri

    # test retry...
    request._retry_attempt = 1
    await mng.upload()

    assert ob.file.content_type == 'image/gif'
    assert ob.file.filename == 'test.gif'
    assert ob.file._size == len(_test_gif)

    assert len(await get_all_objects()) == 1
    gmng = GCloudFileManager(ob, request, IContent['file'].bind(ob))
    await gmng.delete_upload(ob.file.uri)
    assert len(await get_all_objects()) == 0


def test_gen_key(dummy_request):
    request = dummy_request  # noqa
    request._container_id = 'test-container'
    ob = create_content()
    key = generate_key(request, ob)
    assert key.startswith('test-container/')
    last = key.split('/')[-1]
    assert '::' in last
    assert last.split('::')[0] == ob._p_oid


async def test_copy(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    await _cleanup()

    request.headers.update({
        'Content-Type': 'image/gif',
        'X-UPLOAD-MD5HASH': md5(_test_gif).hexdigest(),
        'X-UPLOAD-EXTENSION': 'gif',
        'X-UPLOAD-SIZE': len(_test_gif),
        'X-UPLOAD-FILENAME': 'test.gif'
    })
    request._payload = FakeContentReader()

    ob = create_content()
    ob.file = None
    mng = FileManager(ob, request, IContent['file'].bind(ob))
    await mng.upload()

    new_ob = create_content()
    new_ob.file = None
    gmng = GCloudFileManager(ob, request, IContent['file'].bind(ob))
    dm = DBDataManager(gmng)
    await dm.load()
    new_gmng = GCloudFileManager(new_ob, request, IContent['file'].bind(new_ob))
    new_dm = DBDataManager(new_gmng)
    await new_dm.load()
    await gmng.copy(new_gmng, new_dm)

    new_ob.file.content_type == ob.file.content_type
    new_ob.file.size == ob.file.size
    new_ob.file.uri != ob.file.uri

    items = await get_all_objects()
    assert len(items) == 2


async def test_iterate_storage(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    await _cleanup()

    request.headers.update({
        'Content-Type': 'image/gif',
        'X-UPLOAD-MD5HASH': md5(_test_gif).hexdigest(),
        'X-UPLOAD-EXTENSION': 'gif',
        'X-UPLOAD-SIZE': len(_test_gif),
        'X-UPLOAD-FILENAME': 'test.gif'
    })

    for _ in range(20):
        request._payload = FakeContentReader()
        request._cache_data = b''
        request._last_read_pos = 0
        ob = create_content()
        ob.file = None
        mng = FileManager(ob, request, IContent['file'].bind(ob))
        await mng.upload()

    util = get_utility(IGCloudBlobStore)
    count = 0
    async for item in util.iterate_bucket():  # noqa
        count += 1
    assert count == 20

    await _cleanup()


async def test_download(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    await _cleanup()

    file_data = b''
    # we want to test multiple chunks here...
    while len(file_data) < CHUNK_SIZE:
        file_data += _test_gif

    request.headers.update({
        'Content-Type': 'image/gif',
        'X-UPLOAD-MD5HASH': md5(file_data).hexdigest(),
        'X-UPLOAD-EXTENSION': 'gif',
        'X-UPLOAD-SIZE': len(file_data),
        'X-UPLOAD-FILENAME': 'test.gif'
    })
    request._payload = FakeContentReader(file_data)

    ob = create_content()
    ob.file = None
    mng = FileManager(ob, request, IContent['file'].bind(ob))
    await mng.upload()
    assert ob.file.upload_file_id is None
    assert ob.file.uri is not None

    resp = await mng.download()
    assert resp.content_length == len(file_data)


async def test_raises_not_retryable(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    await _cleanup()

    file_data = b''
    # we want to test multiple chunks here...
    while len(file_data) < MAX_REQUEST_CACHE_SIZE:
        file_data += _test_gif

    request.headers.update({
        'Content-Type': 'image/gif',
        'X-UPLOAD-MD5HASH': md5(file_data).hexdigest(),
        'X-UPLOAD-EXTENSION': 'gif',
        'X-UPLOAD-SIZE': len(file_data),
        'X-UPLOAD-FILENAME': 'test.gif'
    })
    request._payload = FakeContentReader(file_data)

    ob = create_content()
    ob.file = None
    mng = FileManager(ob, request, IContent['file'].bind(ob))
    await mng.upload()

    request._retry_attempt = 1
    with pytest.raises(UnRetryableRequestError):
        await mng.upload()


async def test_upload_statuses(dummy_request):
    request = dummy_request
    request._container_id = 'test-container'
    util = get_utility(IGCloudBlobStore)
    upload_file_id = 'foobar124'
    bucket_name = await util.get_bucket_name()

    init_url = '{}&name={}'.format(
        UPLOAD_URL.format(bucket=bucket_name),
        upload_file_id)

    async with aiohttp.ClientSession() as session:
        async with session.post(
                init_url,
                headers={
                    'AUTHORIZATION': 'Bearer %s' % await util.get_access_token(),
                    'X-Upload-Content-Type': 'application/octet-stream',
                    'Content-Type': 'application/json; charset=UTF-8'
                }) as call:
            resumable_uri = call.headers['Location']

        async with session.put(
                resumable_uri,
                headers={
                    'Content-Length': '262144',
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': 'bytes 0-262143/*'
                },
                data=b'X' * 262144) as call:
            assert call.status == 308

        async with session.put(
                resumable_uri,
                headers={
                    'Content-Length': '262144',
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': 'bytes 262144-524287/*'
                },
                data=b'X' * 262144) as call:
            assert call.status == 308

        async with session.put(
                resumable_uri,
                headers={
                    'Content-Length': '100',
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': 'bytes 524288-524387/524388'
                },
                data=b'X' * 100) as call:
            assert call.status == 200


async def test_upload_same_chunk_multiple_times(dummy_request):
    request = dummy_request
    request._container_id = 'test-container'
    util = get_utility(IGCloudBlobStore)
    upload_file_id = 'foobar124'
    bucket_name = await util.get_bucket_name()

    init_url = '{}&name={}'.format(
        UPLOAD_URL.format(bucket=bucket_name),
        upload_file_id)

    async with aiohttp.ClientSession() as session:
        async with session.post(
                init_url,
                headers={
                    'AUTHORIZATION': 'Bearer %s' % await util.get_access_token(),
                    'X-Upload-Content-Type': 'application/octet-stream',
                    'Content-Type': 'application/json; charset=UTF-8'
                }) as call:
            resumable_uri = call.headers['Location']

        async with session.put(
                resumable_uri,
                headers={
                    'Content-Length': '262144',
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': 'bytes 0-262143/*'
                },
                data=b'X' * 262144) as call:
            assert call.status == 308

        async with session.put(
                resumable_uri,
                headers={
                    'Content-Length': '262144',
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': 'bytes 262144-524287/*'
                },
                data=b'X' * 262144) as call:
            assert call.status == 308
        async with session.put(
                resumable_uri,
                headers={
                    'Content-Length': '262144',
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': 'bytes 262144-524287/*'
                },
                data=b'X' * 262144) as call:
            assert call.status == 308
        async with session.put(
                resumable_uri,
                headers={
                    'Content-Length': '262144',
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': 'bytes 262144-524287/*'
                },
                data=b'X' * 262144) as call:
            assert call.status == 308

        async with session.put(
                resumable_uri,
                headers={
                    'Content-Length': '100',
                    'Content-Type': 'application/octet-stream',
                    'Content-Range': 'bytes 524288-524387/524388'
                },
                data=b'X' * 100) as call:
            assert call.status == 200


async def test_upload_works_with_plus_id(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    await _cleanup()

    request.headers.update({
        'Content-Type': 'image/gif',
        'X-UPLOAD-MD5HASH': md5(_test_gif).hexdigest(),
        'X-UPLOAD-EXTENSION': 'gif',
        'X-UPLOAD-SIZE': len(_test_gif),
        'X-UPLOAD-FILENAME': 'test.gif'
    })
    request._payload = FakeContentReader()

    parent = create_content(id='foobar')
    ob = create_content(id='foo+bar@foobar.com', parent=parent)
    ob.file = None
    mng = FileManager(ob, request, IContent['file'].bind(ob))
    await mng.upload()
    assert getattr(ob.file, 'upload_file_id', None) is None
    assert ob.file.uri is not None

    items = await get_all_objects()
    assert len(items) == 1
    assert items[0]['name'] == ob.file.uri
