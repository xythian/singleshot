import sys
from ConfigParser import ConfigParser
import logging

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
