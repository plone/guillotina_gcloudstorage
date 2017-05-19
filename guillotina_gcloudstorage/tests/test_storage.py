from guillotina.component import getUtility
from guillotina.tests.utils import create_content
from guillotina.tests.utils import login
from guillotina_gcloudstorage.interfaces import IGCloudBlobStore
from guillotina_gcloudstorage.storage import GCloudFileField
from guillotina_gcloudstorage.storage import GCloudFileManager, GCloudFile
from hashlib import md5
from zope.interface import Interface

import base64


_test_gif = base64.b64decode('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')  # noqa


class FakeContentReader:
    _read = False

    async def readexactly(self, size):
        if self._read:
            return b''
        self._read = True
        return _test_gif


class IContent(Interface):
    file = GCloudFileField()


def test_get_storage_object(dummy_request):
    request = dummy_request  # noqa
    request._container_id = 'test-container'
    util = getUtility(IGCloudBlobStore)
    assert util.access_token is not None
    assert util.bucket is not None


def _cleanup():
    util = getUtility(IGCloudBlobStore)
    req = util._service.objects().list(prefix='test-container', bucket=util.bucket)
    resp = req.execute()
    for item in resp.get('items', []):
        util._service.objects().delete(bucket=util.bucket, object=item['name']).execute()


async def test_store_file_in_cloud(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    _cleanup()

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
    mng = GCloudFileManager(ob, request, IContent['file'])
    await mng.upload()
    assert ob.file._upload_file_id is None
    assert ob.file.uri is not None

    assert ob.file.content_type == b'image/gif'
    assert ob.file.filename == 'test.gif'
    assert ob.file._size == len(_test_gif)
    assert ob.file.md5 is not None

    util = getUtility(IGCloudBlobStore)
    assert(len(util._service.objects().list(
        prefix='test-container', bucket=util.bucket).execute()['items']) == 1)
    await ob.file.deleteUpload()
    assert('items' not in util._service.objects().list(
        prefix='test-container', bucket=util.bucket).execute())


async def test_store_file_deletes_already_started(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    _cleanup()
    util = getUtility(IGCloudBlobStore)

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
    mng = GCloudFileManager(ob, request, IContent['file'])
    await mng.upload()
    assert ob.file._upload_file_id is None
    assert ob.file.uri is not None

    list_resp = util._service.objects().list(
        prefix='test-container', bucket=util.bucket).execute()
    assert len(list_resp['items']) == 1
    assert list_resp['items'][0]['name'] == ob.file.uri

    original = ob.file._uri
    ob.file._upload_file_id = ob.file._uri  # like it is in middle of upload
    ob.file._uri = None

    request._payload = FakeContentReader()

    await mng.upload()

    assert ob.file._upload_file_id is None
    assert ob.file.uri != original

    assert(len(util._service.objects().list(
        prefix='test-container', bucket=util.bucket).execute()['items']) == 1)
    await ob.file.deleteUpload()
    assert('ites' not in util._service.objects().list(
        prefix='test-container', bucket=util.bucket).execute())


def test_gen_key(dummy_request):
    request = dummy_request  # noqa
    request._container_id = 'test-container'
    ob = create_content()
    fi = GCloudFile()
    key = fi.generate_key(request, ob)
    assert key.startswith('test-container/')
    last = key.split('/')[-1]
    assert '::' in last
    assert last.split('::')[0] == ob._p_oid


async def test_rename(dummy_request):
    request = dummy_request  # noqa
    login(request)
    request._container_id = 'test-container'
    _cleanup()
    util = getUtility(IGCloudBlobStore)

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
    mng = GCloudFileManager(ob, request, IContent['file'])
    await mng.upload()

    await ob.file.rename_cloud_file('test-container/foobar')
    assert ob.file.uri == 'test-container/foobar'

    list_resp = util._service.objects().list(
        prefix='test-container', bucket=util.bucket).execute()
    assert len(list_resp['items']) == 1
    assert list_resp['items'][0]['name'] == 'test-container/foobar'
