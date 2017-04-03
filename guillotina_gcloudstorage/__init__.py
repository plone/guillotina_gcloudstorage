# -*- coding: utf-8 -*-
from guillotina import configure


app_settings = {
    'cloud_storage': "guillotina_gcloudstorage.interfaces.IGCloudFileField"
}


def includeme(root):
    configure.scan('guillotina_gcloudstorage.storage')
