from singleshot.storage import FilesystemEntity
from singleshot.ssconfig import read_config
from singleshot.jpeg import JpegHeader, parse_exif_date, calculate_box
from singleshot.model import ContainerItem, ImageItem, MONTHS, DynamicContainerItem
from singleshot import imageprocessor, pages


import time
import os
from datetime import datetime
from cStringIO import StringIO
#import cPickle as pickle
import pickle
import sys


class FSLoader(object):
    def __init__(self, store):
        self.store = store
        self.config = store.config

    def handles(self, path, ext, fspath):
        return False
    

class ImageFSLoader(FSLoader):
    def handles(self, path, ext, fspath):
        return self.store.processor.handles(ext, fspath)

    def load_path(self, path, ext, fspath):
        processor = self.store.processor
        
        if path.endswith(ext):
            path = path[:-len(ext)]        
        img = ImageItem()
        img.path = path
        img.aliases = (path + ext,)
        img.rawimagepath = fspath        
        processor.load_metadata(img, ext, fspath)
        if not img.publish_time:
            pth = os.path.dirname(img.rawimagepath)
            p = month_dir(pth)
            if p:
                year, month, t = p
                img.publish_time = t                            
            else:
                img.publish_time = os.stat(img.rawimagepath).st_mtime
        if not img.title:
            img.title = img.filename
        dirpath, img.filename = os.path.split(fspath)
        rootzor = dirpath[len(self.store.root)+1:]
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
        return year, month, time.mktime((year, month, 01, 0, 0, 0, -1, -1, 0))
    else:
        return None
    


class DirectoryFSLoader(FSLoader):
    def __init__(self, store, load_item):
        super(DirectoryFSLoader, self).__init__(store)
        self._load_item = load_item
        
    def handles(self, path, ext, fspath):
        return os.path.isdir(fspath)

    def override_template(self, fspath, name):
        path = os.path.join(fspath, name)
        if os.path.exists(path):
            return path
        else:
            return self.store.find_template(name)

    def load_path(self, path, ext, fspath):
        d = ContainerItem()
        config = read_config(os.path.join(fspath, '_album.cfg'),
                             { 'album': { 'title' : '',
                                          'highlightimage' : '',
                                          'order' : 'dir,title',
                                          }
                               })           
        d.order = config.get('album', 'order')
        d.viewpath = self.override_template(fspath, 'album.html')
        d.imageviewpath = self.override_template(fspath, 'view.html')
        d.title = config.get('album', 'title')
        if not d.title:
            mdir = month_dir(fspath)
            if mdir:
                year, month, d.publish_time = mdir
                d.title = '%s %d' % (MONTHS[month-1], year)
            else:
                d.title = os.path.basename(fspath)
        if not d.publish_time:
            d.publish_time = os.stat(fspath).st_mtime
        d.path = path
        contents = []
        l = len(self.store.root)
        for name in os.listdir(fspath):
            fspath1 = os.path.join(fspath, name)
            if self.config.ignore_path(fspath1):
                continue
            path1 = fspath1[l:]
            if self._load_item(path1):
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
                if item:
                    yield item
                else:
                    continue
                if item.iscontainer:
                    for path in item.contents:
                        todo.append(load(path))    
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

class FilesystemLoader(MemoizeLoader):
    def __init__(self, store):
        super(FilesystemLoader, self).__init__()
        self.store = store
        self.config = store.config
        self.loaders = [ImageFSLoader(store),
                        DirectoryFSLoader(store, self.load_item)]
        
    def _load_item(self, path):
        if path.endswith('/') and len(path) > 1:
            path = path[:-1]
        if path.startswith(self.store.root):
            fspath = path
            path = path[len(self.store.root):]
        elif not path:
            path = '/'            
        fspath = os.path.join(self.store.root, path[1:])
#        try:
        def x():
            st = os.stat(fspath)
            bn = os.path.split(fspath)[1]
            name, ext = os.path.splitext(bn)
            if self.config.ignore_path(fspath):
                return None
            for loader in self.loaders:
                if loader.handles(path, ext, fspath):
                    return loader.load_path(path, ext, fspath)
#        except OSError, msg:
#            pass
        return x()
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
        self.href = self.config.url_prefix + pn[1:] + '/' + filename
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
                                     size=self.size)
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



class SingleshotLoader(ItemLoader):
    def __init__(self, store, parent=None):
        self._cachepath = os.path.join(store.view_root, '.itemcache')
        self._parent = parent
        self._load_item = parent.load_item
        self.store = store

    def load(self):
        n = time.time()
        cached = 'No'
        if self.has_cache():
            cached = 'Yes'
            self._load_cache()
        else:
            self._load_raw()
            self._save_cache()
        self._albums = AlbumData(self.store)        
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
            self._prepare_data(pickle.load(f))
        finally:
            f.close()

    def _prepare_data(self, data):
        self._data = data
        self._itemlist = data._itemlist
        self._itemmap = {}
        self._years = data._years
        for item in data._itemlist:
            assert item != None
            self._itemmap[item.path] = item
            for alias in item.aliases:
                self._itemmap[alias] = item
        self.tags = data.tags
        self._allimages = data._allimages

    def _save_cache(self):
        s = StringIO()
        pickle.dump(self._data, s,
                     pickle.HIGHEST_PROTOCOL)
        f = open(self._cachepath, 'w')
        f.write(s.getvalue())
        f.close()

    def prepare_tag(self, tag):
        tag = tag.lower()
        tag = tag.replace(' ', '')
        return tag
    
    def _load_raw(self):
        data = ItemData()
        data.tags = {}
        data._itemlist = []
        data._years = {}
        data._allimages = 0L
        load_item = self._load_item
        data._itemlist.append(load_item('/'))
        for item in self._parent.walk():
            data._itemlist.append(item)
            if not item.iscontainer:
                itemid = len(data._itemlist) - 1
                path = item.path
                data._allimages |= 1L << itemid
                def record_keywords():
                    def record_keyword(tag):
                        tag = self.prepare_tag(tag)
                        try:
                            data.tags[tag].add(itemid)
                        except KeyError:
                            t = Tag(tag)
                            t.add(itemid)
                            data.tags[tag] = t
                    for tag in item.keywords:
                        record_keyword(tag)
                    pt = item.publish_time
                    d = datetime.fromtimestamp(pt)
                    try:
                        yearrecord = data._years[d.year]
                    except KeyError:
                        yearrecord = ImageYear(d.year)
                        data._years[d.year] = yearrecord
                    yearrecord.add(d.month)
                    record_keyword('publish:%04d-%02d' % (d.year, d.month))
                    record_keyword('publish:%04d' % (d.year))
                    record_keyword('publish:%04d-%02d-%02d' % (d.year, d.month, d.day))
                record_keywords()        
        self._prepare_data(data)

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
        if imgmap == self._allimages:
            imgmap = 0L
        return imgmap, excmap

    def query(self, tags):
        n = time.time()
        imgmap, excmap = self._query(tags)
        result = []
        for idx in xrange(len(self._itemlist)):
            imgmask = 1L << idx
            if imgmap & imgmask and not excmap & imgmask:
                result.append(self._itemlist[idx].path)
        print >>sys.stderr, 'Query time: %s %.2fms' % (','.join(tags), (time.time() - n) * 1000.), len(result)
        return result

    def image_years(self):
        return self._years.values()

    def image_year(self, year):
        return self._years[year]

    def early_images(self, count=10):
        imgs = [(item.publish_time, item.path) for item in self._itemlist if isinstance(item, ImageItem)]
        imgs.sort()
        if count > len(imgs):
            count = len(imgs)
        return [img[1] for img in imgs[:count]]
        

    def recent_images(self, count=10):        
        imgs = [(item.publish_time, item.path) for item in self._itemlist if isinstance(item, ImageItem)]
        imgs.sort()
        imgs.reverse()
        if count > len(imgs):
            count = len(imgs)
        return [img[1] for img in imgs[:count]]

    def dynacontainer(self, path, title, **kw):
        return DynamicContainerItem(self.store, path, title, **kw)

    def load_item(self, path):
        store = self.store
        if path.startswith('/albums'):
            n = path[8:]
            data = self._albums.get(n)
            if not data:
                return None
            def cfunc():
                if data.tag:
                    return self.query(data.tag.split('/'))
                else:
                    return ['/albums/' + al.path for al in data.children]
            if data.tag:
                order = '-publishtime'
            else:
                order = ''
            return self.dynacontainer(path,
                                        data.title,
                                        highlightpath=data.highlightpath,
                                        contentsfunc=cfunc,
                                        caption=data.caption,
                                        order=order)
        elif path.startswith('/recent'):
            km = path.split('/')[1:]
            count = 15
            if len(km) == 2:
                try:
                    count = int(km[1])
                except:
                    pass
            if count > 50:
                count = 50
            
            return self.dynacontainer(path,
                                        'Recent photos',
                                        contentsfunc=lambda : self.recent_images(count),
                                        order='-publishtime')
        elif path.startswith('/keyword'):
            if len(path) > 9:
                kwquery = path[9:]
                tags = kwquery.split('/')
                if len(tags) == 1:
                    try:
                        count = self.tags[tags[0]].count
                    except KeyError:
                        count = 0                    
                else:
                    count = -1
                d = self.dynacontainer(path,
                                         kwquery,
                                         count=count,
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
            try:
                return self._itemmap[path]
            except KeyError:
                return None

class DynamicAlbum(object):
    def __init__(self, name, tag=None, title='', caption='', children=(), highlightpath=''):
        self.path = name
        self.name = name
        if not title:
            self.title = name
        else:
            self.title = title        
        self.tag = tag
        self.caption = caption
        self.children = children
        self.highlightpath = highlightpath

class AlbumData(object):
    def __init__(self, store):
        self._sets = {}
        self.store = store
        self._load()

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
                    if parentpath:
                        s.path = parentpath + '/' + s.path
                    fix_paths(s.path, s)
        root = []
        for set in albums:
            root.append(set)
        rootset = DynamicAlbum('', title=title, children=root)
        fix_paths('', rootset)

    def get(self, path):
        return self._sets.get(path)


