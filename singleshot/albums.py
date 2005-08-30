# $Id$

from __future__ import nested_scopes
import os
import fnmatch
import sys
import re
import struct
import shutil
import tempfile
import process
import time
import cPickle
from datetime import datetime
from jpeg import JpegImage, parse_exif_date
from storage import FilesystemEntity
from properties import *
from ssconfig import CONFIG, STORE, ConfiguredEntity
from taltemplates import ViewableObject, ViewableContainerObject
from cStringIO import StringIO

import imageprocessor

from taltemplates import PathFunctionVariable, CachedFuncResult

from sets import Set

IMAGESIZER = imageprocessor.select_processor()

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'November', 'December']

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
# +-Item (also inherits from ItemBase)
# | |
# | +-AlbumItem (also inherits from ConfiguredEntity)
# | |
# | +-ImageItem (also inherits from JpegImage)
# |
# +-JpegImage
# |
# +-ImageSize



class ItemBase(ViewableObject):
    """Defines the Item protocol"""

    def _get_name(self):
        return ''

    def _load_image(self):
        return None

    def _get_title(self):
        return self.name

    def _get_parents(self):
        p = self.parent
        while p:
            yield p
            p = p.parent

    caption = ''
    parent = virtual_demand_property('parent')
    album = parent

    title = virtual_readonly_property('title')
    parents = virtual_readonly_property('parents')
    image = virtual_demand_property('image')    
    href = virtual_readonly_property('href')
    name = virtual_readonly_property('name')

    cssclassname = 'item'

    def create_context(self):
        context = super(ItemBase, self).create_context()
        context.addGlobal("item", self)
        def pathloader(path):
            return create_item('/' + path)
        def recentimages(path):
            count = int(path)
            return [create_item(path) for path in ITEMLOADER.itemData.recent_images(count)]
        context.addGlobal("title", self.title)
        context.addGlobal("data", PathFunctionVariable(pathloader))
        context.addGlobal("recentimages", PathFunctionVariable(recentimages))
        t = recentimages(1)[0]
        context.addGlobal("lastimage", t)
        context.addGlobal("ssuri",
                          PathFunctionVariable(lambda x:CONFIG.ssuri + '/' + x))
        context.addGlobal("ssroot",
                          PathFunctionVariable(lambda x:CONFIG.url_prefix +  x))
        return context

class Item(ItemBase, FilesystemEntity):
    """
    An Item is an entity in an album represented by a file or
       directory on the filesystem
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

    def filters(self):
        try:
            return self.__filters
        except AttributeError:
            fltd = {}
            for flt in IMAGESIZER.list_filters():
                fltd[flt] = self.filtered(flt=flt)
            self.__filters = fltd
            return self.__filters
        
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
    viewname = 'view'

    def load_predicate(path):
        lcase = path.lower()
        return lcase.endswith('.jpg')
    load_predicate = staticmethod(load_predicate)

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

    def _get_publish_time(self):
        t = 0.0
        for search in ('DateTimeDigitized', 'DateTimeOriginal', 'DateCreated'):
            if hasattr(self.xmp, search):
                t = getattr(self.xmp, search)
                break        
        if not t:
            try:
                et = self._exif['EXIF DateTimeDigitized']
                t = parse_exif_date(et)
            except KeyError:
                try:            
                    month = int(self.parent.basename)
                    year = int(self.parent.parent.basename)
                    if month > 0 and month < 13:
                        t = time.mktime((year, month, 01, 0, 0, 0, -1, -1, 0))
                except:
                    pass
            if not t:
                t = self.mtime
        return t
                
    publish_time = property(_get_publish_time)

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
    def compose(*orders):
        def _compare(x, y):
            for order in orders:
                r = order(x, y)
                if r != 0:
                    return r
            return 0
        return _compare
    compose = staticmethod(compose)
    
    def __init__(self, items, *orders):
        super(OrderedItems, self).__init__(items)
        comparator = OrderedItems.compose(*orders)
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
            for idx, x in enumerate(self):
                if x.path == item.path:                    
                    break
            idx += offset
            if not 0 <= idx < len(self):
                return None
            else:
                return self[idx]
            
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

class AlbumItem(ConfiguredEntity, Item, ViewableContainerObject):
    """
    An AlbumItem represents an Album.
    """
    
    config_filename = '_album.cfg'
    sections = ('album', 'templates')
    cssclassname = 'album'
    viewname = 'album'

    def load_predicate(path):
        return os.path.isdir(path)

    load_predicate = staticmethod(load_predicate)
    
    def __init__(self, path):
        super(AlbumItem, self).__init__(path)

    def find_template(self, name):
        localname = os.path.join(self.path, name + '.html')
        if os.path.exists(localname):
            return localname
        else:
            return super(AlbumItem, self).find_template(name)

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
                                   }
                        }
        return super(AlbumItem, self)._load_config()

    def update_comment(self, comment):
        self.title = comment


    def _load_title(self):
        title = self.config.get('album', 'title')
        if title != self.basename:
            return title
        try:            
            month = int(self.basename)
            year = int(self.parent.basename)
            if month > 0 and month < 13:
                return '%s %s' % (MONTHS[month-1], self.parent.basename)
        except:
            pass
        return self.basename
            

    title = demand_property('title', _load_title)
    
    highlightimagename = writable_config_property('highlightimage', 'album')
    order = config_property('order', 'album')

    items = demand_property('items', _load_items)

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

#
# Sets and tags
#

class Tag(object):    
    def __init__(self, name):
        self.name = name
        self.count = 0
        self.imagemap = 0L

    def add(self, imageid):
        self.count += 1
        self.imagemap |= 1L << imageid        

class ImageData(object):
    def __init__(self, item):
        self.path = item.path
        self.publish_time = item.publish_time

class ImageYear(object):
    def __init__(self, year):
        self.year = year
        self.months = [0] * 12

    def add(self, month):
        self.months[month-1] += 1

class ItemData(object):
    def __init__(self):
        self._cachepath = os.path.join(STORE.view_root, '.itemcache')
        self._load()

    def _load(self):
        n = time.time()
        cached = 'No'
        if self.has_cache():
            cached = 'Yes'
            self._load_cache()
        else:
            self._load_raw()
            self._save_cache()
        print >>sys.stderr, cached,' Load Time: ',time.time() - n

    def has_cache(self):
        path = self._cachepath
        now = time.time()
        try:
            s = os.stat(path)
            if now > s.st_mtime + 86400:
                return False
            else:
                return True
        except:
            pass
        return False
            
    def _load_cache(self):
        f = open(self._cachepath, 'r')
        try:
            self.tags, self._years, self._imagelist, self._allimages = cPickle.load(f)
        finally:
            f.close()

    def _save_cache(self):
        s = StringIO()
        cPickle.dump((self.tags, self._years, self._imagelist, self._allimages), s,
                     cPickle.HIGHEST_PROTOCOL)
        f = open(self._cachepath, 'w')
        f.write(s.getvalue())
        f.close()

    def prepare_tag(self, tag):
        tag = tag.lower()
        tag = tag.replace(' ', '')
        return tag
    
    def _load_raw(self):
        self.tags = {}
        self._imagelist = []
        self._years = {}
        self._allimages = 0L
        count = 0
        for root, dirs, files in os.walk(STORE.root):
            for dir in dirs:
                path = os.path.join(root, dir)
                item = create_item(path)
                if not item:
                    # don't visit directories that aren't albums
                    dirs.remove(dir)
            for file in files:
                path = os.path.join(root, file)
                item = create_item(path)
                if not item:
                    continue
                self._imagelist.append(ImageData(item))
                imageid = count
                self._allimages |= 1L << imageid
                count += 1
                def record_keywords():
                    def record_keyword(tag):
                        tag = self.prepare_tag(tag)
                        try:
                            self.tags[tag].add(imageid)
                        except KeyError:
                            t = Tag(tag)
                            t.add(imageid)
                            self.tags[tag] = t
                    for tag in item.keywords:
                        record_keyword(tag)
                    pt = item.publish_time
                    d = datetime.fromtimestamp(pt)
                    try:
                        yearrecord = self._years[d.year]
                    except KeyError:
                        yearrecord = ImageYear(d.year)
                        self._years[d.year] = yearrecord
                    yearrecord.add(d.month)
                    record_keyword('publish:%04d-%02d' % (d.year, d.month))
                    record_keyword('publish:%04d' % (d.year))
                    record_keyword('publish:%04d-%02d-%02d' % (d.year, d.month, d.day))
                try:
                    record_keywords()
                except TypeError:
                    pass
                except AttributeError:
                    pass

    def is_in(self, path, tags):
        try:
            idx = self._imagelist(path)
        except ValueError:
            return False
        imgmap, excmap = self._query(tags)
        mask = 1L << idx
        return mask & imgmap and not excmap & mask

    def all_tags(self):
        return self.tags.items()

    def most_tags(self):
        return [(tag.name, tag) for tag in self.tags.values() if tag.count > 3 and not tag.name.startswith('publish:')]

    def _query(self, tags):
        imgmap = self._allimages
        excmap = 0L
        for tag in tags:
            tag = self.prepare_tag(tag)
            try:
                if tag[0] == '!':
                    tag = tag[1:]
                    try:
                        excmap |= self.tags[tag].imagemap
                    except KeyError:
                        pass
                else:
                    imgmap &= self.tags[tag].imagemap
            except KeyError:
                pass
        return imgmap, excmap

        

    def query(self, tags):
        n = time.time()
        imgmap, excmap = self._query(tags)
        result = []
        for idx in xrange(len(self._imagelist)):
            imgmask = 1L << idx
            if imgmap & imgmask and not excmap & imgmask:
                result.append(self._imagelist[idx].path)
        print >>sys.stderr, 'Query time: ',time.time() - n, len(result)
        return result

    def image_years(self):
        return self._years.values()

    def image_year(self, year):
        return self._years[year]

    def early_images(self, count=10):
        imgs = [(item.publish_time, item.path) for item in self._imagelist]
        imgs.sort()
        if count > len(imgs):
            count = len(imgs)
        return [img[1] for img in imgs[:count]]
        

    def recent_images(self, count=10):        
        imgs = [(item.publish_time, item.path) for item in self._imagelist]
        imgs.sort()
        imgs.reverse()
        if count > len(imgs):
            count = len(imgs)
        return [img[1] for img in imgs[:count]]

    def get(self, path):
        return ImagesByTagItem(path)

class SetData(object):
    def __init__(self):
        self._sets = {}

    def add(self, set):
        self._sets[set.path] = set

    def define_sets(self, title, sets):
        def fix_paths(parentpath, set):
            self.add(set)
            if set.children:
                for s in set.children:                    
                    if isinstance(s, SetItem):
                        if parentpath:
                            s.path = parentpath + '/' + s.path
                        fix_paths(s.path, s)        
        root = []
        for set in sets:
            root.append(set)
        rootset = SetItem('', title=title, children=root)
        fix_paths('', rootset)        

    def get(self, path):
        return self._sets.get(path)

class ContextHrefWrapper(object):
    def __init__(self, item, ctx=None, href=None):
        if href:
            self.href = href
        else:
            self.href = item.href + ctx            
        self.__item = item

    def __getattr__(self, v):
        return getattr(self.__item, v)

class RecentItems(ItemBase, ViewableContainerObject):
    viewname = 'recent'

    def __init__(self, count=15):
        self.path = '/recent'
        self.isdir = True
        self.count = count

    caption = ''
    title = 'Recent photos'
    
    def _load_parent(self):
        return create_item(STORE.image_root)

    def _load_items(self):
        return [create_item(path) for path in ITEMLOADER.itemData.recent_images(self.count)]

    items = virtual_demand_property('items')    

class SetItem(ItemBase, ViewableContainerObject):
    cssclassname = 'album'
    viewname = 'album'
    
    def __init__(self, path, tag=None, children=None, title='', caption='', viewname=''):
        self.path = path
        self.isdir = True
        self.caption = caption
        if viewname:
            self.viewname = viewname

        if not title:
            self._title = path.split('/')[-1]
        else:
            self._title = title
        
        self.tag = tag
        self.children = children

    def _load_parent(self):
        if not self.path:
            return create_item(STORE.image_root)
        try:
            idx = self.path.rindex('/')
        except ValueError:
            return ITEMLOADER.setData.get('')
        return ITEMLOADER.setData.get(self.path[:idx])
        
    def _get_title(self):
        return self._title

    def _load_items(self):
        if self.children:
            return self.children
        else:
            items = ITEMLOADER.itemData.query(self.tag.split('/'))
            result = []
            for item in items:
                item = create_item(item)
                if isinstance(item, ImageItem):
                    inref = '/albums/' + self.path
                    result.append(ContextHrefWrapper(item, '?in=' + inref))
                else:
                    result.append(item)
            return OrderedItems(result,
                                ORDERS['-mtime'])

    def _get_href(self):
        return CONFIG.url_prefix + 'albums/' + self.path

    def _load_image(self):
        return self.items[0].image

    items = virtual_demand_property('items')


class ImageTags(ItemBase, ViewableContainerObject):
    viewname = 'keywords'

    def __init__(self):
        self.isdir = False
        self.path = '/keyword'

    def _get_href(self):
        return CONFIG.url_prefix + 'keyword/'

    def _load_parent(self):
        return create_item(STORE.image_root)

    def _get_title(self):
        return 'Keywords'

    def _load_items(self):
        result = list(ITEMLOADER.itemData.most_tags())
        result.sort()
        return [ContextHrefWrapper(tag, href=CONFIG.url_prefix+'keyword/' + name) for name, tag in result]

    items = virtual_demand_property('items')    


class MonthItem(object):
    def __init__(self, year, month, count):
        self.year = year
        self.month = month
        self.title = '%s %s' % (MONTHS[month-1], str(year))
        self.path = '/bydate/%04d/%02d' % (year, month)
        self.href = CONFIG.url_prefix + self.path[1:]
        self.count = count
        

class YearItem(object):
    def __init__(self, yearo):
        self.year = yearo.year
        self.title = str(self.year)
        self.path = '/bydate/%04d' % (self.year,)
        self.href = CONFIG.url_prefix + self.path[1:]
        self.months = []
        total = 0
        for idx, month in enumerate(MONTHS):
            count = yearo.months[idx]
            total += count
            if count > 0:
                self.months.append(MonthItem(yearo.year, idx+1, count))                
        self.months.reverse()
        self.count = total
        
class YearView(ItemBase, ViewableContainerObject):
    viewname = 'bydate'
    
    def __init__(self, year=None):
        if year:
            self.year = year
            self.path = '/bydate/' + str(year)
        else:
            self.year = ''
            self.path = '/bydate'
        self.isdir = True

    def _get_title(self):
        if self.year:
            return str(self.year)
        else:
            return 'Browse by date'
        

    def _get_href(self):
        return CONFIG.url_prefix + self.path[1:]

    def _load_parent(self):
        if self.year:
            return create_item('/bydate')
        else:
            return create_item(STORE.root)
        

    def _load_items(self):
        if self.year:
            items = [(self.year, YearItem(ITEMLOADER.itemData.image_year(self.year) ))]
        else:
            items = [(year.year, YearItem(year)) for year in ITEMLOADER.itemData.image_years()]
        items.sort()
        items.reverse()
        return [m[1] for m in items]

    items = virtual_demand_property('items')

class ImagesByDate(ItemBase, ViewableContainerObject):
    viewname = 'album'

    def __init__(self, year, month):
        self.tag = 'publish:%04d-%02d' % (year, month)
        self.isdir = True
        self.path = '/bydate/%04d/%02d' % (year, month)
        self.year = year
        self.month = month

    def _get_href(self):
        return CONFIG.url_prefix + self.path[1:]

    def _load_parent(self):
        return create_item('/bydate')

    parent = property(_load_parent)

    def _get_parents(self):
        p = self.parent
        while p:
            yield p
            p = p.parent

    parents = property(_get_parents)
            
    def _get_title(self):
        return '%s %s' % (MONTHS[self.month-1], self.year)

    def _load_items(self):
        items = ITEMLOADER.itemData.query(self.tag.split('/'))
        result = []
        for item in items:
            item = create_item(item)
            if isinstance(item, ImageItem):
                inref = self.path
                result.append(ContextHrefWrapper(item, '?in=' + inref))
            else:
                result.append(item)
        return OrderedItems(result,
                            ORDERS['-publishtime'])

    def _load_config(self):
        return create_item(STORE.root).config
    
    config = virtual_demand_property('config')
    items = virtual_demand_property('items')


class ImagesByTagItem(ItemBase, ViewableContainerObject):
    viewname = 'album'
    
    def __init__(self, tag):
        self.tag = tag
        self.isdir = True
        self.path = '/keyword/' + self.tag

    def _get_href(self):
        return CONFIG.url_prefix + self.path[1:]

    def _load_parent(self):
        return create_item('/keyword')

    parent = property(_load_parent)

    def _get_parents(self):
        p = self.parent
        while p:
            yield p
            p = p.parent

    parents = property(_get_parents)
            
    def _get_title(self):
        return self.tag

    def _load_items(self):
        items = ITEMLOADER.itemData.query(self.tag.split('/'))
        result = []
        for item in items:
            item = create_item(item)
            if isinstance(item, ImageItem):
                inref = '/keyword/' + self.tag
                result.append(ContextHrefWrapper(item, '?in=' + inref))
            else:
                result.append(item)
        return OrderedItems(result,
                            ORDERS['-mtime'])

    def _load_config(self):
        return create_item(STORE.root).config
    
    config = virtual_demand_property('config')
    items = virtual_demand_property('items')



def init_orders():
    def get_exif_date(img):
        try:
            return img.get_exif('Image DateTime')
        except AttributeError:
            return None

    def reverse(f):
        def _reverse(x, y):
            return -f(x, y)
        return _reverse
        
    ORDERS = {'title' : lambda x,y:cmp(x.title, y.title),
              'dir'   : lambda x,y:cmp(x.isdir, y.isdir),
              'mtime' : lambda x,y:cmp(x.mtime, y.mtime),
              'exifdate' : lambda x,y:cmp(get_exif_date(x), get_exif_date(y)),
              'name'  : lambda x,y:cmp(x.name, y.name),
              'href'  : lambda x,y:cmp(x.href, y.href),
              'publishtime' : lambda x,y:cmp(x.publish_time,y.publish_time)}

    for key, item in ORDERS.items():
        ORDERS['-' + key] = reverse(item)
    return ORDERS

ORDERS = init_orders()

class ItemLoader(object):
    def __init__(self):
        self.__cache = {}
        self._loaders = []

    def register_loader(self, predicate, loader):
        self._loaders.insert(0, (predicate, loader))

    def _create_item(self, path):
        name = os.path.basename(path).lower()
        if CONFIG.ignore_path(path):
            return None
        for predicate, loader in self._loaders:
            if predicate(path):
                return loader(path)
        return None

    def get_item(self, path):
        path = os.path.abspath(path) # TODO: this may not work right on windows
        try:
            return self.__cache[path]
        except KeyError:
            v = self._create_item(path)
            self.__cache[path] = v
            return v

    def _load_itemData(self):
        return ItemData()
    def _load_setData(self):
        return SetData()

    itemData = virtual_demand_property('itemData')
    setData = virtual_demand_property('setData')

ITEMLOADER = ItemLoader()

create_item = ITEMLOADER.get_item

def register_loaders():
    def redir_ext(ext):
        def predicate(path):
            return os.path.exists(path + ext)
        def load(path):
            return ITEMLOADER.get_item(path + ext)
        return predicate, load
    def prefixloader(prefix, func):
        def predicate(path):
            return path.startswith(prefix)
        def load(path):
            path = path[len(prefix):]
            if path.startswith('/'):
                path = path[1:]
            return func(path)
        return predicate, load
    ITEMLOADER.register_loader(ImageItem.load_predicate, ImageItem)
    ITEMLOADER.register_loader(AlbumItem.load_predicate, AlbumItem)
    ITEMLOADER.register_loader(*redir_ext('.jpg'))
    ITEMLOADER.register_loader(*redir_ext('.JPG'))
    def load_set(x):
        return ITEMLOADER.setData.get(x)
    def load_tag(x):
        if not x:
            return ImageTags()
        else:
            return ITEMLOADER.itemData.get(x)
    def load_by_date(x):        
        if not x:
            return YearView()
        else:
            ym = x.split('/')
            try:
                if len(ym) == 1:
                    return YearView(int(ym[0]))
                elif len(ym) == 2:
                    return ImagesByDate(int(ym[0]), int(ym[1]))
            except ValueError:
                pass
        return None
    ITEMLOADER.register_loader(*prefixloader('/bydate', load_by_date))
    ITEMLOADER.register_loader(*prefixloader('/recent', lambda x:RecentItems()))
    ITEMLOADER.register_loader(*prefixloader('/albums', load_set))
    ITEMLOADER.register_loader(*prefixloader('/keyword', load_tag))
    ITEMLOADER.register_loader(*prefixloader(STORE.root + '/albums',
                                             load_set))
    ITEMLOADER.register_loader(*prefixloader(STORE.root + '/keyword',
                                             load_tag))

    if os.path.exists(os.path.join(STORE.root, '_singleshot.py')):
        gl = {'ITEMLOADER' : ITEMLOADER}
        lc = {}
        execfile(os.path.join(STORE.root, '_singleshot.py'),
                 gl, lc)


register_loaders()
