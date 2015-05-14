from __future__ import print_function

import sys
import base64
import hashlib
import tempfile
import os
import errno
import pickle
from xdg import BaseDirectory as xdg

try:
    from configparser import ConfigParser, Error as ConfigParserError
except ImportError:
    from ConfigParser import Error as ConfigParserError, SafeConfigParser as ConfigParser #py2 compat


class Db(object):
    """This is stupid.
    To be replaced with sqlite or something, when I have more then 5 minutes free
    """
    def __init__(self, path):
        assert os.path.exists(os.path.dirname(path))
        self.path = path
        if not os.path.exists(self.path):
            with open(self.path, 'wb') as pkl:
                pickle.dump({}, pkl)

    def read(self, section, k=None):
        with open(self.path, 'rb') as pkl:
            db = pickle.load(pkl)
            if not section in db: return
            if k:
                if not k in db[section]: return
                v = db[section][k]
            else:
                v = db[section]
            return v

    def write(self, section, k, v):
        db = None
        with open(self.path, 'rb') as pkl:
            db = pickle.load(pkl)

        with open(self.path, 'wb') as pkl:
            if not section in db: db[section] = {}
            if not k in db[section]: db[section][k] = {}
            db[section][k] = v
            pickle.dump(db, pkl)

    def delete(self, section, k):
        db = None
        with open(self.path, 'rb') as pkl:
            db = pickle.load(pkl)

        with open(self.path, 'wb') as pkl:
            if not section in db: return
            if not k in db[section]: return
            del db[section][k]
            pickle.dump(db, pkl)


class Config(object):
    def __init__(self):
        config_dir = xdg.save_config_path('hobo')
        data_dir = xdg.save_data_path('hobo')
        self.images_dir = os.path.join(data_dir, 'images')

        if not os.path.isdir(self.images_dir):
            os.mkdir(self.images_dir)

        self.template_file = os.path.join(self.images_dir, 'hobo.templates')
        touch(self.template_file)

        self.db = Db(os.path.join(data_dir, 'hobo.db'))

        config_file = os.path.join(config_dir, 'hobo.ini')
        self._cfg = ConfigParser()
        self._cfg.read(config_file)

        self.bridge_device = self.get('config', 'bridge_device') or 'hob0'
        self.base_mem = self.get('config', 'base_mem') or '1024'
        self.base_cpu = self.get('config', 'base_cpu') or '1'

        # compression analysis:
        #  -1 256M
        #  -9 213M
        #  --best 223M
        # might as well use -1
        # libvirt docs recommend:
        #   --best --block-size=16777216
        # but it's sloooow
        self.compress_flags = self.get('config', 'compress_flags') or '-1 -T0 --block-size=16777216'

    def get(self, section, attr):
        try:
            result = self._cfg.get(section, attr)
        except ConfigParserError:
            return

        return result


def mkdir_all(path):
    """Emulate "mkdir -p"
    """
    try:
        os.makedirs(path)
    except OSError as ex:
        if ex.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else: 
            raise


def tempname():
    """Generate a filesystem-friendly random name"""
    return '_hobo_{}'.format(
        next(tempfile._get_candidate_names())
    )


def touch(where):
    """Emulate "touch"
    """
    with open(where, 'a'):
        os.utime(where, None)


class cached_property(object):
    """ A property that is only computed once per instance and then replaces
        itself with an ordinary attribute. Deleting the attribute resets the
        property.

        Source: https://github.com/bottlepy/bottle/commit/fa7733e075da0d790d809aa3d2f53071897e6f76
        """

    def __init__(self, func):
        self.__doc__ = getattr(func, '__doc__')
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


def is_rh_family(platform):
    return \
        platform.startswith('centos') or \
        platform.startswith('rhel') or \
        platform.startswith('fedora')


def get_key_fingerprint(pubkey):
    key = base64.b64decode(pubkey.strip().split()[1].encode('ascii'))
    fp_plain = hashlib.md5(key).hexdigest()
    return ':'.join(a+b for a,b in zip(fp_plain[::2], fp_plain[1::2]))


class Timeout(Exception):
    pass


def timeout(signum, frame):
    raise Timeout
