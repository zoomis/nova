#
#    Copyright (C) 2012.
#    Eliot J. Kang <joonmyung.kang@utoronto.ca>
#    Hadi Bannazadeh <hadi.bannazadeh@utoronto.ca>
#    Alberto Leon-Garcia <alberto.leongarcia@utoronto.ca>
#

"""
Scheduler host plugins
"""

import os
import types

from nova import exception
from nova.openstack.common import importutils


class BaseHostPlugin(object):
    """Base class for host plugins."""

    def host_select(self, host_state, plugin_properties):
        raise NotImplementedError()

    def _full_name(self):
        """module.classname of the plugin."""
        return "%s.%s" % (self.__module__, self.__class__.__name__)


def _is_plugin_class(cls):
    """Return whether a class is a valid Host Plugin class."""
    return type(cls) is types.TypeType and issubclass(cls, BasePluginFilter)


def _get_plugin_classes_from_module(module_name):
    """Get all filter classes from a module."""
    classes = []
    module = importutils.import_module(module_name)
    for obj_name in dir(module):
        itm = getattr(module, obj_name)
        if _is_plugin_class(itm):
            classes.append(itm)
    return classes


def standard_plugins():
    """Return a list of plugin classes found in this directory."""
    classes = []
    plugins_dir = __path__[0]
    for dirpath, dirnames, filenames in os.walk(plugins_dir):
        relpath = os.path.relpath(dirpath, plugins_dir)
        if relpath == '.':
            relpkg = ''
        else:
            relpkg = '.%s' % '.'.join(relpath.split(os.sep))
        for fname in filenames:
            root, ext = os.path.splitext(fname)
            if ext != '.py' or root == '__init__':
                continue
            module_name = "%s%s.%s" % (__package__, relpkg, root)
            mod_classes = _get_plugin_classes_from_module(module_name)
            classes.extend(mod_classes)
    return classes


def get_plugin_classes(plugin_class_names):
    """Get filter classes from class names."""
    classes = []
    for cls_name in plugin_class_names:
        obj = importutils.import_class(cls_name)
        if _is_plugin_class(obj):
            classes.append(obj)
        elif type(obj) is types.FunctionType:
            # Get list of classes from a function
            classes.extend(obj())
        else:
            raise exception.ClassNotFound(class_name=cls_name,
                    exception='Not a valid scheduler plugin')
    return classes
