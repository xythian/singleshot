from singleshot.properties import *
from singleshot.storage import FilesystemEntity
from singleshot.xmp import XMPHeader, EmptyXMPHeader

import os
import tempfile
import shutil
from cStringIO import StringIO
import re
import time
import mmap

def gcd(a, b):
   if b == 0:
      return a
   else:
      return gcd(b, a % b)


class Ratio(object):
    def __init__(self, num, den):
        self.num=num
        self.den=den
        self.reduce()

    def __repr__(self):
        if self.den == 1:
            return str(self.num)
        return '%d/%d' % (self.num, self.den)

    def floatformat(self):
        return '%.1f' % (float(self.num)/
                         float(self.den))

    def reduce(self):
        div=gcd(self.num, self.den)
        if div > 1:
            self.num=self.num/div
            self.den=self.den/div



EXIFDT = re.compile(r'(?P<year>\d\d\d\d):(?P<month>\d\d):(?P<day>\d\d) (?P<hour>\d\d):(?P<minute>\d\d):(?P<second>\d\d)')

def iptc_property(tuple, typ=None):
    def _delegate_get(self):
        result = self._get_property(tuple)
        if typ:
            if isinstance(result, str):
                return (result,)
            else:
                return result
        else:
            return result
    return property(_delegate_get)
    
class IptcHeader(object):
    def __init__(self, iptckeys):
        data = {}
        for tag, val in iptckeys:
            try:
                existing = data[tag]
                if isinstance(existing, str):
                    existing = [existing]
                    data[tag] = existing
                existing.append(val)
            except KeyError:
                data[tag] = val
        self.info = data

    def _get_property(self, tuple):
        try:
            return self.info[tuple]
        except KeyError:
            return ''

    caption = iptc_property((2, 120))
    author = iptc_property((2, 80))
    headline = iptc_property((2, 105))
    keywords = iptc_property((2, 25), tuple)
    title = iptc_property((2, 05))

class DummyIptc(object):
    caption = ''
    author = ''
    headline = ''
    keywords = ()
    title = ''

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

from struct import pack, unpack, calcsize


class ExposureMetadata(object):
    capture_time = None
    camera_mfg = None
    camera_model = None
    duration = None
    aperture = None
    focal = None
    iso = None

class JpegHeader(object):
    __metaclass__ = AutoPropertyMeta
    def __init__(self, path):
        self.comment = ''
        self.height = 0
        self.width = 0
        self.iptc = DummyIptc()
        self.path = path
        self.exposure = ExposureMetadata()
        self.load(path)
        


    def handle_sof(self, body, offset, length):
        self.height, self.width = unpack('>HH', body[offset+1:offset+5])

    def handle_comment(self, body, offset, length):
        self.comment = body[offset:offset+length]

    def handle_xmp(self, body, offset, length):
        self.__xmpbody = body[offset:offset+length]

    def handle_photoshop(self, body, offset, length):
        if body[offset:offset+14] != 'Photoshop 3.0\x00':
            return
        offset += 14
        while body[offset:offset+4] == '8BIM':        
            offset += 4
            code, namel = unpack('>HB', body[offset:offset+3])
            offset += 3
            offset += namel
            if offset & 1:
                offset += 1
            size = unpack('>I', body[offset:offset+4])[0]
            offset += 4
            if code == 0x404:
                self.iptc = IptcHeader(self.iptc_tags(offset, body, offset+size))
            offset += size
            if offset & 1:
                offset += 1


    def handle_exif(self, body, soffset, l):
        def bytes_of(start, length):
            return body[soffset+start:soffset+start+length]
        offset = soffset
        endian = body[offset:offset+2]
        e = {'II' : '<', 'MM' : '>'}[endian]
        def _unpack(fmt, val):
            return unpack(e+fmt, val)
        ifd_offset = _unpack('I', body[offset+4:offset+8])[0]
        xoffset = offset
        offset += ifd_offset
        data = self.decode_tags(body, offset, bytes_of, _unpack)
        exififd = 0
        try:
            exififd = data[0x8769]
        except KeyError:
            pass
        self.exposure.camera_mfg = data.get(0x10f)
        self.exposure.camera_model = data.get(0x110)
        self.exposure.capture_time = parse_exif_date(data.get(0x132))
        if exififd:
            exif = self.decode_tags(body, xoffset+exififd, bytes_of, _unpack,
                                    {0x829d : 1,
                                     0x829A : 1,
                                     0x920A : 1,
                                     0x8827 :1}.get)
            self.exposure.duration = exif.get(0x829a)
            self.exposure.aperture = exif.get(0x829d)
            self.exposure.focal = exif.get(0x920A)
            self.exposure.iso = exif.get(0x8827)
        

    def handle_app1(self, body, offset, length):
        if body[offset:offset+6] == 'Exif\x00\x00':
            self.handle_exif(body, offset+6, length-6)
#        elif body.startswith('http://ns.adobe.com/xap/1.0/\x00'):
#            self.handle_xmp(body[29:])
#        print body


    def _read_header(self, path, callbacks):
        fd = os.open(path, os.O_RDONLY)
        l = os.fstat(fd).st_size
        f = mmap.mmap(fd, l, access=mmap.ACCESS_READ)
        file = f
        try:
           if file[:2] != '\xFF\xD8':
               return ''
           offset = 2
           subhdr = file[offset:offset+4]
           while (subhdr[0] == '\xFF') and callbacks:
               ff, type, length = unpack('>BBH', subhdr)
               offset += 4
               length -= 2
               try:
                   callback = callbacks[type]
                   callback(file, offset, length)
               except KeyError:
                   pass
               offset += length              
               subhdr = file[offset:offset+4]
        finally:
            file.close()
            os.close(fd)

    def _get_xmp(self):
        if not self.__xmp_parsed and self.__xmpbody:
            self.__xmp_parsed = XMPHeader(self.__xmpbody)
        elif not self.__xmp_parsed:
            self.__xmp_parsed = self.emptyxmp
        return self.__xmp_parsed        


    def iptc_tags(self, offset, body, endoffset):
        while offset+3 < endoffset:
            hdr, t1, t2 = unpack('>BBB', body[offset:offset+3])
            if hdr != 0x1C or t1 < 1 or t1 > 9:
                break
            offset += 3
            size = ord(body[offset])
            if size & 128:
                sizesize = ((size-128) << 8) + (ord(body[offset]))
                offset += 2
                size = unpack('>I', ('\x00\x00\x00\x00' + body[offset:offset+sizesize][:-4]))
                offset += sizesize
            else:
                size = (size << 8) + ord(body[offset+1])
                offset += 2
            data = body[offset:offset+size]
            offset += size
            yield (t1, t2), data
            

    def ratiozip(self, data):
        ix = iter(data)        
        try:
            r = Ratio(ix.next(), ix.next())
            yield r
        except StopIteration:
            pass

    def decode_tags(self, body, offset, bytes_of, _unpack, want=lambda x:True):
        count = _unpack('H', body[offset:offset+2])[0]
        offset += 2
        result = {}
        for c in xrange(count):
            tag, typ, count, voffset = _unpack('HHII', body[offset:offset+12])
            if not want(tag):
                offset += 12
                continue
            if typ == 1 and count < 4:
                val = map(ord, body[offset+9:offset+9+count])
            elif typ == 1:
                val = map(ord, bytes_of(voffset, count))
            elif typ == 2:
                val = bytes_of(voffset, count-1)
            elif typ == 3 and count == 1:
                val = _unpack('H', body[offset+8:offset+10])[0]
            elif typ == 3 and count == 2:
                val = _unpack('HH', body[offset+8:offset+10])
            elif typ == 3:
                val = _unpack(('H' * count), bytes_of(voffset, 2*count))
            elif typ == 4 and count == 1:
                val = voffset
            elif typ == 4 and count > 1:
                val = _unpack(('I' * count), bytes_of(voffset, 4*count))
            elif typ == 5 and count == 1:
                val =Ratio(*_unpack(('II' * count), bytes_of(voffset, 8*count)))
            elif typ == 5:
                val = tuple(self.ratiozip(_unpack(('II' * count), bytes_of(voffset, 8*count))))
                if len(val) == 1:
                    val = val[0]
            elif typ == 7 and count < 4:
                val = body[offset+8:offset+8+count]
            elif typ == 7:
                val = bytes_of(voffset, count)
            elif typ == 9 and count == 1:
                val = _unpack('i', body[offset+8:offset+12])[0]
            elif typ == 9:
                val = _unpack(('i'*count), bytes_of(voffset, count*4))
            elif typ == 10:
                val = _unpack(('ii'*count), bytes_of(voffset, count*8))
            else:
                val = ''                
            offset += 12
            result[tag] = val
        return result
        


    emptyxmp = EmptyXMPHeader()

    def load(self, path):
        self.__xmp_parsed = None
        self.__xmpbody = None
        self._read_header(path, {0xC0 : self.handle_sof,
#                                 0xFE : self.handle_comment,
                                 0xED : self.handle_photoshop,
                                 0xE1 : self.handle_app1})




