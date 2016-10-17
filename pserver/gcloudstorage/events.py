# -*- encoding: utf-8 -*-
from pserver.gcloudstorage.interfaces import IInitialGCloudUpload
from pserver.gcloudstorage.interfaces import IFinishGCloudUpload
from zope.interface import implementer
from zope.interface.interfaces import ObjectEvent


@implementer(IInitialGCloudUpload)
class InitialGCloudUpload(ObjectEvent):
    """An object has been created"""


@implementer(IFinishGCloudUpload)
class FinishGCloudUpload(ObjectEvent):
    """An object has been created"""
