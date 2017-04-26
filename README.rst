.. contents::

GUILLOTINA_GCLOUDSTORAGE
========================

GCloud blob storage for guillotina.


Example config.json entry:

    "utilities": {
        "provides": "guillotina_gcloudstorage.interfaces.IGCloudBlobStore",
        "factory": "guillotina_gcloudstorage.storage.GCloudBlobStore",
        "settings": {
            "json_credentials": "/path/to/credentials.json",
            "bucket": "name-of-bucket"
        }
    }
