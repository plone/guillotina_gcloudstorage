from guillotina_gcloudstorage.storage import GCloudBlobStore
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture()
def credentials():
    yield MagicMock()


@pytest.fixture()
def store(credentials):

    with patch(
        "guillotina_gcloudstorage.storage.ServiceAccountCredentials.from_json_keyfile_name",
        return_value=credentials,
    ):
        yield GCloudBlobStore({"json_credentials": None, "bucket": "foobar"})


async def test_get_access_token_missing(store, credentials):
    credentials.access_token = None
    await store.get_access_token()
    credentials.refresh.assert_called_once()


async def test_get_access_token_refresh(store, credentials):
    credentials.access_token_expired = True
    await store.get_access_token()
    credentials.refresh.assert_called_once()


async def test_get_access_token_cached(store, credentials):
    credentials.access_token_expired = False
    await store.get_access_token()
    credentials.refresh.assert_not_called()
