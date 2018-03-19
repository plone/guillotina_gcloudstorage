# -*- coding: utf-8 -*-
from guillotina import configure


app_settings = {
    'cloud_storage': "guillotina_gcloudstorage.interfaces.IGCloudFileField"
}


def includeme(root, settings):
    configure.scan('guillotina_gcloudstorage.storage')
    if 'guillotina_rediscache' in settings.get('applications', []):
        configure.scan('guillotina_gcloudstorage.redisdm')
