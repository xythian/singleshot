from struct import pack, unpack, calcsize

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
