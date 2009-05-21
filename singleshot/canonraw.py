
#
# Canon Raw manipulation
#


import sys

from fnmatch import fnmatch
import hotshot
import os
import mmap
import time
import timeit

from datetime import datetime
from singleshot.jpeg import JpegHeader, ExposureMetadata, DummyIptc, Ratio
from singleshot.properties import *
from singleshot.storage import FilesystemEntity
from struct import unpack, pack
from array import array

class CRWPre(PackedRecord):
    __fields__ = ['ByteOrder', 'BlockStart', 'Signature']
    _format = '<2sI8s'

# this one doesn't work, need to find better info about it
class CanonShotInfo(PackedRecord):
    __fields__ = ['ISO',
                  'TargetAperture',
                  'TargetExposureTime',
                  'ExposureCompensation',
                  'WhiteBalance',
                  'SequenceNumber',
                  'IxusAFPoint',
                  'FlashExposureComp',
                  'AutoExposureBracketing',
                  'AEBBracketValue',
                  'FocusDistanceUpper',
                  'FocusDistanceLower',
                  'FNumber',
                  'ExposureTime',
                  'BulbDuration',
                  'AutoRotate',
                  'SelfTimer2']
    _format = '<hhbhibbbhbbbhih'

class CanonFileInfo(PackedRecord):
    __fields__ = ['FileNumber',
                  'ShutterCount']
    _format = '<II'

class CanonPictureInfo(PackedRecord):
    __fields__ = ['CanonImageWidth',
                  'CanonImageHeight',
                  'CanonImageWidthAsShot',
                  'CanonImageHeightAsShot',
                  'AFPointsUsed']

    _format = '<HHHHH'

class CanonImageInfo(PackedRecord):
    __fields__ = ['ImageWidth',
                  'ImageHeight',
                  'PixelAspectRatio',
                  'Rotation',
                  'ComponentBitDepth',
                  'ColorBitDepth',
                  'ColorBW']

    _format = '<2if4i'

class CRWDirectoryEntry(PackedRecord):
    __fields__ = ['Tag', 'Size', 'Offset']

    _format = '<HII'

    def _get_DataLocation(self):
        return self.Tag & 0xc000

    def _get_DataFormat(self):
        return self.Tag & 0x3800

    def _get_TagIndex(self):
        return self.Tag & 0x7ff

    def _get_TagID(self):
        return self.DataFormat + self.TagIndex

    DataLocation = property(_get_DataLocation)
    DataFormat = property(_get_DataFormat)
    TagIndex = property(_get_TagIndex)
    TagID = property(_get_TagID)

def CRW_EntryValue(entry, block):
    if entry.DataLocation == 0x4000:
        return entry._raw[2:]
    else:
        return buffer(block, entry.Offset, entry.Size)


def CRW_Entries(block):
    s = unpack('<I', block[-4:])[0]
    count = unpack('<H', block[s:s+2])[0]
    diroff = s + 2
    for c in xrange(count):
        diroff, entry = CRWDirectoryEntry.read(block, diroff, saveraw=True)
#        print 'entry: location: %s format: %s index: %s TagId: %s' % (hex(entry.DataLocation), hex(entry.DataFormat), hex(entry.TagIndex), hex(entry.TagID))
        yield entry


class CRWHeader(object):
    __metaclass__ = AutoPropertyMeta

    def __init__(self, path):
        self.comment = ''
        self.height = 0
        self.width = 0
        self.path = path
        self.exposure = ExposureMetadata()
        self.load(path)

    def _read(self, data):
        offset, hdr = CRWPre.read(data, 0)
        if hdr.Signature != 'HEAPCCDR':
            raise 'Not a CRW file'
        data = buffer(data, hdr.BlockStart)
        for entry in CRW_Entries(data):
            if entry.TagID == 0x300a:  # ImageProps
                self._read_ImageProps(buffer(data, entry.Offset, entry.Size))
        self.iptc = DummyIptc()
        self.exposure.camera_mfg = self.Make
        self.exposure.camera_model = self.Model
        self.exposure.capture_fileno = self.FileNumber        
        self.exposure.camera_serial = self.CameraSerialNumber
        self.exposure.duration = None
        self.exposure.aperture = None
        self.exposure.focal = None
        self.exposure.iso = self.ISO

    def _readString(self, name):
        def handle(entry, block):
            value = CRW_EntryValue(entry, block)
            idx = str(value).find('\0')
            if idx > -1:
                value = value[:idx]
#            print '%s: %s' % (name, value)
            setattr(self, name, value)
        return handle

    def _readInt(self, name):
        def handle(entry, block):
            value = unpack('<I', CRW_EntryValue(entry, block)[:4])[0]
#            print '%s: %s' % (name, value)
            setattr(self, name, value)
        return handle

    def _readShort(self, name):
        def handle(entry, block):
            value = unpack('<H', CRW_EntryValue(entry, block)[:2])[0]
#            print '%s: %s' % (name, value)
            setattr(self, name, value)
        return handle

#    def _read_ShotInfo(self, entry, block):
#        v = CRW_EntryValue(entry, block)
#        print repr(str(v)), len(v)
#        of, info = CanonShotInfo.read(CRW_EntryValue(entry, block))
#        for field in info.__fields__:
#            print field, ' = ',getattr(info, field)

#    def _read_PictureInfo(self, entry, block):
#        of, info = CanonPictureInfo.read(CRW_EntryValue(entry, block))
#        for field in info.__fields__:
#            print field, ' = ',getattr(info, field)
            

    def _read_ImageInfo(self, entry, block):
        of, info = CanonImageInfo.read(CRW_EntryValue(entry, block), 0)
        self.width = info.ImageWidth
        self.height = info.ImageHeight
        self.rotation = info.Rotation
#        for field in info.__fields__:
#            print field, ' = ',getattr(info, field)

    def _read_MakeModel(self, entry, block):
        value = CRW_EntryValue(entry, block)
        make = value[:5]
        model = value[6:]
        idx = model.find('\0')
        if idx > -1:
            model = model[:idx]
#        print 'Make: %s Model: %s' % (make, model)
        self.Make = make
        self.Model = model

    def _read_TimeStamp(self, entry, block):
        when, ts, what = unpack('<IiI', CRW_EntryValue(entry, block))
#        print time.ctime(when), ts, what
        self.exposure.capture_time = datetime.fromtimestamp(when)
            

    def _read_ImageProps(self, block):
        mapped = {0x0816 : self._readString('OriginalFileName'),
                  0x0817 : self._readString('ThumbnailFileName'),
                  0x080a : self._read_MakeModel,
                  0x1804 : self._readInt('RecordID'),
                  0x1810 : self._read_ImageInfo,
#                  0x102a : self._read_ShotInfo,
#                  0x1038 : self._read_PictureInfo,
                  0x101c : self._readShort('ISO'),
                  0x180b : self._readInt('CameraSerialNumber'),
                  0x1817 : self._readInt('FileNumber'),
                  0x180e : self._read_TimeStamp
                  }
        for entry in CRW_Entries(block):
            handler = mapped.get(entry.TagID)
            if handler:
                handler(entry, block)
            elif entry.TagID in (0x300b, 0x3004, 0x2807, 0x300a): # exifinformation, camera spec, camera object
                self._read_ImageProps(buffer(block, entry.Offset, entry.Size))
    def load(self, path):
        fd = os.open(path, os.O_RDONLY)
        l = os.fstat(fd).st_size
        self.disksize = l
        try:
            f = mmap.mmap(fd, l, access=mmap.ACCESS_READ)
        except:
            print path, l
            raise
        try:
            self._read(f)
        finally:
            del f            
            os.close(fd)

class CR2Pre(PackedRecord):
    __fields__ = ['ByteOrder', 'Signature', 'IFDOffset']

    _format = '<2sHI'

class CR2Header(CRWHeader):
    def _read(self, body):
        offset, hdr = CR2Pre.read(body, 0)
        def bytes_of(start, length):
            return body[start:start+length]
        e = {'II' : '<', 'MM' : '>'}[hdr.ByteOrder]
        def _unpack(fmt, val):
            return unpack(e+fmt, val)
#        print 'CR2: ',hdr.Signature, hdr.IFDOffset
        data = self.decode_tags(body, hdr.IFDOffset, bytes_of, _unpack)
        self.width = data.get(0x100, 0)
        self.height = data.get(0x101, 0) 
        exififd = 0
        try:
            exififd = data[0x8769]
        except KeyError:
            pass
        self.exposure.camera_mfg = data.get(0x10f)
        self.exposure.camera_model = data.get(0x110)
        self.exposure.capture_time = parse_exif_datetime(data.get(0x132))
        if exififd:
#           print 'now exif'
           exiftags = {0x829d : 1,
                       0x829A : 1,
                       0x920A : 1,
                       0x100 : 1,
                       0x101 : 1,
                       0x8827 : 1}
           if data.get(0x10f) == 'Canon':
              exiftags[0x927C] = 1 # MakerNote
           exif = self.decode_tags(body, exififd, bytes_of, _unpack) # , exiftags.get)
           self.exposure.duration = exif.get(0x829a)
           self.exposure.aperture = exif.get(0x829d)
           self.exposure.focal = exif.get(0x920A)
           self.exposure.iso = exif.get(0x8827)
           if data.get(0x10f) == 'Canon':
              cmap = {15 : 'Auto', 16 : '50', 17 : '100', 18 : '200', 19 : '400'}
              data = exif.get(0x927C)
              if data:
                 canon = self.decode_tags(data, 0, bytes_of, _unpack) # , {0x0008 : 1, 0x000c : 1, 0x0001 : 1}.get)
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


    def decode_tags(self, body, offset, bytes_of, _unpack, want=lambda x:True):
        "Takes an IFD (body:offset), func to fetch bytes from wherever the offsets are releative to"
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

