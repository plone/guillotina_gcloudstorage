# -*- encoding: utf-8 -*-
from guillotina_gcloudstorage.interfaces import IFinishGCloudUpload
from guillotina_gcloudstorage.interfaces import IInitialGCloudUpload
from zope.interface import implementer
from zope.interface.interfaces import ObjectEvent


@implementer(IInitialGCloudUpload)
class InitialGCloudUpload(ObjectEvent):
    """An object has been created"""


@implementer(IFinishGCloudUpload)
class FinishGCloudUpload(ObjectEvent):
    """An object has been created"""
