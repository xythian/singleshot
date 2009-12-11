from singleshot.handlers import Handler
from StringIO import StringIO
import Image, ImageDraw
from paste.fileapp import FileApp, DataApp

def create_404_image():
    msg = Image.new("RGB", (100, 20), (0, 0, 0))
    draw = ImageDraw.Draw(msg)
    draw.text((5, 5), "404 Not found", fill=(255, 255, 255))
    del draw
    f = StringIO()
    msg.save(f, "JPEG")
    del msg
    app = DataApp(content=f.getvalue(), content_type='image/jpeg')
    app.cache_control(public=True, max_age=86400*36500)
    return app

IMAGE_404 = create_404_image()

def image_handler(request):
    path, size = request.urlmatch.group('path', 'size')
    if not size:
        size = '1200'
    size = int(size)
    image = request.store.load_view(path)
    if not image or not size:
        return request.wsgi_pass(IMAGE_404)
    serveimage = image
    path = image.rawimagepath
    if image.width > size or image.height > size:
        serveimage = image.sizes[size]
        serveimage.ensure()
        path = serveimage.path
    serveimage = image.sizes[size]
    serveimage.ensure()
    path = serveimage.path
    return request.wsgi_pass(FileApp(path))

class ImageCreationFailedException(Exception):
    pass

class ImageHandlerBase(Handler):
    def __init__(self, store=None):
        super(ImageHandlerBase, self).__init__(store=store)
        
    def view_html(self, item=None):
        sv = item.sizes['view']        
        return '<img src="%s" height="%s" width="%s" class="thumbnail" border="0">' % (sv.href, str(sv.height), str(sv.width))

    def load_metadata(self, target=None, fileinfo=None):
        hdr = self.store.metareader.get(fileinfo)
        if not hdr:
            return
        header = hdr(fileinfo.path)
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

    def url_handlers(self):
        return (r'(?P<path>.+?)(-(?P<size>[0-9]+))?\.jpg', image_handler)
    
        
