import logging
from singleshot.handlers import ImageHandlerBase
import Image
import ImageEnhance

LOG = logging.getLogger('singleshot.handlers.pil')

class PILProcessor(ImageHandlerBase):
    def generate(self, source=None, dest=None, size=None):
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
