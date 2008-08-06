import os
import fnmatch
import sys
import re
import struct
import shutil
import imp
import logging

LOG = logging.getLogger('singleshot')

from singleshot.jpeg import JpegHeader
from singleshot.storage import FilesystemEntity, FileInfo

try:
    import Image
    import ImageEnhance    
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

    extensions = ('.jpg',)

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
        if header.exposure.focal:
            target.exposure_focal = header.exposure.focal.floatformat()
        target.exposure_iso = header.exposure.iso
        target.height = header.height
        target.width = header.width
        if header.iptc.datetime:
            target.publish_time = header.iptc.datetime
        elif  header.exposure.capture_time:
            target.publish_time = header.exposure.capture_time
        target.keywords = ()
        if header.iptc.keywords:
            target.keywords = header.iptc.keywords
        return target    

class ImageMagickProcessor(ImageProcessor):
    def execute(self, source=None,
                dest=None,
                size=None,
                sharpen="0.9x80"):
        LOG.info('IM Generating image %s -> %s (%dx%d)',
                 source,
                 dest,
                 size.width,
                 size.height)
        cmd = 'convert'
        size = size.size
        sizespec = '%sx%s' % (size, size)
        args = [cmd, '-size', sizespec, '-scale', sizespec, '-unsharp', sharpen, source, dest]
        LOG.debug('ImageMagickProcessor: "%s"', '" "'.join(args))
        r = os.spawnvpe(os.P_WAIT, cmd, args, self.config.getInvokeEnvironment())
        if r != 0 or not os.path.exists(dest):
            LOG.debug("ImageProcessor failed for %s -> %s", source, dest)

class PILProcessor(ImageProcessor):
    def handles(self, fileinfo):
        return fileinfo.isa('.jpg', '.png', '.gif')

    extensions = ('.jpg', '.png', '.gif')

    def load_metadata(self, target, fileinfo):
        if fileinfo.isa('.jpg'):
            super(PILProcessor, self).load_metadata(target, fileinfo)
            return
        img = Image.open(fileinfo.path)
        target.width, target.height = img.size

    def execute(self, source=None, dest=None, size=None):
        LOG.info('PIL Generating image %s -> %s (%dx%d)',
                  source,
                  dest,
                  size.width,
                  size.height)
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

class CompositeProcesser(object):
    def __init__(self, processors):
        self.processors = processors
        mapping = {}
        for processor in processors:
            for ext in processor.extensions:
                if not mapping.has_key(ext):
                    mapping[ext] = processor
        self.mapping = mapping
        self.extensions = mapping.keys()
            
    def handles(self, fileinfo):
        return fileinfo.isa(*self.extensions)

    def _for(self, fileinfo):
        return self.mapping[fileinfo.extension.lower()]

    def load_metadata(self, target, fileinfo):
        self._for(fileinfo).load_metadata(target,
                                          fileinfo)

    def execute(self, *args, **kwargs):
        fileinfo = FileInfo(kwargs['source'])
        self._for(fileinfo).execute(*args, **kwargs)

def create(store):
    im = store.config.config.getboolean('images', 'imagemagick')
    pil = store.config.config.getboolean('images', 'pil')
    processors = []
    if im:
        processors.append(ImageMagickProcessor(store))
    if pil:
        try:
            import Image
            processors.append(PILProcessor(store))
        except ImportError:
            pass
    from singleshot.flv import FLVProcessor, AVIProcessor
    processors.append(FLVProcessor(store))
    # we don't really know what to do with these
    # also we need imageprocessors to be involved in the DISPLAY (unlike the hack in views.py now)
#    processors.append(AVIProcessor(store))
    if not processors:
        LOG.error('No available image processors')
        return CompositeProcesser([])
    elif len(processors) == 1:
        return processors[0]
    else:
        return CompositeProcesser(processors)
