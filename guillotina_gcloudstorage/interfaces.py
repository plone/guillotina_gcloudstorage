# -*- coding: utf-8 -*-
from guillotina.interfaces import IFile
from guillotina.interfaces import IFileField
from guillotina.interfaces import IFileFinishUploaded
from zope.interface import Interface
from zope.interface import interfaces


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


class IFinishGCloudUpload(IFileFinishUploaded):
    """An upload has started
    """
