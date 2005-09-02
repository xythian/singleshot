from singleshot.properties import *
from singleshot.storage import FilesystemEntity
from singleshot.xmp import XMPHeader, EmptyXMPHeader

import EXIF

import os
import tempfile
import shutil
from cStringIO import StringIO
import re
import time

EXIFDT = re.compile(r'(?P<year>\d\d\d\d):(?P<month>\d\d):(?P<day>\d\d) (?P<hour>\d\d):(?P<minute>\d\d):(?P<second>\d\d)')

def parse_exif_date(dt):
    dt = str(dt)
    m = EXIFDT.match(dt)
    if m:
        year, month, day, hour, minute, second = m.groups()
    else:
        return 0.0
    [year, month, day, hour, minute, second] = map(int, [year, month, day, hour, minute, second])
    t = time.mktime((year, month, day, hour, minute, second, -1, -1, 0))
    return t
    

HAS_ITPC = False
try:
    import IptcImagePlugin
    import Image

    IptcImagePlugin.getiptcinfo   # make sure the function we need is there
    
    def itpc_property(tuple):
        def _delegate_get(self):
            return self._get_property(tuple)
        return property(_delegate_get)
    
    class ItpcHeader(object):
        def __init__(self, path):
            img = Image.open(path)
            self.info = IptcImagePlugin.getiptcinfo(img)
	    if not self.info:
		self.info = {}

        def _get_property(self, tuple):
            try:
                return self.info[tuple]
            except KeyError:
                return ''

        caption = itpc_property((2, 120))
        author = itpc_property((2, 80))
        headline = itpc_property((2, 105))
        keywords = itpc_property((2, 25))
        title = itpc_property((2, 05))
        
        
    HAS_ITPC = True
except:
    class DummyItpc(object):
        caption = ''
        author = ''
        headline = ''
        keywords = ''
        title = ''
    DUMMY_ITPC = DummyItpc()

def calculate_box(size, width, height):
    if height > width:
        h2 = size
        w2 = int(float(size) * (float(width) / float(height)))
    else:
        w2 = size
        h2 = int(float(size) * (float(height) / float(width)))
    if h2 < height or w2 < width:
        return w2, h2
    else:
        return width, height
    

def decode_2byte(bytes):
    return ord(bytes[0]) * 256 + ord(bytes[1])


class JpegHeader(object):
    __metaclass__ = AutoPropertyMeta
    def __init__(self, path):
        self.comment = ''
        self.height = 0
        self.width = 0
        self.load(path)
        self.path = path
        

    def _load_itpc(self):
        if HAS_ITPC:            
            return ItpcHeader(self.path)
        else:
            return DUMMY_ITPC
     

    def handle_sof(self, body):
        self.height = decode_2byte(body[1:3])
        self.width = decode_2byte(body[3:5])

    def handle_comment(self, body):
        self.comment = body

    def _read_header(self, path, callbacks):
        file = open(path, 'rb')
        try:
           file.seek(0)
           header = file.read(2)
           if header != '\xFF\xD8':
                return ''
           subhdr = file.read(4)
           while (subhdr[0] == '\xFF') and callbacks:
              type = ord(subhdr[1])              
              length = decode_2byte(subhdr[2:4]) - 2
              try:
                  callback = callbacks[type]                  
                  body = file.read(length)
                  callback(body)
              except KeyError:
                  file.seek(length, 1)
              subhdr = file.read(4);
           return ''
        finally:
            file.close()

    def _get_xmp(self):
        if not self.__xmp_parsed and self.__xmpbody:
            self.__xmp_parsed = XMPHeader(self.__xmpbody)
        elif not self.__xmp_parsed:
            self.__xmp_parsed = self.emptyxmp
        return self.__xmp_parsed        

    def handle_xmp(self, body):
        self.__xmpbody = body
#        self.xmp = XMPHeader(body)

    def handle_app1(self, body):
        if len(body) > 4 and body[:4] == 'Exif':
            pass # exif data
        elif body.startswith('http://ns.adobe.com/xap/1.0/\x00'):
            self.handle_xmp(body[29:])
        pass
#        print body

    emptyxmp = EmptyXMPHeader()

    def load(self, path):
        self.__xmp_parsed = None
        self.__xmpbody = None
        self._read_header(path, {0xC0 : self.handle_sof,
                                 0xFE : self.handle_comment,
                                 0xE1 : self.handle_app1})




