from singleshot.storage import FilesystemEntity, FileInfo
import mimetypes
from pkg_resources import iter_entry_points
from shotweb import by2
from itertools import chain

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
        handlers = list(by2(chain(*(t.url_handlers() for t in self.handlers.values()))))
        seen = set()
        for h, v in handlers:
            if h not in seen:
                seen.add(h)
                yield h
                yield v
