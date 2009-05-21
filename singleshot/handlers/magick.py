import os
import sys
import re
import struct
import shutil
import logging
from singleshot.handlers.images import ImageHandlerBase

LOG = logging.getLogger('singleshot.handlers.magick')


class ImageMagickHandler(ImageHandlerBase):
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
