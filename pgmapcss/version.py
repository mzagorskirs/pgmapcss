__all__ = 'VERSION', 'VERSION_INFO'

#: (:class:`tuple`) The version tuple e.g. ``(0, 9, 2)``.
VERSION_INFO = (0, 10, 5)

#: (:class:`basestring`) The version string e.g. ``'0.9.2'``.
if len(VERSION_INFO) == 4:
    VERSION = '%d.%d.%d-%s' % VERSION_INFO
elif type(VERSION_INFO[2]) == str:
    VERSION = '%d.%d-%s' % VERSION_INFO
else:
    VERSION = '%d.%d.%d' % VERSION_INFO
