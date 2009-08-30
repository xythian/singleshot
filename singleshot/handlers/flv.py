
#
# Flash Video stuff
#

# thank you http://www.adobe.com/devnet/flv/pdf/video_file_format_spec_v9.pdf

from struct import unpack, calcsize
from datetime import datetime
from pytz import utc
from singleshot.properties import PackedRecord
import tempfile
import shutil
import os
import subprocess
from singleshot.handlers import Handler, HandlerManager
from paste.fileapp import FileApp
import logging
LOG = logging.getLogger("singleshot.handlers.flv")

def video_handler(request):
    path = request.urlmatch.group('path')
    image = request.store.load_view(path)
    path = image.rawimagepath
    return request.wsgi_pass(FileApp(path))
    
class FLVHandler(Handler):
    def __init__(self, store=None):
        super(FLVHandler, self).__init__(store=store)
        
    def load_metadata(self, target, fileinfo):
        header = FLVHeader(fileinfo.path)
        target.height = int(header.height)
        target.width = int(header.width)
        target.duration = header.duration
        #target.audio_data_rate = header.audiodatarate
        #target.video_data_rate = header.videodatarate
        #target.framerate = header.framerate

    def generate(self, source=None, dest=None, size=None):
        tmpdir = tempfile.mkdtemp()
        #args = ['mplayer', '-nosound', '-really-quiet', '-quiet', '-vo', 'jpeg:outdir=%s' % tmpdir, '-ss', '00:00:03', '-frames', '1', source]
        args = ['ffmpeg', '-i', source, '-an', '-r', '1', '-ss', '00:00:03', '-vframes', '1', '-y', os.path.join(tmpdir, '%d.jpg')]
        proc = subprocess.Popen(args, stdin=None, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=self.config.getInvokeEnvironment())
        data = proc.stdout.read()
        #LOG.warn("mplayer invocation: %s" % data)
        r = proc.wait()
        #jpg = os.path.join(tmpdir, '00000001.jpg')
        jpg = os.path.join(tmpdir, '1.jpg')
        if r != 0 or not os.path.exists(jpg):
            LOG.debug("ImageProcessor failed for %s -> %s", source, dest)
        else:
            self.store.handler.generate(source=jpg, dest=dest, size=size)
            #shutil.move(jpg, dest)
            os.remove(jpg)
            os.rmdir(tmpdir)

    def view_html(self, item=None):
        return """<div id="videocontent"></div>
<script>
flashembed("videocontent", {src : "%(player)s",
                            width : %(width)d, height : %(height)d},
                           {config : {autoPlay : false, autoBuffering : true, initialScale : 'scale',
                            videoFile : "%(href)s"}});
</script>""" % {'player' : self.store.full_href('/static/FlowPlayerLight.swf'),
                'height' : item.height,
                'width' : item.width,
                'href' : self.store.full_href(item.path + '.flv')}
        

    def url_handlers(self):
        return (r'(?P<path>.+?)\.flv', video_handler)
        

class FormatException(Exception):
    pass

class Readable(object):
    @classmethod
    def consume(cls, f):
        return cls(_data=f.read(cls._length))

class FlashVideoHeader(PackedRecord, Readable):
    __fields__ = ["version", "typeFlags", "dataOffset"]
    _format = '>BBI'

def read3byte(v, offset):
    a, b, c = unpack('3B', v[offset:offset+3])
    return (a << 16) + (b << 8) + c

class TagType(object):
    def __init__(self, typ=None, size=None, timestamp=None, streamID=None):
        self.type = typ
        self.size = size
        self.timestamp = timestamp
        self.streamID = streamID
        
    def consume(self, f):
        # skip data
        f.seek(self.size, 1)

class ScriptDataTag(TagType):
    unknown = False
    def consume(self, f):
        r = ScriptDataReader(f)
        t = f.tell()
        self.name = r.read()
        self.data = r.read()
        f.seek(t + self.size, 0)


# we can't do anything with audio or video tags anyway

class UnknownTag(TagType):
    unknown = True

TAG_TYPES = {
#    8 : AudioTag,
#    9 : VideoTag,
    18 : ScriptDataTag
}    
    

def reader(fmt):
    size = calcsize(fmt)
    def read(self):
        return unpack(fmt, self.f.read(size))[0]
    return read

def reader_u(fmt, unpacker):
    size = calcsize(fmt)
    def _read(self):
        return unpacker(*unpack(fmt, self.f.read(size)))
    return _read
    

class ScriptDataReader(object):
    def __init__(self, f):
        self.f = f
        self.dispatch = {
            0: self.readDouble,
            1: self.readBoolean,
            2: self.readString,
            3: self.readObject,
            8: self.readMixedArray,
           10: self.readArray,
           11: self.readDate
        }
        

    readint = reader('>I')
    readshort = reader('>H')
    readbyte = reader('B')
    read24bit = reader_u('3B', lambda b1, b2, b3: (b1 << 16) + (b2 << 8) + b3)
    readDouble = reader('>d')

    def read(self, dataType=None):
        if dataType is None:
            dataType = self.readbyte()
        return self.dispatch[dataType]()

    def readBoolean(self):
        return self.readbyte() == 1

    def readString(self):
        size = self.readshort()
        val = self.f.read(size)
        return val

    def readObject(self):
        result = {}
        while True:
            key = self.readString()
            dataType = self.readbyte()
            if not key and dataType == 9:
                break
            result[key] = self.read(dataType=dataType)
        return result

    def readMixedArray(self):
        size = self.readint()
        result = {}
        while True:
            key = self.readString()
            dataType = self.readbyte()
            if not key and dataType == 9:
                break
            result[key] = self.read(dataType=dataType)
        return result

    def readArray(self):
        size = self.readint()
        result = []
        for i in range(size):
            result.append(self.read())
        return result

    def readDate(self):
        ts, offset = self.readDouble(), self.readshort()
        return datetime.fromtimestamp(ts / 1000.0).replace(tzinfo=utc)

    def readtag(self):
        tid = self.readbyte()
        typ = TAG_TYPES.get(tid, UnknownTag)
        size = self.read24bit()
        ts  = self.read24bit()
        ts_extended = self.readbyte()
        timestamp = (ts_extended << 24) + ts
        streamID = self.read24bit()
        return typ(typ=tid, size=size, timestamp=timestamp, streamID=streamID)

    def readtags(self):
        while True:
            previous_length = self.f.read(4)
            if not previous_length:
                return
            tag = self.readtag()
            tag.consume(self.f)
            if not tag.unknown:
                yield tag


    def readmetadata(self):
        t = iter(self.readtags())
        return t.next()

class FLVHeader(object):
    "Read .flv metadata"

    def __init__(self, path):
        self.load(path)

    def load(self, path):
        f = open(path, 'rb')
        if f.read(3) != 'FLV':
            raise FormatException("Not an FLV file: %s" % path)
        self.header = FlashVideoHeader.consume(f)
        f.seek(self.header.dataOffset, 0)
        f.seek(self.header.dataOffset, 0)
        r = ScriptDataReader(f)
        # hacky
        data = r.readmetadata()
        self.__dict__.update(data.data)

if __name__ == '__main__':
    import sys
    from pprint import pprint
    if len(sys.argv) == 1:
        print 'Usage: %s filename [filename]...' % sys.argv[0]
        print 'Where filename is a .flv file'
        print 'eg. %s myfile.flv' % sys.argv[0]
    for fn in sys.argv[1:]:
        x = FLVHeader(fn)
        pprint(x.__dict__)
