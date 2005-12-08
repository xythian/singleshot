from singleshot.storage import FilesystemEntity, FileInfo
from singleshot.ssconfig import read_config
from singleshot.jpeg import JpegHeader, calculate_box
from singleshot.model import ContainerItem, ImageItem, MONTHS, DynamicContainerItem
from singleshot import imageprocessor, pages
import mmap

from singleshot.properties import dtfromtimestamp, Local
import time
import os
from datetime import datetime, date
from cStringIO import StringIO
import cPickle as pickle
#import pickle
import sys


import fnmatch

import logging
LOG = logging.getLogger('singleshot')

class FSLoader(object):
    def __init__(self, store):
        self.store = store
        self.config = store.config

    def handles(self, finfo):
        return False
    

class ImageFSLoader(FSLoader):
    def handles(self, fileinfo):
        return self.store.processor.handles(fileinfo)

    extensions = property(lambda self:self.store.processor.extensions)

    def load_path(self, path, fileinfo):
        processor = self.store.processor
        
        if path.endswith(fileinfo.extension):
            path = path[:-len(fileinfo.extension)]        
        img = ImageItem()
        img.path = path
        img.aliases = (path + fileinfo.extension,)
        img.rawimagepath = fileinfo.path
        img.filename = fileinfo.filename
        processor.load_metadata(img, fileinfo)
        img.modify_time = fileinfo.mtime
        if not img.publish_time:
            p = month_dir(fileinfo.dirname)
            if p:
                year, month, t = p
                img.publish_time = t
            else:
                img.publish_time = dtfromtimestamp(fileinfo.mtime)
        if not img.title.strip():
            img.title = img.filename
        rootzor = fileinfo.dirname[len(self.store.root)+1:]
        img.viewfilepath = os.path.join(self.store.view_root, rootzor)
        return img       

def month_dir(fspath):
    p2, p1 = os.path.split(fspath)
    p2 = os.path.basename(p2)
    try:
        month = int(p1)
        year = int(p2)
    except ValueError:
        return None
    if month > 0 and month < 13:
        return year, month, datetime(year, month, 01, 00, 00, 00,tzinfo=Local)
    else:
        return None
    


class DirectoryFSLoader(FSLoader):
    def __init__(self, store, is_item):
        super(DirectoryFSLoader, self).__init__(store)
        self._is_item = is_item
        
    def handles(self, fileinfo):
        return fileinfo.isdir

    def override_template(self, fspath, name):
        path = os.path.join(fspath, name)
        if os.path.exists(path):
            return path
        else:
            return self.store.find_template(name)

    def load_path(self, path, fileinfo):
        d = ContainerItem()
        config = read_config(os.path.join(fileinfo.path, '_album.cfg'),
                             { 'album': { 'title' : '',
                                          'highlightimage' : '',
                                          'order' : 'dir,title',
                                          }
                               })           
        d.order = config.get('album', 'order')
        d.viewpath = self.override_template(fileinfo.path, 'album.html')
        d.imageviewpath = self.override_template(fileinfo.path, 'view.html')
        d.title = config.get('album', 'title')
        d.modify_time = fileinfo.mtime
        d.publish_time = d.modify_time
        if not d.title:
            mdir = month_dir(fileinfo.path)
            if mdir:
                year, month, d.publish_time = mdir
                d.title = '%s %d' % (MONTHS[month-1], year)
            else:
                d.title = fileinfo.basename
        d.path = path
        contents = []
        l = len(self.store.root)
        for name in os.listdir(fileinfo.path):
            fspath1 = os.path.join(fileinfo.path, name)
            if self.config.ignore_path(fspath1):
                continue
            elif os.path.isdir(fspath1):
                pass
            elif not self._is_item(FileInfo(fspath1)):
                continue
            path1 = fspath1[l:]            
            contents.append(path1)
        d.contents = contents
        return d

class ItemLoader(object):
    def load_item(self, path):
        return None

    def walk(self):
        def walk(load, item):
            todo = [item]
            while todo:
                item = todo.pop()
                assert item != None
                yield item
                if item.iscontainer:
                    for path in item.contents:
                        item = load(path)
                        assert item != None
                        todo.append(item)    
        return walk(self.load_item, self.load_item('/'))

class MemoizeLoader(ItemLoader):
    def __init__(self, load_item=None):
        if load_item:
            self._load_item = load_item
        self._cache = {}

    def load_item(self, path):
        try:
            return self._cache[path]
        except KeyError:
            v = self._load_item(path)
            self._cache[path] = v
            return v

class FilesystemLoader(ItemLoader):
    def __init__(self, store):
        self.store = store
        self.config = store.config
        self.imgloader = ImageFSLoader(store) 
        self.loaders = [self.imgloader,
                        DirectoryFSLoader(store, self.imgloader.handles)]
        self._cache = {}

    def load_item(self, path):
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]
        if path.startswith(self.store.root):
            fspath = path
            path = path[len(self.store.root):]
        elif not path:
            path = '/'
        finfo = FileInfo(self.store.root, path[1:])
        if self.config.ignore_path(finfo.path):
            return None
        try:
            item = self._cache[path]
        except KeyError:            
            item = None

        if not item:
            mtime = 0
        else:
            mtime = item.modify_time

        if not mtime or mtime > finfo.mtime:
            item = self._load_path(path, finfo)
            self._cache[path] = item
            if item:
                for alias in item.aliases:
                    self._cache[alias] = item
        return item

    
    def _load_path(self, path, finfo):
        for loader in self.loaders:
            if loader.handles(finfo):
                return loader.load_path(path, finfo)
        def both(exts):
            while True:
                n = exts.next()            
                yield n
                yield n.upper()
            
        if not finfo.extension:
            xpath = finfo.path
            for ext in both(iter(self.imgloader.extensions)):
                finfo = FileInfo(xpath + ext)
                if finfo.exists:
                    if self.imgloader.handles(finfo):
                        return self.imgloader.load_path(path, finfo)        
        return None

class ImageSize(FilesystemEntity):
    """
    An ImageSize is an ImageItem rendered at a particular size.
    It may or may not represent something already in the cache.
    """
    def __init__(self,
                 store=None,
                 image=None,
                 size=None,
                 height=None,
                 width=None,
                 mtime=None):
        self.image = image
        self.height = height
        self.width = width
        self.size = size
        self.imagemtime = mtime
        self.store = store
        self.config = store.config
        pn, fn = os.path.split(image.path)
        bn, ext = os.path.splitext(image.filename)
        filename = '%s-%s.jpg' % (bn,
                                  size)
        self.href = self.config.url_prefix + pn[1:]
        if self.href[-1] != '/':
            self.href += '/' + filename
        else:
            self.href += filename
        path = os.path.join(image.viewfilepath, filename) 
        super(ImageSize, self).__init__(path)

    def _get_uptodate(self):
        if not self.exists:
            return False
        elif self.imagemtime > self.mtime:
            return False
        else:
            return True

    uptodate = property(_get_uptodate)

    def ensure(self):
        if self.uptodate:
            return        
        self.generate()

    def generate(self):
        if not os.path.exists(self.image.viewfilepath):
            os.makedirs(self.image.viewfilepath)
        self.store.processor.execute(source=self.image.rawimagepath,
                                     dest=self.path,
                                     size=self)

    def expire(self):
        if self.exists:    
            os.remove(self.path)


class ImageSizes(dict):
    def __init__(self, image):
        self.__image = image
        store = image.store
        w, h = image.width, image.height
        available = []
        self.config = store.config
        for box in self.availableSizes:
            szname = self.sizeNames[box]
            width, height = calculate_box(box, w, h)
            s = os.stat(image.rawimagepath).st_mtime
            sz = ImageSize(store=store,
                           image=image,
                           size=box,
                           width=width,
                           height=height,
                           mtime=s)
            if not sz.uptodate:
                sz.expire()
            setattr(self, '%sSize' % szname, sz)
            self[box] = sz
            self[szname] = sz
            setattr(self, 'has%sSize' % szname, True)
            
    def _get_files(self):
        # get files for all of the
        # existing sizes for this image
        pattern = r'(__filter_.+_)?%s-([1-9][0-9]+).jpg' % (re.escape(self.__image.filename),)
        rxp = re.compile(pattern)
        vp = self.__image.viewfilepath
        paths = [os.path.join(vp, filename) for filename in os.listdir(vp) if rxp.match(filename)]
        return paths

    def _get_availableSizes(self):
        return self.config.availableSizes

    def _get_sizeNames(self):
        return self.config.sizeNames

    availableSizes = property(_get_availableSizes)
    sizeNames = property(_get_sizeNames)
    files = property(_get_files)


class Tag(object):
    __slots__ = ('name', 'count', 'imagemap')
    def __init__(self, name):
        self.name = name
        self.count = 0
        self.imagemap = 0L

    def add(self, imageid):
        self.count += 1
        self.imagemap |= 1L << imageid        

class ImageYear(object):
    __slots__ = ('year', 'months', 'count')
    
    def __init__(self, year):
        self.year = year
        self.months = [0] * 12
        self.count = 0

    def add(self, month):
        self.months[month-1] += 1
        self.count += 1

class ItemData(object):
    pass

class PickleCacheStore(object):
    def __init__(self, store, load_itemdata=None):
        self.store = store
        self._cachepath = os.path.join(store.view_root, '.itemcache')
        self._data = False
        self._load_itemdata = load_itemdata
        self._itemmap = {}
        self._directories = []
        self.__uptodatecheck = 0

    def uptodate(self):
        n = time.time()
        path = self._cachepath
        if (n - self.__uptodatecheck) < 10.:
            return True
        try:
            self.__uptodatecheck = n
            LOG.debug('Rechecking directories')
            t = os.stat(path).st_mtime
            outofdate = [item for item in self._directories if os.stat(item).st_mtime > t]
            return not bool(outofdate)
        except:
            pass
        return False        

    def _store(self, itemdata):
        s = StringIO()
        pickle.dump(itemdata, s,
                     pickle.HIGHEST_PROTOCOL)
        f = open(self._cachepath, 'w')
        f.write(s.getvalue())
        f.close()

    def _read(self):
        n = time.time()
        f = open(self._cachepath, 'r')
        try:
            self._prepare_data(pickle.load(f))
        finally:
            f.close()
        LOG.info('Loaded itemcache %.2fms', (time.time() - n)*1000.)                
    def _initcache(self):
        n = time.time()
        itemdata = self._load_itemdata()
        self._store(itemdata)
        self._prepare_data(itemdata)
        self.__uptodatecheck = time.time()        
        LOG.info('Initialized itemcache %.2fms', (time.time() - n)*1000.)

    def ready(self):        
        if not self._data:
            try:
                self._read()
            except IOError:
                pass
            if not self._data:
                self._initcache()
        if not self.uptodate():
            self._initcache()

    def _prepare_data(self, data):
        self._directories = []
        self._data = data
        self._itemlist = data._itemlist
        self._itemmap = {}
        self._years = data._years
        for item in data._itemlist:
            assert item != None
            if item.iscontainer:
                self._directories.append(os.path.join(self.store.root,
                                                      item.path[1:]))
            self._itemmap[item.path] = item
            for alias in item.aliases:
                self._itemmap[alias] = item
        self.tags = data.tags
        self._allimages = data._allimages

    def all_tags(self):
        self.ready()
        return self.tags.items()


    def load_item(self, path):
        self.ready()
        try:
            return self._itemmap[path]
        except KeyError:
            return None

    def _query(self, tags):
        self.ready()        
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
        if imgmap == self._allimages:
            imgmap = 0L
        return imgmap, excmap

    def query_tag(self, tags):
        imgmap, excmap = self._query(tags)
        result = []
        for idx in xrange(len(self._itemlist)):
            imgmask = 1L << idx
            if imgmap & imgmask and not excmap & imgmask:
                result.append(self._itemlist[idx].path)
        return result


    def most_tags(self):
        self.ready()
        x = [(unicode(tag.name), tag) for tag in self.tags.values() if tag.count > 3 and ':' not in tag.name]
        return x

    def recent_images(self, count=10):
        self.ready()        
        imgs = [(item.publish_time, item.path) for item in self._itemlist if isinstance(item, ImageItem)]
        imgs.sort()
        imgs.reverse()
        if count > len(imgs):
            count = len(imgs)
        return [img[1] for img in imgs[:count]]

    def recent_items(self, count=10):
        event = None
        items = []
        for item in self.recent_images(1000):
            item = self.load_item(item)
            if event and event in item.keywords:
                continue
            else:
                event = None
            eventalbum = None
            for keyword in item.keywords:
                if keyword.startswith('event:'):
                    evtkey = keyword[6:]
                    eventalbum = '/albums/events/%s' % evtkey
            if eventalbum:
                items.append(eventalbum)
                event = keyword
            else:
                items.append(item.path)
            if len(items) == count:
                break
        return items
                    
        

    def image_years(self):
        self.ready()        
        return self._years.values()

    def image_year(self, year):
        self.ready()        
        return self._years[year]

    def prepare_tag(self, tag):
        tag = tag.lower()
        tag = tag.replace(' ', '')
        return tag

CacheStore = PickleCacheStore

class SingleshotLoader(ItemLoader):
    def __init__(self, store, parent=None):
        self._parent = parent
        self._load_item = parent.load_item
        self.store = store
        self._data = CacheStore(self.store,
                                load_itemdata=self._load_raw)
        self.all_tags = self._data.all_tags
        self.most_tags = self._data.most_tags
        self.query = self._data.query_tag
        self.recent_images = self._data.recent_images
        self.recent_items = self._data.recent_items
        self.image_year = self._data.image_year
        self.image_years = self._data.image_years
        self._albums = AlbumData(self.store)

    def _load_raw(self):
        data = ItemData()
        data.tags = {}
        data._itemlist = []
        data._years = {}
        data._allimages = 0L
        load_item = self._load_item
        data._itemlist.append(load_item('/'))
        for item in self._parent.walk():
            assert item != None
            data._itemlist.append(item)
            if isinstance(item, ImageItem):
                itemid = len(data._itemlist) - 1
                path = item.path
                data._allimages |= 1L << itemid
                def record_keywords():
                    def record_keyword(tag):
                        tag = self._data.prepare_tag(tag)
                        if not tag:
                            return
                        try:
                            data.tags[tag].add(itemid)
                        except KeyError:
                            t = Tag(tag)
                            t.add(itemid)
                            data.tags[tag] = t
                    for tag in item.keywords:
                        record_keyword(tag)
                    d = item.publish_time
                    try:
                        yearrecord = data._years[d.year]
                    except KeyError:
                        yearrecord = ImageYear(d.year)
                        data._years[d.year] = yearrecord
                    yearrecord.add(d.month)
                    record_keyword('publish:%04d-%02d' % (d.year, d.month))
                    record_keyword('publish:%04d' % (d.year))
                    record_keyword('publish:%04d-%02d-%02d' % (d.year, d.month, d.day))
                    if item.camera_model:
                        record_keyword('camera:%s' % item.camera_model)
                record_keywords()
        return data

    def dynacontainer(self, path, title, **kw):
        return DynamicContainerItem(self.store, path, title, **kw)

    def load_item(self, path):
        store = self.store
        if path.startswith('/albums'):
            n = path[8:]
            data = self._albums.get(n)
            if not data:
                return None
            def absify(path):
                if isinstance(path, str):
                    return path
                else:
                    return '/albums/' + path.path
            def cfunc():
                if data.tag:
                    return self.query(data.tag.split('/'))
                else:
                    return [absify(al) for al in data.children]
            if data.tag:
                order = '-publishtime'
            else:
                order = ''
            return self.dynacontainer(path,
                                      data.title,
                                      contentsfunc=cfunc,
                                      order=order,
                                      caption=data.caption,
                                      **data.info)
        elif path.startswith('/recent'):
            km = path.split('/')[1:]
            count = 200
            if len(km) == 2:
                try:
                    count = int(km[1])
                except:
                    pass
            if count > 5000:
                count = 5000
            
            return self.dynacontainer(path,
                                        'Recent photos',
                                        contentsfunc=lambda : self.recent_images(count),
                                        order='-publishtime')
        elif path.startswith('/keyword'):
            if len(path) > 9:
                kwquery = path[9:]
                tags = kwquery.split('/')
                d = self.dynacontainer(path,
                                         kwquery,
                                         contentsfunc=lambda : self.query(tags),
                                         order='-publishtime')
            else:
                mosttags = self.most_tags()
                mosttags.sort()
                contents = ['/keyword/' + tag for tag, o in mosttags]
                d = self.dynacontainer(path,
                                         'Keywords',
                                         contents=contents,
                                         viewpath=store.find_template('keywords.html'),
                                         order = '')
            return d
        elif path.startswith('/bydate'):
            ym = path.split('/')[1:]
            if len(ym) == 1:
                contents = ['/bydate/' + str(year.year) for year in self.image_years()]
                count = reduce(lambda x,y:x+y, [year.count for year in self.image_years()])
                contents.sort()
                contents.reverse()
                return self.dynacontainer(path,
                                            'Browse by date',
                                            contents=contents,
                                            count=count,
                                            viewpath=store.find_template('bydate.html'),
                                            order='')
                                            
            elif len(ym) == 2:
                try:
                    year = int(ym[1])
                except ValueError:
                    return None
                yr = self.image_year(year)
                contents = ['/bydate/%04d/%02d' % (year, idx+1) for idx, count in enumerate(yr.months) if count > 0]
                contents.sort()
                contents.reverse()
                return self.dynacontainer(path,
                                            str(year),
                                            contents=contents,
                                            count=yr.count,
                                            viewpath=store.find_template('bydate.html'),
                                            order='')
            elif len(ym) == 3:
                try:
                    year = int(ym[1])
                    month = int(ym[2])
                    yearo = self.image_year(year)                    
                except ValueError:
                    return None
                except KeyError:
                    return None
                return self.dynacontainer(path,
                                            '%s %d' % (MONTHS[month-1],
                                                       year),
                                            count=yearo.months[month-1],
                                            contentsfunc=lambda : self.query(['publish:%04d-%02d' % (year, month)]))
            else:
                return None
        else:
            return self._data.load_item(path)

class DynamicAlbum(object):
    def __init__(self, name, tag=None, title='', caption='', children=(), **kw):
        self.path = name
        self.name = name
        if not title:
            self.title = name
        else:
            self.title = title        
        self.tag = tag
        self.caption = caption
        self.children = children
        self.info = kw

class AlbumData(object):
    def __init__(self, store):
        self._sets = {}
        self.store = store
        self._loaded = False    
        

    def _load(self):
        path = os.path.join(self.store.root, '_singleshot.py')
        if os.path.exists(path):
            gl = {'ALBUMS' : self,
                  'Album' : DynamicAlbum}
            lc = {}
            execfile(path, gl, lc)
        

    def add(self, set):
        self._sets[set.path] = set

    def define_albums(self, title, albums):
        def fix_paths(parentpath, set):
            self.add(set)
            set.path = parentpath
            if set.children:
                for s in set.children:
                    if isinstance(s, DynamicAlbum):
                        if parentpath:
                            s.path = parentpath + '/' + s.path
                        fix_paths(s.path, s)
        root = []
        for set in albums:
            root.append(set)
        rootset = DynamicAlbum('', title=title, children=root)
        fix_paths('', rootset)

    def get(self, path):
        if not self._loaded:
            self._loaded = True
            self._load()
        return self._sets.get(path)



