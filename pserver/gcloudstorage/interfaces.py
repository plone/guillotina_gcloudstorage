# -*- coding: utf-8 -*-
from zope.interface import Interface
from plone.server.interfaces import IFileField
from zope.interface import interfaces
from plone.server.interfaces import IFile
from zope.schema import TextLine
from plone.server.directives import index
from plone.server.directives import catalog


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

    catalog(extension='string')
    index(extension='non_analyzed')
    extension = TextLine(
        title='Extension of the file',
        default='')

    catalog(md5='string')
    index(md5='non_analyzed')
    md5 = TextLine(
        title='MD5',
        default='')

# Events

class IInitialGCloudUpload(interfaces.IObjectEvent):
    """An upload has started
    """


class IFinishGCloudUpload(interfaces.IObjectEvent):
    """An upload has started
    """
