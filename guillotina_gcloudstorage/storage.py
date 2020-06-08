# -*- coding: utf-8 -*-
from datetime import datetime
from guillotina import configure
from guillotina import task_vars
from guillotina.component import get_utility
from guillotina.exceptions import FileNotFoundException
from guillotina.files import BaseCloudFile
from guillotina.files.utils import generate_key
from guillotina.interfaces import IApplication
from guillotina.interfaces import IExternalFileStorageManager
from guillotina.interfaces import IFileCleanup
from guillotina.interfaces import IJSONToValue
from guillotina.interfaces import IRequest
from guillotina.interfaces import IResource
from guillotina.response import HTTPGone
from guillotina.response import HTTPNotFound
from guillotina.response import HTTPPreconditionFailed
from guillotina.schema import Object
from guillotina.utils import get_authenticated_user_id
from guillotina.utils import get_current_request
from guillotina.utils import to_str
from guillotina_gcloudstorage.interfaces import IGCloudBlobStore
from guillotina_gcloudstorage.interfaces import IGCloudFile
from guillotina_gcloudstorage.interfaces import IGCloudFileField
from oauth2client.service_account import ServiceAccountCredentials
from typing import AsyncIterator
from urllib.parse import quote_plus
from zope.interface import implementer

import aiohttp
import asyncio
import backoff
import google.api_core.exceptions
import google.cloud.exceptions
import google.cloud.storage
import json
import logging


class IGCloudFileStorageManager(IExternalFileStorageManager):
    pass


log = logging.getLogger("guillotina_gcloudstorage")

MAX_SIZE = 1073741824

SCOPES = ["https://www.googleapis.com/auth/devstorage.read_write"]
UPLOAD_URL = "https://www.googleapis.com/upload/storage/v1/b/{bucket}/o?uploadType=resumable"  # noqa
OBJECT_BASE_URL = "https://www.googleapis.com/storage/v1/b"
CHUNK_SIZE = 524288
MAX_RETRIES = 5


class GoogleCloudException(Exception):
    pass


RETRIABLE_EXCEPTIONS = (
    GoogleCloudException,
    aiohttp.client_exceptions.ClientPayloadError,
    aiohttp.client_exceptions.ClientConnectorError,
    aiohttp.client_exceptions.ClientOSError,
)


@configure.adapter(for_=(dict, IGCloudFileField), provides=IJSONToValue)
def dictfile_converter(value, field):
    return GCloudFile(**value)


@implementer(IGCloudFile)
class GCloudFile(BaseCloudFile):
    """File stored in a GCloud, with a filename."""


def _is_uploaded_file(file):
    return file is not None and isinstance(file, GCloudFile) and file.uri is not None


@configure.adapter(
    for_=(IResource, IRequest, IGCloudFileField), provides=IGCloudFileStorageManager
)
class GCloudFileManager(object):

    file_class = GCloudFile

    def __init__(self, context, request, field):
        self.context = context
        self.request = request
        self.field = field

    def should_clean(self, file):
        cleanup = IFileCleanup(self.context, None)
        return cleanup is None or cleanup.should_clean(file=file, field=self.field)

    async def iter_data(self, uri=None, headers=None):
        if uri is None:
            file = self.field.get(self.field.context or self.context)
            if not _is_uploaded_file(file):
                raise FileNotFoundException("Trying to iterate data with no file")
            else:
                uri = file.uri

        if headers is None:
            headers = {}

        util = get_utility(IGCloudBlobStore)
        url = "{}/{}/o/{}".format(
            OBJECT_BASE_URL, await util.get_bucket_name(), quote_plus(uri)
        )
        headers["AUTHORIZATION"] = "Bearer {}".format(await util.get_access_token())
        async with util.session.get(
            url, headers=headers, params={"alt": "media"}, timeout=-1
        ) as api_resp:
            if api_resp.status not in (200, 206):
                text = await api_resp.text()
                if api_resp.status == 404:
                    raise HTTPNotFound(
                        content={
                            "reason": "Google cloud file not found",
                            "response": text,
                        }
                    )
                elif api_resp.status == 401:
                    log.warning(f"Invalid google cloud credentials error: {text}")
                    raise HTTPNotFound(
                        content={
                            "reason": "Google cloud invalid credentials",
                            "response": text,
                        }
                    )
                raise GoogleCloudException(f"{api_resp.status}: {text}")
            while True:
                chunk = await api_resp.content.read(1024 * 1024)
                if len(chunk) > 0:
                    yield chunk
                else:
                    break

    async def range_supported(self) -> bool:
        return True

    async def read_range(self, start: int, end: int) -> AsyncIterator[bytes]:
        """
        Iterate through ranges of data
        """
        async for chunk in self.iter_data(
            headers={"Range": f"bytes={start}-{end - 1}"}
        ):
            yield chunk

    @backoff.on_exception(backoff.expo, RETRIABLE_EXCEPTIONS, max_tries=4)
    async def start(self, dm):
        """Init an upload.

        _uload_file_id : temporal url to image beeing uploaded
        _resumable_uri : uri to resumable upload
        _uri : finished uploaded image
        """
        util = get_utility(IGCloudBlobStore)
        request = get_current_request()
        upload_file_id = dm.get("upload_file_id")
        if upload_file_id is not None:
            await self.delete_upload(upload_file_id)

        upload_file_id = generate_key(self.context)

        init_url = "{}&name={}".format(
            UPLOAD_URL.format(bucket=await util.get_bucket_name()),
            quote_plus(upload_file_id),
        )

        creator = get_authenticated_user_id()
        metadata = json.dumps(
            {"CREATOR": creator, "REQUEST": str(request), "NAME": dm.get("filename")}
        )
        call_size = len(metadata)
        async with util.session.post(
            init_url,
            headers={
                "AUTHORIZATION": "Bearer {}".format(await util.get_access_token()),
                "X-Upload-Content-Type": to_str(dm.content_type),
                "X-Upload-Content-Length": str(dm.size),
                "Content-Type": "application/json; charset=UTF-8",
                "Content-Length": str(call_size),
            },
            data=metadata,
        ) as call:
            if call.status != 200:
                text = await call.text()
                raise GoogleCloudException(f"{call.status}: {text}")
            resumable_uri = call.headers["Location"]

        await dm.update(
            current_upload=0, resumable_uri=resumable_uri, upload_file_id=upload_file_id
        )

    @backoff.on_exception(backoff.expo, RETRIABLE_EXCEPTIONS, max_tries=4)
    async def delete_upload(self, uri):
        util = get_utility(IGCloudBlobStore)
        if uri is not None:
            url = "{}/{}/o/{}".format(
                OBJECT_BASE_URL, await util.get_bucket_name(), quote_plus(uri)
            )
            async with util.session.delete(
                url,
                headers={
                    "AUTHORIZATION": "Bearer {}".format(await util.get_access_token())
                },
            ) as resp:
                try:
                    data = await resp.json()
                except Exception:
                    text = await resp.text()
                    data = {"text": text}
                if resp.status not in (200, 204, 404):
                    if resp.status == 404:
                        log.error(
                            f"Attempt to delete not found gcloud: {data}, "
                            f"status: {resp.status}",
                            exc_info=True,
                        )
                    else:
                        raise GoogleCloudException(f"{resp.status}: {json.dumps(data)}")
        else:
            raise AttributeError("No valid uri")

    @backoff.on_exception(
        backoff.constant, RETRIABLE_EXCEPTIONS, interval=1, max_tries=4
    )
    async def _append(self, dm, data, offset):
        if dm.size is not None:
            size = dm.size
        else:
            # assuming size will come eventually
            size = "*"
        headers = {
            "Content-Length": str(len(data)),
            "Content-Type": to_str(dm.content_type),
        }
        if len(data) != size:
            content_range = "bytes {init}-{chunk}/{total}".format(
                init=offset, chunk=offset + len(data) - 1, total=size
            )
            headers["Content-Range"] = content_range

        util = get_utility(IGCloudBlobStore)
        async with util.session.put(
            dm.get("resumable_uri"), headers=headers, data=data
        ) as call:
            text = await call.text()  # noqa
            if call.status not in [200, 201, 308]:
                if call.status == 410:
                    raise HTTPGone(
                        content={
                            "reason": "googleError",
                            "message": "Resumable upload is no longer available",
                            "info": text,
                        }
                    )
                raise GoogleCloudException(f"{call.status}: {text}")
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
                range_header = resp.headers["Range"]
                if offset - 1 != int(range_header.split("-")[-1]):
                    # range header is the byte range google has received,
                    # which is different from the total size--off by one
                    raise HTTPPreconditionFailed(
                        content={
                            "reason": f"Guillotina and google cloud storage "
                            f"offsets do not match. Google: "
                            f"{range_header}, TUS(offset): {offset}"
                        }
                    )
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
                    log.warning(
                        f"Could not delete existing google cloud file "
                        f"with uri: {file.uri}: {e}"
                    )
        await dm.update(uri=dm.get("upload_file_id"), upload_file_id=None)

    @backoff.on_exception(backoff.expo, RETRIABLE_EXCEPTIONS, max_tries=4)
    async def exists(self):
        file = self.field.get(self.field.context or self.context)
        if not _is_uploaded_file(file):
            return False
        util = get_utility(IGCloudBlobStore)
        url = "{}/{}/o/{}".format(
            OBJECT_BASE_URL, await util.get_bucket_name(), quote_plus(file.uri)
        )
        async with util.session.get(
            url,
            headers={
                "AUTHORIZATION": "Bearer {}".format(await util.get_access_token())
            },
        ) as api_resp:
            return api_resp.status == 200

    @backoff.on_exception(backoff.expo, RETRIABLE_EXCEPTIONS, max_tries=4)
    async def copy(self, to_storage_manager, to_dm):
        file = self.field.get(self.field.context or self.context)
        if not _is_uploaded_file(file):
            raise HTTPNotFound(
                content={"reason": "To copy a uri must be set on the object"}
            )
        new_uri = generate_key(self.context)

        util = get_utility(IGCloudBlobStore)
        bucket_name = await util.get_bucket_name()
        url = "{}/{}/o/{}/copyTo/b/{}/o/{}".format(
            OBJECT_BASE_URL,
            bucket_name,
            quote_plus(file.uri),
            bucket_name,
            quote_plus(new_uri),
        )
        async with util.session.post(
            url,
            headers={
                "AUTHORIZATION": "Bearer {}".format(await util.get_access_token()),
                "Content-Type": "application/json",
            },
        ) as resp:
            if resp.status == 404:
                text = await resp.text()
                reason = (
                    f"Could not copy file: {file.uri} to {new_uri}:404: {text}"  # noqa
                )
                log.warning(reason)
                raise HTTPNotFound(content={"reason": reason})
            else:
                data = await resp.json()
                assert data["name"] == new_uri
                await to_dm.finish(
                    values={
                        "content_type": data["contentType"],
                        "size": int(data["size"]),
                        "uri": new_uri,
                        "filename": file.filename or "unknown",
                    }
                )


@implementer(IGCloudFileField)
class GCloudFileField(Object):
    """A NamedBlobFile field."""

    _type = GCloudFile
    schema = IGCloudFile

    def __init__(self, **kw):
        if "schema" in kw:
            self.schema = kw.pop("schema")
        super(GCloudFileField, self).__init__(schema=self.schema, **kw)


# Configuration Utility


class GCloudBlobStore(object):
    def __init__(self, settings, loop=None):
        self._loop = loop
        self._json_credentials = settings["json_credentials"]
        self._credentials = ServiceAccountCredentials.from_json_keyfile_name(
            self._json_credentials, SCOPES
        )
        self._bucket_name = settings["bucket"]
        self._location = settings.get("location", None)
        self._project = settings.get("project", None)
        # https://cloud.google.com/storage/docs/bucket-locations
        self._bucket_name_format = settings.get(
            "bucket_name_format", "{container}{delimiter}{base}"
        )
        self._bucket_labels = settings.get("bucket_labels") or {}
        self._uniform_bucket_level_access = settings.get(
            "uniform_bucket_level_access", False
        )
        self._cached_buckets = []
        self._creation_access_token = datetime.now()
        self._client = None
        self._session = None

    @property
    def session(self):
        if self._session is None:
            self._session = aiohttp.ClientSession()
        return self._session

    def _get_access_token(self):
        access_token = self._credentials.get_access_token()
        self._creation_access_token = datetime.now()
        return access_token.access_token

    async def get_access_token(self):
        return self._get_access_token()

    def get_client(self):
        if self._client is None:
            self._client = google.cloud.storage.Client.from_service_account_json(  # noqa
                self._json_credentials
            )
        return self._client

    def _create_bucket(self, bucket_name, client):
        bucket = google.cloud.storage.Bucket(client, name=bucket_name)
        try:
            bucket.create(client=client, project=self._project, location=self._location)
        except TypeError:
            # work with more versions of google storage api
            bucket.create(client=client)
        return bucket

    def _get_or_create_bucket(self, container, bucket_name, client):
        try:
            bucket = client.get_bucket(bucket_name)
        except google.cloud.exceptions.NotFound:
            try:
                bucket = self._create_bucket(bucket_name, client)
                log.warning("We needed to create bucket " + bucket_name)
            except google.api_core.exceptions.Conflict:
                # created by another process in the meantime
                bucket = client.get_bucket(bucket_name)

        try:
            labels = bucket.labels
        except AttributeError:
            labels = {}

        orig_labels = labels.copy()
        labels["container"] = container.id.lower()
        labels.update(self._bucket_labels)
        if (
            orig_labels != labels
            or bucket.iam_configuration.bucket_policy_only_enabled
            is not self._uniform_bucket_level_access
        ):
            bucket.iam_configuration.bucket_policy_only_enabled = (
                self._uniform_bucket_level_access
            )
            # only update if labels have changed
            bucket.labels = labels
            try:
                bucket.patch()
            except (
                google.api_core.exceptions.Conflict,
                google.api_core.exceptions.TooManyRequests,
                google.api_core.exceptions.ServiceUnavailable,
            ):
                ...
            except google.cloud.exceptions.Forbidden:
                log.warning(
                    "Insufficient permission to update bucket labels: {}".format(
                        bucket_name
                    )
                )
        return bucket

    async def get_bucket_name(self):
        if "." in self._bucket_name:
            char_delimiter = "."
        else:
            char_delimiter = "_"

        container = task_vars.container.get()
        bucket_name = self._bucket_name_format.format(
            container=container.id.lower(),
            delimiter=char_delimiter,
            base=self._bucket_name,
        )

        # we don't need to check every single time...
        if bucket_name in self._cached_buckets:
            return bucket_name

        client = self.get_client()
        root = get_utility(IApplication, name="root")
        loop = self._loop or asyncio.get_event_loop()
        await loop.run_in_executor(
            root.executor, self._get_or_create_bucket, container, bucket_name, client
        )

        self._cached_buckets.append(bucket_name)
        return bucket_name

    async def initialize(self, app=None):
        # No asyncio loop to run
        self.app = app

    async def iterate_bucket(self):
        url = "{}/{}/o".format(OBJECT_BASE_URL, await self.get_bucket_name())
        container = task_vars.container.get()
        async with self.session.get(
            url,
            headers={
                "AUTHORIZATION": "Bearer {}".format(await self.get_access_token())
            },
            params={"prefix": container.id + "/"},
        ) as resp:
            assert resp.status == 200
            data = await resp.json()
            if "items" not in data:
                return
            for item in data["items"]:
                yield item

        page_token = data.get("nextPageToken")
        while page_token is not None:
            async with self.session.get(
                url,
                headers={
                    "AUTHORIZATION": "Bearer {}".format(await self.get_access_token())
                },
                params={"prefix": container.id, "pageToken": page_token},
            ) as resp:
                data = await resp.json()
                items = data.get("items", [])
                if len(items) == 0:
                    break
                for item in items:
                    yield item
                page_token = data.get("nextPageToken")
