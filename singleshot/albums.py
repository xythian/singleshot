# $Id$

from __future__ import nested_scopes
import os
import fnmatch
import sys
import Cheetah.Template
import re
import struct
import shutil
import tempfile
import process
from jpeg import JpegImage
from storage import FilesystemEntity
from properties import *
from ssconfig import CONFIG, STORE, ConfiguredEntity
import imageprocessor

from sets import Set


IMAGESIZER = imageprocessor.select_processor()

def get_path_info():
    v = os.environ['PATH_INFO']
    return v[1:]

def calculate_box(size, width, height):
    if height > width:
        h2 = size
        w2 = int(float(size) * (float(width) / float(height)))
    else:
        w2 = size
        h2 = int(float(size) * (float(height) / float(width)))
    if h2 < height or w2 < width:
        return w2, h2
    else:
        return width, height


# class hierarchy:
#
# FileSystemEntity
# |
# +-ConfiguredEntity
# | |
# | +-SingleshotConfig
# |
# +-Item
# | |
# | +-AlbumItem (also inherits from ConfiguredEntity)
# | |
# | +-ImageItem (also inherits from JpegImage)
# |
# +-JpegImage
# |
# +-ImageSize

class ItemLoader(object):
    def __init__(self):
        self.__cache = {}

    def _create_item(self, path):
        name = os.path.basename(path).lower()
        item = None
        if CONFIG.ignore_path(path):
            return item
        elif os.path.isdir(path):
            item = AlbumItem(path)
        elif os.path.isfile(path) and fnmatch.fnmatch(name, '*.jpg'):
            item = ImageItem(path)
        elif os.path.exists(path + '.jpg'):
            return create_item(path + '.jpg')
        elif os.path.exists(path + '.JPG'):
            return create_item(path + '.JPG')
        return item

    def get_item(self, path):
        path = os.path.abspath(path)
        try:
            return self.__cache[path]
        except KeyError:
            v = self._create_item(path)
            self.__cache[path] = v
            return v

create_item = ItemLoader().get_item

class ItemBase(object):
    """Defines the Item protocol"""

    def _get_hasNext(self):
        return bool(self.nextItem)
    
    def _get_hasPrev(self):
        return bool(self.prevItem)

    def _get_name(self):
        return ''

    def _load_image(self):
        return None

    def _get_title(self):
        return self.name

    parent = virtual_demand_property('parent')
    album = parent

    title = virtual_readonly_property('title')
    hasNext = virtual_readonly_property('hasNext')
    hasPrev = virtual_readonly_property('hasPrev')
    nextItem = virtual_demand_property('nextItem')
    prevItem = virtual_demand_property('prevItem')
    image = virtual_demand_property('image')    
    href = virtual_readonly_property('href')
    name = virtual_readonly_property('name')

    cssclassname = 'item'
    viewtemplatekey = 'item'

class Item(ItemBase, FilesystemEntity):
    """
    An Item is an entity in an album.
    """

    def _load_parent(self):
        if not STORE.within_root(self.dirname):
            return None
        else:
            return create_item(self.dirname);
    
    def _get_itempath(self):
        return self.path[len(STORE.image_root):]

    def _get_href(self):
        v = CONFIG.url_prefix + self.itempath.replace('\\', '/')[1:]
        if os.path.isdir(self.path) and v[-1] != '/':
            v += '/'
        return v

    def _get_viewpath(self):
        trace("view_root: %s", STORE.view_root)
        return os.path.join(STORE.view_root, self.itempath[1:])
    
    def _load_nextItem(self):
        if self.album:
            return self.album.items.nextItemFor(self)
        else:
            return None

    def _load_prevItem(self):
        if self.album:
            return self.album.items.prevItemFor(self)
        else:
            return None

    itempath = virtual_readonly_property('itempath')
    viewpath = property(_get_viewpath)


class ImageSize(FilesystemEntity):
    """
    An ImageSize is an ImageItem rendered at a particular size.
    It may or may not represent something already in the cache.
    """
    def __init__(self,
                 image=None,
                 size=None,
                 height=None,
                 width=None,
                 flt=None):        
        self.image = image
        self.height = height
        self.width = width
        self.size = size
        if flt:
            filename = '__filter_%s_%s-%s%s' % (flt,
                                                image.filename,
                                                size,
                                                image.extension)
        else:
            filename = '%s-%s%s' % (image.filename,
                                    size,
                                    image.extension)
        self.filter = flt
        self.href = image.album.href + filename
        path = os.path.join(image.album.viewpath, filename) 
        super(ImageSize, self).__init__(path)

    def _get_uptodate(self):
        if not self.exists:
            return False
        elif self.image.mtime > self.mtime:
            return False
        else:
            return True

    uptodate = property(_get_uptodate)

    def filtered(self, flt=None):
        if not flt:
            return self
        return ImageSize(self.image, self.size, self.height, self.width, flt=flt)
    
    def ensure(self):
        if self.uptodate:
            return        
        self.generate()

    def generate(self):
        self.image.album.ensure_viewpath()
        IMAGESIZER.execute(source=self.image.path,
                           dest=self.path,
                           size=self.size,
                           flt=self.filter)                           

    def expire(self):
        if self.exists:    
            os.remove(self.path)

class ImageSizes(dict):
    def __init__(self, image):
        self.__image = image
        w, h = image.width, image.height
        available = []
        for box in self.availableSizes:
            szname = self.sizeNames[box]
            width, height = calculate_box(box, w, h)
            sz = ImageSize(image=image,
                           size=box,
                           width=width,
                           height=height)
            if sz.exists and not sz.uptodate:
                sz.expire()
            setattr(self, '%sSize' % szname, sz)
            self[box] = sz
            self[szname] = sz
            setattr(self, 'has%sSize' % szname, True)
            
    def _get_files(self):
        # get files for all of the
        # existing sizes for this image
        pattern = r'%s-([1-9][0-9]+)%s' % (re.escape(self.__image.filename),
                                           re.escape(self.__image.extension))
        rxp = re.compile(pattern)
        filenames = filter(rxp.match, os.listdir(self.__image.album.viewpath))
        paths = map(os.path.join,
                    [self.__image.album.viewpath] * len(filenames),
                    filenames)
        return paths

    def _get_availableSizes(self):
        return CONFIG.availableSizes

    def _get_sizeNames(self):
        return CONFIG.sizeNames

    availableSizes = property(_get_availableSizes)
    sizeNames = property(_get_sizeNames)
    files = property(_get_files)
                    

class ImageItem(JpegImage, Item):
    """
    An ImageItem is an image in an album.
    """
    
    cssclassname = 'image'
    viewtemplatekey = 'view'

    def _get_name(self):
        "Override Item._get_name"
        return self.filename

    def _load_sizes(self):
        return ImageSizes(self)

    def _get_href(self):
        return self.album.href + self.filename + '.html'

    def _load_image(self):
        return self

    href = property(_get_href)
    sizes = demand_property('sizes', _load_sizes)

    def expire_sizes(self):
       map(os.remove, self.sizes.files) 

    def filtered(self, flt=None):
        if not flt:
            return self
        if self.height > self.width:
            size = self.height
        else:
            size = self.width
        return ImageSize(self, size, self.height, self.width, flt=flt)

    dirty = expire_sizes


class OrderedItems(list):
    def __init__(self, items, *orders):
        super(OrderedItems, self).__init__(items)
        comparator = compose(*orders)
        self.sort(comparator)

    def offsetItemFor(self, item, offset):
        try:
            idx = self.index(item)
            idx += offset
            if not 0 <= idx < len(self):
                return None
            else:
                return self[idx]
        except ValueError:
            return None

    def nextItemFor(self, item):
        return self.offsetItemFor(item, 1)

    def prevItemFor(self, item):
        return self.offsetItemFor(item, -1)

    def resolveOrder(self, order):
        if callable(order):
            return order
        else:
            return ORDERS[order]

    def orderedBy(self, *orders):
        orders = tuple(map(self.resolveOrder, orders))
        return OrderedItems(self, *orders)
    
class AlbumItem(ConfiguredEntity, Item):
    """
    An AlbumItem represents an Album.
    """
    
    config_filename = '_album.cfg'
    sections = ('album', 'templates')
    cssclassname = 'album'
    viewtemplatekey = 'album'
    
    def __init__(self, path):
        super(AlbumItem, self).__init__(path)

    def _get_name(self):
        "Override Item._get_name"
        return self.basename + '/'
    
    def _load_items(self):        
        items = []
        for name in os.listdir(self.path):
            path = os.path.join(self.path, name)
            item = create_item(path)
            if item:
                items.append(item)
        orders = self.order.split(',')
        orders = map(ORDERS.get, orders)
        return OrderedItems(items, *orders)        

    def get(self, imagename):
        for item in self.items:
            if item.name == imagename:
                return item

    def _load_image(self):
        trace('_load_image: %s', self.name)
        # pretend we look in a config for this
        # for now, pick thing with a thumbnail
        if self.highlightimagename:
            return self.get(self.highlightimagename)
        else:
            dir = None
            image = None
            for item in self.items:
                if item.image:
                    if item.isdir:
                        dir = dir or item.image
                    else:
                        image = image or item.image
            return image or dir

    def _load_config(self):
        self.defaults = { 'album': { 'title' : self.basename,
                                     'highlightimage' : '',
                                     'order' : 'title,mtime',
                                   },
                          'templates': {
                                         'view' : CONFIG.viewTemplate,
                                         'album' : CONFIG.albumTemplate,
                                         'albumedit' : CONFIG.albumEditTemplate,
                                       }
                        }
        return super(AlbumItem, self)._load_config()

    def update_comment(self, comment):
        self.title = comment

    title = writable_config_property('title', 'album')
    highlightimagename = writable_config_property('highlightimage', 'album')
    order = config_property('order', 'album')

    items = demand_property('items', wrap_printexc(_load_items))

    def ensure_viewpath(self):
        if os.path.exists(self.viewpath):
            return
        try:
            os.makedirs(self.viewpath)
        except os.error:
           print >>sys.stderr, "ensure_viewpath ERROR: Unable to create directory %s: is view/ writable?" % (self.viewpath,)
           sys.exit(1)
        
    def expire_sizes(self):
        for item in self.items:
            item.expire_sizes()

class Crumb(object):
    def __init__(self, link=None, item=None):
        self.link = link
        self.item = item
        self.title = item.title
        
class Breadcrumbs(object):
    SPLIT_RE = re.compile(r'[/\\]')
    
    def __init__(self, fsroot, urlprefix, path):
        chunks = Breadcrumbs.SPLIT_RE.split(path)
        self.crumbs = []
        path = urlprefix
        fspath = fsroot        
        self.add_crumb(fspath, path)
        for chunk in chunks:
            path += '%s/' % chunk
            fspath = os.path.join(fspath, chunk)
            if chunk:
                 self.add_crumb(fspath, path)

    def add_crumb(self, fspath, urlpath):
        item = create_item(fspath)
        if not item:
            return
        crumb = Crumb(item=item, link=urlpath)
        self.crumbs.append(crumb)

    def _get_parents(self):
        return self.crumbs[:-1]
    
    def _get_current(self):
        return self.crumbs[-1]
    
    parents = property(_get_parents)
    current = property(_get_current)

def get_exif_date(img):
    try:
        return img.get_exif('Image DateTime')
    except AttributeError:
        return None


def reverse(f):
    def _reverse(x, y):
        return -f(x, y)
    return _reverse

def compose(*orders):
    def _compare(x, y):
        for order in orders:
            r = order(x, y)
            if r != 0:
                return r
        return 0
    return _compare

ORDERS = {'title' : lambda x,y:cmp(x.title, y.title),
          'dir'   : lambda x,y:cmp(x.isdir, y.isdir),
          'mtime' : lambda x,y:cmp(x.mtime, y.mtime),
          'exifdate' : lambda x,y:cmp(get_exif_date(x), get_exif_date(y)),
          'name'  : lambda x,y:cmp(x.name, y.name),
          'href'  : lambda x,y:cmp(x.href, y.href)}

for key, item in ORDERS.items():
    ORDERS['-' + key] = reverse(item)
