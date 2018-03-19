# -*- coding: utf-8 -*-
from guillotina.interfaces import IFile
from guillotina.interfaces import IFileField
from zope.interface import Interface


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
