from singleshot.storage import FilesystemEntity, FileInfo
import mimetypes
from pkg_resources import iter_entry_points

def load_handlers():
    actions = {}
    for act in iter_entry_points("singleshot.handlers"):
        actions[act.name] = act.load()
    return actions

def load_readers():
    actions = {}
    for act in iter_entry_points("singleshot.readers"):
        actions[act.name] = act.load()
    return actions

class Handler(object):
    """Sketches out interface for a handler.  A handler has to define:
          method to load metadata for an item (at least height/width)
          method to generate a JPEG view of an item in a given size
          (future) async method to prepare an item for viewing (e.g. transcode, raw conversion)
          method to take an item instance and generate HTML to view it"""

    def __init__(self, store=None):
        self.store = store
        self.config = store.config

    def generate(self, source=None, dest=None, size=None):
        "Generate JPEG thumbnail from source to dest in size."

    def view_html(self, item=None):
        "Generate view HTML for an item which can be handled by this handler."

    def load_metadata(self, target=None, fileinfo=None):
        "Load metadata for fileinfo onto target, which will at least include height and width."

    def url_handlers(self):
        "Return URL handlers related to this handler (image resizers, support data, etc)"
        return ()


class ImageHandlerBase(Handler):
    def __init__(self, store=None):
        super(ImageHandlerBase, self).__init__(store=store)
        
    def view_html(self, item=None):
        print '***** hodor'
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
        

class MetadataManager(object):
    def __init__(self, store=None, handlers=None):
        self.handlers = handlers
    
    def get(self, fileinfo):
        ct, ce = mimetypes.guess_type(fileinfo.basename)
        val = self.handlers.get(ct) if ct else None
        return val if val else self.handlers.get(fileinfo.extension.lower())

class HandlerManager(Handler):
    def __init__(self, store=None, handlers=None):
        super(HandlerManager, self).__init__(store=store)
        self.handlers = dict((key, val(store=store)) for key, val in handlers.items())

    def handles(self, fileinfo):
        return self.get(fileinfo) is not None

    def get(self, fileinfo):
        ct, ce = mimetypes.guess_type(fileinfo.basename)
        val = self.handlers.get(ct) if ct else None
        return val if val else self.handlers.get(fileinfo.extension.lower())

    def generate(self, source=None, dest=None, size=None):
        return self.get(FileInfo(source)).generate(source=source, dest=dest, size=size)

    def view_html(self, item=None):
        return self.get(FileInfo(item.rawimagepath)).view_html(item=item)

    def load_metadata(self, target=None, fileinfo=None):
        return self.get(fileinfo).load_metadata(target=target, fileinfo=fileinfo)

    def url_handlers(self):
        return chain(*list(t.url_handlers() for t in self.handlers.values()))
