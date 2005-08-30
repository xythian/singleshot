import sys
from ConfigParser import ConfigParser

def trace(v, *args):
    msg = v
    if args:
        msg = v % args
    print >>sys.stderr, 'Trace: ', msg

def no_trace(v, *args):
    pass

trace = no_trace

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

def virtual_readonly_property(name):
    getter = '_get_%s' % name
    def _get(self):
        try:
            g = getattr(self, getter)
        except AttributeError:
            return None
        return g()
    return property(_get)

def virtual_property(name):
    getter = '_get_%s' % name
    setter = '_set_%s' % name
    def _get(self):
        try:
            g = getattr(self, getter)
        except AttributeError:
            return None
        return g()
        
    def _set(self, value):
        try:
            g = getattr(self, setter)
        except AttributeError:
            return None
        return g(value)    
    return property(_get, _set)


def virtual_demand_property(name):
    loader_name = '_load_%s' % name
    value_name = '_%s_value' % name
    def _get_vdemand_property(self):
        v = None
        try:
            return getattr(self, value_name)
        except AttributeError:
            try:
                loadfunc = getattr(self, loader_name)
            except AttributeError:
                v = None
                loadfunc = None
            if loadfunc:
                v = loadfunc()
            setattr(self, value_name, v)
            return v

    def _flush_vdemand_property(self):
        try:
            delattr(self, value_name)
        except AttributeError:
            # ok, not loaded
            pass
        
    return property(_get_vdemand_property, None, _flush_vdemand_property)

    
    

def config_property(key, section='DEFAULT', get='get'):
    def get_config_property(self):
        trace('config_property %s.%s [%s]', self, key, section)
        return getattr(self.config, get)(section, key)
    return property(get_config_property)

def writable_config_property(key, section='DEFAULT', get='get'):
    def get_config_property(self):
        trace('config_property %s.%s [%s]', self, key, section)
        return getattr(self.config, get)(section, key)
    def set_config_property(self, value):
        trace('config_property_set %s.%s [%s] = %s', self, key, section, value)
        if get_config_property(self) == value:
            return
        cfg = ConfigParser()
        cfg.read(self._config_path()[-1])
        if not cfg.has_section(section):
            cfg.add_section(section)
        cfg.set(section, key, value)
        fh = file(self._config_path()[-1], "w")
        cfg.write(fh)
        fh.close()
        del self.config
    return property(get_config_property, set_config_property)

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
