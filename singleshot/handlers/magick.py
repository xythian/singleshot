import os
import fnmatch
import sys
import re
import struct
import shutil
import imp
import logging

LOG = logging.getLogger('singleshot.handlers.magick')
from singleshot.handlers import ImageHandlerBase

class ImageMagickProcessor(ImageHandlerBase):
    def generate(self, source=None, dest=None, size=None, sharpen="0.9x80"):
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
