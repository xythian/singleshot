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

HAVE_PIL = False
try:
    import Image
    import ExifTags
    import ImageEnhance    
    HAVE_PIL = True
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

    def handles(self, fileinfo):
        return fileinfo.isa('.jpg')

    def load_exif(self, fileinfo):
        file=open(fileinfo.path, 'rb')
        try:
            data = EXIF.process_file(file)
        except:
            # file unreadable
            data = {}
        file.close()
        return data         


    def load_metadata(self, target, fileinfo):
        header = JpegHeader(fileinfo.path)
        if header.iptc.title:
            target.title = header.iptc.title
        target.caption = header.iptc.caption
        target.capture_time = header.exposure.capture_time
        target.camera_model = header.exposure.camera_model
        target.camera_mfg = header.exposure.camera_mfg
        if header.exposure.duration:
            target.exposure_duration = repr(header.exposure.duration)
        if header.exposure.aperture:
            target.exposure_aperture = 'f/' +header.exposure.aperture.floatformat()
        target.exposure_focal = header.exposure.focal
        target.exposure_iso = header.exposure.iso
        target.height = header.height
        target.width = header.width
        target.publish_time = header.exposure.capture_time
        if header.iptc.keywords:
            target.keywords = header.iptc.keywords
        return target    

class ImageMagickProcessor(ImageProcessor):
    def execute(self, source=None,
                dest=None,
                size=None,
                sharpen="0.9x80"):
        cmd = 'convert'
        size = size.size
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
    def load_exif(self, fileinfo):        
        try:
            data = Image.open(fileinfo.path)._getexif()
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
    
    def execute(self, source=None, dest=None, size=None):
        height = size.height
        width = size.width    
        image = Image.open(source)
        size = size.size
        if size**2 < 40000:
            image.thumbnail((size, size), Image.ANTIALIAS)
        else:
            image = image.resize((width, height), Image.ANTIALIAS)
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(1.6)
        image.save(dest, "JPEG")

def create(store):
#    return ImageMagickProcessor(store)
    try:
        import Image
        import ExifTags
        return PILProcessor(store)    
    except:
        return ImageMagickProcessor(store)
