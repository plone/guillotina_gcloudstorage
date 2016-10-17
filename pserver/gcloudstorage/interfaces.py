# -*- coding: utf-8 -*-
from zope.interface import Interface
from plone.server.interfaces import IFileField
from zope.interface import interfaces
from plone.server.interfaces import IFile


class IGCloudFileField(IFileField):
    """Field marked as GCloudFileField
    """

# Configuration Utility


class IGCloudBlobStore(Interface):
    """Configuration utility.
    """


class IGCloudFile(IFile):
    """Marker for a GCloudFile
    """


# Events

class IInitialGCloudUpload(interfaces.IObjectEvent):
    """An upload has started
    """


class IFinishGCloudUpload(interfaces.IObjectEvent):
    """An upload has started
    """
