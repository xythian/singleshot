"""This module has slowly been accumulating various utility functions."""

__all__ = ['AutoPropertyMeta',
           'ViewMeta',
           'trace',
           'demand_property',
           'config_property',
           'delegate_property',
           'RecordBodyMeta',
           'PackedRecord',
           'parse_iso8601',
           'parse_exif_datetime',
           'dtfromtimestamp']

import sys
from ConfigParser import ConfigParser
import logging
from struct import pack, unpack, calcsize
from datetime import tzinfo, datetime, timedelta
import time as _time

LOG = logging.getLogger('singleshot')

class AutoPropertyMeta(type):
    def process_properties(cls, name, bases, dict):
        for key, val in dict.items():
            if key.startswith('_get_') and callable(val):
                pname = key[5:]
                if dict.has_key(pname):
                    continue
                getter = val
                if dict.has_key('_set_' + pname):
                    setter = dict['_set_' + pname]
                    prop = property(getter, setter)
                else:
                    prop = property(getter)
                dict[pname] = prop
            elif key.startswith('_load_') and callable(val):
                pname = key[6:]
                if dict.has_key(pname):
                    continue
                dict[pname] = demand_property(pname, val)
    process_properties = classmethod(process_properties)
    def __new__(cls, name, bases, dict):
        cls.process_properties(name, bases, dict)
        return super(AutoPropertyMeta, cls).__new__(cls, name, bases, dict)
    

class ViewMeta(AutoPropertyMeta):
    def process_properties(cls, name, bases, dict):
        super(ViewMeta, cls).process_properties(name, bases, dict)

        def any_has(name):
            for b in bases:
                if hasattr(b, name):
                    return True
            return False
        def process_of(c):
            if c == type:
                return
            for key, val in c.__dict__.items():
                if key.startswith('_'):
                    continue
                elif any_has(name):
                    continue
                elif dict.has_key(key):
                    continue
                def make_getter(key):
                    def getter(self):
                        return getattr(self._of, key)
                    return getter
                dict[key] = property(make_getter(key))
            for b in c.__bases__:
                process_of(b)
        try:
            view_of = dict['__of__']
            process_of(view_of)                        
        except KeyError:
            pass
    process_properties = classmethod(process_properties)    

LOG_TRACE = logging.getLogger('singleshot.trace')

def trace(v, *args):
    if LOG_TRACE.isEnabledFor(logging.DEBUG):
        LOG_TRACE.info(v, *args)

def wrap_printexc(func):
    def wrap_func(*args, **kw):
        trace("wrap_func: %s(%s)", func, args)
        try:
            return func(*args, **kw)
        except:
            import traceback
            traceback.print_exc()
            return None
    return wrap_func

def demand_property(name, loadfunc):
    def _get_demand_property(self):
        try:
            return getattr(self, '_%s_value' % name)
        except AttributeError:
            trace('demand_get %s.%s', self, name)
            v = loadfunc(self)
            setattr(self, '_%s_value' % name, v)
            trace('demand_get set %s.%s', self, name)
            return v
    def _flush_demand_property(self):
        try:
            delattr(self, '_%s_value' % name)
        except AttributeError:
            # ok, not loaded
            pass
        
    return property(_get_demand_property, None, _flush_demand_property)


def config_property(key, section='DEFAULT', get='get'):
    def get_config_property(self):
        trace('config_property %s.%s [%s]', self, key, section)
        return getattr(self.config, get)(section, key)
    return property(get_config_property)

def delegate_property(name, propname):
    def _delegate_get(self):
        trace('delegate_get %s.%s.%s', self, name, propname)
        o = getattr(self, name)
        if o:
            return getattr(o, propname)
        else:
            return o

    def _delegate_set(self, v):
        o = getattr(self, name)
        if o:
            setattr(o, propname, v)

    def _delegate_del(self):
        o = getattr(self, name)
        if o:
            delattr(o, propname)

    return property(_delegate_get, _delegate_set, _delegate_del)

class RecordBodyMeta(type):
    def __new__(cls, name, bases, classdict):
        try:
            fields = classdict['__fields__']
        except KeyError:
            return type.__new__(cls, name, bases, classdict)
        try:
            fmt = classdict['_format']
            if fmt:
                classdict['_length'] = calcsize(fmt)
        except KeyError:
            pass
        for i, columnname in enumerate(fields):
            def makeproperty(i, name, classdict):
                def getter(self):
                    return self._fields[i]
                def setter(self, v):
                    self._fields[i] = v
                classdict[columnname] = property(getter, setter, None)
            if classdict.has_key(columnname):
                raise TypeError, ("RecordBody class can't define %s" % columnname,)
            makeproperty(i, columnname, classdict)
        classdict['fieldCount'] = len(fields)        
        return type.__new__(cls, name, bases, classdict)

class PackedRecord(object):
    __metaclass__ = RecordBodyMeta
    __slots__ = ['_fields', '_length']

    _format = ''

    def __init__(self, _data='', **kwargs):
        self._fields = [0] * self.fieldCount        
        if _data:
            self._fields = self.unpack(_data)
        elif kwargs:
            for name, kval in kwargs.items():
                setattr(self, name, kval)
        else:
            self._fields = [0] * self.fieldCount

    def read(cls, data, offset):
        return offset + cls._length, cls(_data=data[offset:offset+cls._length])

    read = classmethod(read)

    def unpack(self, data):
        return list(unpack(self._format, data))

    def pack(self):
        return pack(self._format, *self._fields) 

# from the datetime documentation

ZERO = timedelta(0)
HOUR = timedelta(hours=1)

# A UTC class.

class UTC(tzinfo):
    """UTC"""

    def utcoffset(self, dt):
        return ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return ZERO

utc = UTC()

class FixedOffset(tzinfo):
    """Fixed offset in minutes east from UTC."""

    def __init__(self, offset=0, name='UTC'):
        self.__offset = timedelta(minutes = offset)
        self.__name = name

    def utcoffset(self, dt):
        return self.__offset

    def tzname(self, dt):
        return self.__name

    def dst(self, dt):
        return ZERO


STDOFFSET = timedelta(seconds = -_time.timezone)
if _time.daylight:
    DSTOFFSET = timedelta(seconds = -_time.altzone)
else:
    DSTOFFSET = STDOFFSET

DSTDIFF = DSTOFFSET - STDOFFSET

class LocalTimezone(tzinfo):

    def utcoffset(self, dt):
        if self._isdst(dt):
            return DSTOFFSET
        else:
            return STDOFFSET

    def dst(self, dt):
        if self._isdst(dt):
            return DSTDIFF
        else:
            return ZERO

    def tzname(self, dt):
        return _time.tzname[self._isdst(dt)]

    def _isdst(self, dt):
        tt = (dt.year, dt.month, dt.day,
              dt.hour, dt.minute, dt.second,
              dt.weekday(), 0, -1)
        stamp = _time.mktime(tt)
        tt = _time.localtime(stamp)
        return tt.tm_isdst > 0

Local = LocalTimezone()

def parse_iso8601(dt='', d='', t=''):
   if not dt and not d and not t:
      return None
   if dt:  
       try:
           idx = dt.index('T')
           d = dt[:idx]
           t = dt[idx+1:]
       except ValueError:
           d = dt
           t = ''   
   try:
      year, month, day = int(d[:4]), int(d[4:6]), int(d[6:])
   except ValueError:
      return None
   hour, minute, second = 0,0,0
   tzsign = '-'
   tzhour, tzminute = 0, 0
   tzname = 'UTC'
   if t:
      if len(t) == 11:
         try:
            hour, minute, second = int(t[:2]), int(t[2:4]), int(t[4:6])
            tzhour, tzminute = int(t[7:9]), int(t[9:])
            tzsign = t[6]
            tzname = t[6:]
         except ValueError:
            pass
      elif len(t) == 9:
         try:
            hour, minute, second = int(t[:2]), int(t[2:4]), 0
            tzhour, tzminute = int(t[6:8]), int(t[8:])            
            tzsign = t[4]
            tzname = t[4:]
         except ValueError:
            pass
   tzoffset = int(tzsign + str((tzhour * 60) + tzminute))
   tz = FixedOffset(tzoffset, tzname)
   t = datetime(year, month, day, hour, minute, second, tzinfo=tz)
   return t


def parse_exif_datetime(dt):
    dt = str(dt)
    # 2005:07:10 18:07:37
    # 0123456789012345678
    #           1       
    if len(dt) == 19:
        year, month, day = int(dt[:4]), int(dt[5:7]), int(dt[8:10])
        hour, minute, second = int(dt[11:13]), int(dt[14:16]), int(dt[17:19])
        return datetime(year, month, day, hour, minute, second, tzinfo=Local)
    return None
         
def dtfromtimestamp(t):
    return datetime.fromtimestamp(t, tz=Local)
