import os
import fnmatch
import sys
import re
import struct
import shutil
import tempfile
import process
from jpeg import JpegImage
from storage import FilesystemEntity
from properties import *
from ssconfig import CONFIG, STORE, ConfiguredEntity
import imp


#
# Singleshot image processing code
#   Handles all filters including 'resize' and plugin filters/processors
#

#
# For now assume we're only going to use one image processer
#   per Singleshot install and we can decide which one at startup
#

class ImageMagickSizer(object):
    def execute(self, source=None,
                dest=None,
                size=None,
                sharpen="0.9x80",
                flt=None):
        cmd = os.path.join(CONFIG.imagemagickPath, 'convert')
        sizespec = '%sx%s' % (size, size)
        args = [cmd, '-size', sizespec, '-scale', sizespec, '-unsharp', sharpen, source, dest]
        
        trace('Running: "%s"', '" "'.join(args))
        p = process.ProcessProxy(cmd=args,
                                 cwd=STORE.image_root,
                                 env=CONFIG.getInvokeEnvironment(),
                                 stderr=sys.stderr,
                                 stdout=sys.stderr)
        r = p.wait()
        if r != 0 or not os.path.exists(dest):
            trace("ImageSizer failed for %s -> %s", source, dest)

    def list_filters(self):
        return ()

class PILSizer(object):
    def __init__(self):
        self.filterpath = os.path.join(STORE.ss_root, 'filters')
        self.__filters = {} # self._load_filters()
        
    def _load_filters(self):
        filters = {}
        if os.path.exists(self.filterpath):
            for name in os.listdir(self.filterpath):
                if name.endswith('.py'):
                    flt = self._load_filter(name, os.path.join(self.filterpath, name)).pil_filter
                    filters[name] = flt
        return filters

    def _load_filter(self, name, path):
        f = open(path, 'U')
        try:
            m = imp.load_source(name, path, f)
            return m.pil_filter
        finally:
            f.close()

    def list_filters(self):
        return self.__filters.keys()
    
    def load_filter(self, name):
        return self.__filters[name]

    def execute(self, source=None, dest=None, size=None,sharpen=None, flt=None):
        import Image

        input = Image.open(source)
        if flt:
            input.thumbnail((size, size), Image.ANTIALIAS)
            flt = self.load_filter(flt)
            flt(size, input)
        else:
            input.thumbnail((size, size), Image.ANTIALIAS)
        input.save(dest, "JPEG")

def select_processor():
    try:
        import Image
        return PILSizer()    
    except:
        return ImageMagickSizer()
