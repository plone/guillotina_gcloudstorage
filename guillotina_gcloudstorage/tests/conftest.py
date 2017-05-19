from guillotina.testing import TESTING_SETTINGS

import os


if 'applications' in TESTING_SETTINGS:
    TESTING_SETTINGS['applications'].append('guillotina_gcloudstorage')
else:
    TESTING_SETTINGS['applications'] = ['guillotina_gcloudstorage']

TESTING_SETTINGS['utilities'] = [{
    "provides": "guillotina_gcloudstorage.interfaces.IGCloudBlobStore",
    "factory": "guillotina_gcloudstorage.storage.GCloudBlobStore",
    "settings": {
        "json_credentials": os.environ['GCLOUD_CREDENTIALS'],
        "bucket": os.environ['GCLOUD_BUCKET'],
        "project": os.environ['GCLOUD_PROJECT']
    }
}]

from guillotina.tests.conftest import *  # noqa
