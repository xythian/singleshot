import os
import tempfile
import shutil

import EXIF
import process
from properties import *
from storage import FilesystemEntity
from xmp import XMPHeader, EmptyXMPHeader

from ssconfig import CONFIG, STORE
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
    

def decode_2byte(bytes):
    return ord(bytes[0]) * 256 + ord(bytes[1])

def load_exif_python(path):
    file=open(path, 'rb')
    try:
        try:
            data = EXIF.process_file(file)
        finally:
            file.close()
    except:
        # file unreadable
        data = {}
    return data 

def load_exif_pil(path):
    data = Image.open(path)._getexif()
    if not data:
        return {}
    result = {}
    # add more tags later
    for tag in (36868, 36867):
        try:
            result[ExifTags.TAGS[tag]] = data[tag]
        except KeyError:
            pass
    return result
try:
    import Image
    import ExifTags
    load_exif = load_exif_pil
except ImportError:
    load_exif = load_exif_python

class JpegImage(FilesystemEntity):
    def _load_header(self):
        return JpegHeader(self.path)

    _header = demand_property('_header', _load_header)
    comment = delegate_property('_header', 'comment')
    height = delegate_property('_header', 'height')
    width = delegate_property('_header', 'width')    

    def _load_itpc(self):
        if HAS_ITPC:            
            return ItpcHeader(self.path)
        else:
            return DUMMY_ITPC

    def _load_xmp(self):
        return self._header.xmp

    itpc = demand_property('_itpc', _load_itpc)
    xmp = demand_property('_xmp', _load_xmp)

    def _load_title(self):
        if self.xmp.Headline:
            return self.xmp.Headline
#        elif self.itpc.headline:
#            return self.itpc.headline
        elif self.itpc.title:
            return self.itpc.title
#        elif self.comment:
#            return self.comment
        else:
            return self.filename

    title = demand_property('_title', _load_title)    
    caption = delegate_property('itpc', 'caption')
    keywords = delegate_property('xmp', 'keywords')

    def _load_exif(self):
        return load_exif(self.path)

    _exif = demand_property('exif', _load_exif)
    
    def get_exif(self, key):
        try:
            return self._exif[key].printable
        except KeyError:
            return 'Unknown'

    def dirty(self):
        pass

    def _do_update(self, operation, *args):
        tmpimage = tempfile.mktemp()
        stats = os.stat(self.path)
        try:
            if operation(tmpimage, *args):
                shutil.copyfile(tmpimage, self.path)
                os.remove(tmpimage)
                os.utime(self.path, stats[7:9])
                self.dirty()                
                return 1
        finally:
            if os.path.exists(tmpimage):
                os.remove(tmpimage)
        return 0

    def update_comment(self, comment):
        self._do_update(self._update_comment, comment)        
            
    def _update_comment(self, tmpimage, comment):
        wrjpgcom = os.path.join(CONFIG.libjpegbinPath, 'wrjpgcom')
        outfile = open(tmpimage, 'wb')        
        cmd = [wrjpgcom, "-replace", self.path]
        trace("Running: %s, tmpfile = %s", repr(cmd), tmpimage)
        p = process.ProcessProxy(cmd=cmd, stdout=outfile, env=CONFIG.getInvokeEnvironment())
        p.stdin.write(comment)
        p.stdin.close()
        r = p.wait()        
        p.close()
        outfile.close()
        if r != 0:
            return 0
        return 1

    def rotate(self, rotation):
        rotation = int(rotation)
        if rotation % 90 != 0:
            return 0
        self._do_update(self._do_rotate, rotation)
        
    def _do_rotate(self, tmpimage, rotation):
        jpegtran = os.path.join(CONFIG.libjpegbinPath, 'jpegtran')
        cmd = [jpegtran, '-copy', 'all', '-rotate', str(rotation), '-outfile', tmpimage, self.path]
        trace('Running: %s', repr(cmd))
        output = StringIO()
        p = process.ProcessProxy(cmd=cmd, stderr=output, stdout=output, env=CONFIG.getInvokeEnvironment())
        r = p.wait()
        if r != 0:
            trace("Running jpegtran %s -> %s failed: %s", self.path, tmpimage, output.getvalue())
            return 0
        p.close()
        return 1


class JpegHeader(object):
    def __init__(self, path):
        self.comment = ''
        self.height = 0
        self.width = 0
        self.load(path)

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
    xmp = property(_get_xmp)
    def load(self, path):
        self.__xmp_parsed = None
        self.__xmpbody = None
        self._read_header(path, {0xC0 : self.handle_sof,
                                 0xFE : self.handle_comment,
                                 0xE1 : self.handle_app1})




