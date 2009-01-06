from singleshot.properties import *
from singleshot.storage import FilesystemEntity
from singleshot.xmp import XMPHeader, EmptyXMPHeader

import os
import re
import mmap
from struct import pack, unpack, calcsize

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

    def floatformat(self, fmt='%.1f'):
        if self.den == 1:
            return str(self.num)
        return fmt % (float(self.num)/
                      float(self.den))

    def reduce(self):
        div=gcd(self.num, self.den)
        if div > 1:
            self.num=self.num/div
            self.den=self.den/div


def iptc_property(tuple, typ=None):
    def _delegate_get(self):
        result = self._get_property(tuple)
        if typ:
            if isinstance(result, str) and result:
                return (result,)
            elif not result:
               return ()
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
    date = iptc_property((2, 55))
    time = iptc_property((2, 60))

    def _get_datetime(self):
       return parse_iso8601(d=self.date, t=self.time)

    datetime = property(_get_datetime)

class DummyIptc(object):
    caption = ''
    author = ''
    headline = ''
    keywords = ()
    title = ''
    datetime = None
    info = {}

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


class ExposureMetadata(object):
    capture_time = None
    camera_mfg = None
    camera_model = None
    camera_serial = None
    capture_fileno = None
    duration = None
    aperture = None
    focal = None
    iso = None

def hexout(s, o=0):
   while s:
       print '  %3d: %02x %s' % (o, ord(s[0]), repr(s[0]))
       o += 1
       s = s[1:]


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

    def handle_app2(self, body, offset, length):
        pass

    def handle_app13(self, body, offset, length):
        pass
        
    def handle_photoshop(self, body, offset, length):
        endmark = offset+length
        if body[offset:offset+14] != 'Photoshop 3.0\x00':
            return
#        print repr(body[offset:offset+length])
        offset += 14
        while body[offset:offset+4] == '8BIM' and offset < endmark:
            start = offset
            offset += 4
            code, namel = unpack('>HB', body[offset:offset+3])
            if namel:
                offset += 3 + namel
#                if offset & 1:
#                    print 'skip ',repr(body[offset-10:offset+5])
#                    offset += 1
                size = unpack('>I', body[offset:offset+4])[0]
#                print 'size = ',size
#                print repr(body[offset:offset+4])
                offset += 4
#                print 'size = %d' % size
            else:
                offset = start + 10
#                print 'hexoutzor'
#                hexout(body[start:offset+2], start)
                size = unpack('>H', body[offset:offset+2])[0]
                offset += 2
#                print 'alternate size = %d' % size
#            if not size:
#                print 'bogus!!'
#                break
#                mx = body.find('8BIM', offset)
#                if mx > endmark or mx == -1:
#                    size = endmark - offset
#                else:
#                    size = mx - offset

#            print hex(code), namel, size
#            hexout(body[start:offset+5], start)
            if code == 0x404:
                xendmark = offset+size
                self.iptc = IptcHeader(self.iptc_tags(offset, body, xendmark))

            offset += size
#            if offset & 1:
#                offset += 1

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
        self.exposure.capture_time = parse_exif_datetime(data.get(0x132))
        
        if exififd:
           exiftags = {0x829d : 1,
                       0x829A : 1,
                       0x920A : 1,
                       0x8827 : 1}
           if data.get(0x10f) == 'Canon':
              exiftags[0x927C] = 1 # MakerNote             
           exif = self.decode_tags(body, xoffset+exififd, bytes_of, _unpack,
                                    exiftags.get)
           self.exposure.duration = exif.get(0x829a)
           self.exposure.aperture = exif.get(0x829d)
           self.exposure.focal = exif.get(0x920A)
           self.exposure.iso = exif.get(0x8827)
           if data.get(0x10f) == 'Canon':
              cmap = {15 : 'Auto', 16 : '50', 17 : '100', 18 : '200', 19 : '400'}
              data = exif.get(0x927C)
              if data:
                 canon = self.decode_tags(data, 0, bytes_of, _unpack, {0x0008 : 1, 0x000c : 1, 0x0001 : 1, 0x93 : 1}.get)
                 if canon.get(0x93) and not canon.get(0x008):                     
                     ix = unpack('<HI', pack('<16H', *canon.get(0x93))[:6])[1]
                     # thank you ExifTools, there's little hope I would've
                     # been patient enough to figure this out
                     self.exposure.capture_fileno = ((ix & 0xffc0)>>6)*10000+((ix>>16)&0xff)+((ix&0x3f)<<8)
                 else:
                     self.exposure.capture_fileno = canon.get(0x0008)
                 self.exposure.camera_serial = canon.get(0x000c)
                 ix1 = canon.get(0x001)
                 if ix1:
                    if not self.exposure.iso and ix1[16]:
                       self.exposure.iso = cmap.get(ix1[16])
                       
                 

    def handle_app1(self, body, offset, length):
        if body[offset:offset+6] == 'Exif\x00\x00':
            self.handle_exif(body, offset+6, length-6)
        elif body[offset:offset+29] == ('http://ns.adobe.com/xap/1.0/\x00'):
            self.handle_xmp(body, offset+29, length-29)

    def _read_markers(self, file, offset=2):
       while True:
          while ord(file[offset]) == 0xFF:
             offset += 1
          if ord(file[offset]) == 0xDA:
             return
          else:
             subhdr = file[offset:offset+3]
             type, length = unpack('>BH', subhdr)
             offset += 3
             length -= 2
             yield (offset, type, length)
             offset += length

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
           for offset, type, length in self._read_markers(file, 2):
               callback = None
               try:
                   callback = callbacks[type]
               except KeyError:
                   pass
               if callback:
                  try:
                     callback(file, offset, length)
                  except:
                     # for now, eat the exception
                     pass
               else:
                   pass
#                   print hex(type), length
#                   hexout(file[offset:offset+50])
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
#        print repr(body[offset-30:offset+20])
#        print endoffset - offset
        while offset+3 < endoffset:
            hdr, t1, t2 = unpack('>BBB', body[offset:offset+3])
            if hdr != 0x1C or t1 < 1 or t1 > 9:
               offset += 3
               continue
            offset += 3
            size = ord(body[offset])
            if size & 128:
                sizesize = ((size-128) << 8) + (ord(body[offset+1]))
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
        


    def load(self, path):
        self.__xmp_parsed = None
        self.__xmpbody = None
        self._read_header(path, {0xC0 : self.handle_sof,
                                 0xC2 : self.handle_sof, # progressive
#                                 0xFE : self.handle_comment,
#                                 0xE2 : self.handle_app2,
                                 0xEE : self.handle_app13,
                                 0xED : self.handle_photoshop,
                                 0xE1 : self.handle_app1})
        if self.__xmpbody and isinstance(self.iptc, DummyIptc):
            xmp = XMPHeader(self.__xmpbody)
            if hasattr(xmp, 'caption'):
                self.iptc.caption = str(xmp.caption[0])
            if hasattr(xmp, 'keywords'):
                self.iptc.keywords = map(str, xmp.keywords)
            if hasattr(xmp, 'Headline'):
                self.iptc.headline = str(xmp.Headline)




