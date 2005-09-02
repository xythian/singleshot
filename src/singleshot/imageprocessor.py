import os
import fnmatch
import sys
import re
import struct
import shutil
import process
import imp


from singleshot.jpeg import JpegHeader, parse_exif_date
from singleshot.storage import FilesystemEntity
from singleshot.properties import *

try:
    import Image
    import ExifTags
except ImportError:
    # no pil, I guess
    pass


#
# Singleshot image processing code
#   Handles all filters including 'resize' and plugin filters/processors
#

#
# For now assume we're only going to use one image processer
#   per Singleshot install and we can decide which one at startup
#

class ImageProcessor(object):
    def __init__(self, store):
        self.store = store
        self.config = store.config

    def handles(self, ext, fspath):
        return ext.lower() == '.jpg'

    def load_exif(self, fspath):
        file=open(fspath, 'rb')
        try:
            data = EXIF.process_file(file)
        except:
            # file unreadable
            data = {}
        file.close()
        return data         

    def find_publish_time(self, header, img):
        t = 0.0
        for search in ('DateTimeDigitized', 'DateTimeOriginal', 'DateCreated'):
            if hasattr(header.xmp, search):
                t = getattr(header.xmp, search)
                break        
        if not t:
            exif = self.load_exif(img.rawimagepath)
            try:
                et = exif['EXIF DateTimeDigitized']
                t = parse_exif_date(et)
            except KeyError:
                pass
        return t

    def load_metadata(self, target, ext, fspath):
        header = JpegHeader(fspath)
        if header.xmp.Headline:
            target.title = header.xmp.Headline
        elif header.itpc.title:
            target.title = header.itpc.title
        target.caption = header.itpc.caption
        target.height = header.height
        target.width = header.width
        target.publish_time = self.find_publish_time(header, target)
        target.keywords = header.xmp.keywords
        return target    

class ImageMagickProcessor(ImageProcessor):
    def execute(self, source=None,
                dest=None,
                size=None,
                sharpen="0.9x80",
                flt=None):
        cmd = 'convert'
        sizespec = '%sx%s' % (size, size)
        args = [cmd, '-size', sizespec, '-scale', sizespec, '-unsharp', sharpen, source, dest]
        
        trace('Running: "%s"', '" "'.join(args))
        p = process.ProcessProxy(cmd=args,
                                 cwd=self.store.image_root,
                                 env=self.config.getInvokeEnvironment(),
                                 stderr=sys.stderr,
                                 stdout=sys.stderr)
        r = p.wait()
        if r != 0 or not os.path.exists(dest):
            trace("ImageProcessor failed for %s -> %s", source, dest)

class PILProcessor(ImageProcessor):
    def load_exif(self, fspath):        
        try:
            data = Image.open(path)._getexif()
        except:
            return {}
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
    
    def execute(self, source=None, dest=None, size=None,sharpen=None, flt=None):
        input = Image.open(source)
        if flt:
            input.thumbnail((size, size), Image.ANTIALIAS)
            flt = self.load_filter(flt)
            flt(size, input)
        else:
            input.thumbnail((size, size), Image.ANTIALIAS)
        input.save(dest, "JPEG")

def create(store):
    try:
        import Image
        import ExifTags
        return PILProcessor(store)    
    except:
        return ImageMagickProcessor(store)
