from guillotina import configure
from guillotina.interfaces import IUploadDataManager
from guillotina_gcloudstorage.storage import IGCloudFileStorageManager
from guillotina_rediscache.files import RedisFileDataManager


@configure.adapter(
    for_=IGCloudFileStorageManager,
    provides=IUploadDataManager)
class GCloudDataManager(RedisFileDataManager):
    pass
