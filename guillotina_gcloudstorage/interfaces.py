# -*- coding: utf-8 -*-
from zope.interface import Interface

from guillotina.interfaces import IFile
from guillotina.interfaces import IFileField


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
