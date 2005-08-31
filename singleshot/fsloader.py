from storage import FilesystemEntity
from ssconfig import CONFIG, STORE, read_config
from jpeg import JpegHeader, parse_exif_date, load_exif, calculate_box
import time
import os
from datetime import datetime
from model import ContainerItem, ImageItem, MONTHS, DynamicContainerItem
from cStringIO import StringIO
import cPickle
import sys
import imageprocessor

IMAGE_EXTENSIONS = ('.jpg', '.JPG')
IMAGESIZER = imageprocessor.select_processor()

def find_publish_time(header, img):
        t = 0.0
        for search in ('DateTimeDigitized', 'DateTimeOriginal', 'DateCreated'):
            if hasattr(header.xmp, search):
                t = getattr(header.xmp, search)
                break        
        if not t:
            exif = load_exif(img.rawimagepath)
            try:
                et = exif['EXIF DateTimeDigitized']
                t = parse_exif_date(et)
            except KeyError:
                pth = os.path.dirname(img.rawimagepath)
                p = month_dir(pth)
                if p:
                    year, month, t = p
            if not t:
                t = os.stat(img.rawimagepath).st_mtime
        return t

def load_image_item(st, path, fspath):
    header = JpegHeader(fspath)
    img = ImageItem()
    img.path = path
    if header.xmp.Headline:
        img.title = header.xmp.Headline
    elif header.itpc.title:
        img.title = header.itpc.title
    else:
        img.title = os.path.splitext(os.path.basename(fspath))[0]
    img.caption = header.itpc.caption
    img.rawimagepath = fspath
    img.height = header.height
    img.width = header.width
    img.publish_time = find_publish_time(header, img)
    img.keywords = header.xmp.keywords
    dirpath, img.filename = os.path.split(fspath)
    rootzor = dirpath[len(STORE.root)+1:]
    img.viewfilepath = os.path.join(STORE.view_root, rootzor)
    return img

def override_template(fspath, name):
    path = os.path.join(fspath, name)
    if os.path.exists(path):
        return path
    else:
        return STORE.find_template(name)

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
    

def load_directory_item(st, path, fspath):
    d = ContainerItem()
    config = read_config(os.path.join(fspath, '_album.cfg'),
                         { 'album': { 'title' : '',
                                      'highlightimage' : '',
                                      'order' : 'dir,title',
                                      }
                           })           
    d.order = config.get('album', 'order')
    d.viewpath = override_template(fspath, 'album.html')
    d.imageviewpath = override_template(fspath, 'view.html')
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
    l = len(STORE.root)
    for name in os.listdir(fspath):
        fspath1 = os.path.join(fspath, name)
        if CONFIG.ignore_path(fspath1):
            continue
        name, ext = os.path.splitext(name)
        if os.path.isdir(fspath1):            
            contents.append(fspath1[l:])
        elif ext in IMAGE_EXTENSIONS:
            contents.append(fspath1[l:-4])
            
    d.contents = contents
    return d

def load_item(path):
    if path.endswith('/') and len(path) > 1:
        path = path[:-1]
    if path.startswith(STORE.root):
        fspath = path
        path = path[len(STORE.root):]
    else:
        fspath = os.path.join(STORE.root, path[1:])
    if not path:
        path = '/'
    try:
        if CONFIG.ignore_path(fspath):
            return None
        if os.path.isdir(fspath):
            return load_directory_item(os.stat(fspath), path, fspath)
        else:
            for ext in IMAGE_EXTENSIONS:
                try:
                    st = os.stat(fspath + ext)
                    return load_image_item(st, path, fspath + ext)
                except OSError:
                    pass
        return None
    except OSError:
        return None

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
                 mtime=None,
                 flt=None):        
        self.image = image
        self.height = height
        self.width = width
        self.size = size
        self.imagemtime = mtime
        pn, fn = os.path.split(image.path)
        bn, ext = os.path.splitext(image.filename)
        if flt:
            filename = '__filter_%s_%s-%s.jpg' % (flt,
                                                bn,
                                                size)
        else:
            filename = '%s-%s.jpg' % (bn,
                                      size)
        self.filter = flt
        self.href = CONFIG.url_prefix + pn[1:] + '/' + filename
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

    def filtered(self, flt=None):
        if not flt:
            return self
        return ImageSize(self.image, self.size, self.height, self.width, mtime=self.imagemtime, flt=flt)

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
        if not os.path.exists(self.image.viewfilepath):
            os.makedirs(self.image.viewfilepath)
        IMAGESIZER.execute(source=self.image.rawimagepath,
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
            s = os.stat(image.rawimagepath).st_mtime
            sz = ImageSize(image=image,
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
        return CONFIG.availableSizes

    def _get_sizeNames(self):
        return CONFIG.sizeNames

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

class MemoizeLoader(object):
    def __init__(self, load_item=load_item):
        self._load_item = load_item
        self._cache = {}

    def load_item(self, path):
        try:
            return self._cache[path]
        except KeyError:
            v = self._load_item(path)
            self._cache[path] = v
            return v

def loaderwalk(load_func):
    def walk(item):
        todo = [item]
        while todo:
            item = todo.pop()
            if item:
                yield item
            if item.iscontainer:
                for path in item.contents:
                    todo.append(load_item(path))        
    item = load_func('/')
    return walk(item)

class FilesystemLoader(object):
    def __init__(self, load_item=load_item):
        self._cachepath = os.path.join(STORE.view_root, '.itemcache')
        self._load_item = load_item
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
            self._prepare_data(cPickle.load(f))
        finally:
            f.close()

    def _prepare_data(self, data):
        self._data = data
        self._itemlist = data._itemlist
        self._itemmap = {}
        self._years = data._years
        self._albums = data._albums
        for item in data._itemlist:
            assert item != None
            self._itemmap[item.path] = item
        self.tags = data.tags
        self._allimages = data._allimages

    def _save_cache(self):
        s = StringIO()
        cPickle.dump(self._data, s,
                     cPickle.HIGHEST_PROTOCOL)
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
        data._albums = AlbumData()
        for item in loaderwalk(load_item):
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

    def load_item(self, path):
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
            return DynamicContainerItem(path,
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
            
            return DynamicContainerItem(path,
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
                d = DynamicContainerItem(path,
                                         kwquery,
                                         count=count,
                                         contentsfunc=lambda : self.query(tags),
                                         order='-publishtime')
            else:
                mosttags = self.most_tags()
                mosttags.sort()
                contents = ['/keyword/' + tag for tag, o in mosttags]
                d = DynamicContainerItem(path,
                                         'Keywords',
                                         contents=contents,
                                         viewpath=STORE.find_template('keywords.html'),
                                         order = '')
            return d
        elif path.startswith('/bydate'):
            ym = path.split('/')[1:]
            if len(ym) == 1:
                contents = ['/bydate/' + str(year.year) for year in self.image_years()]
                count = reduce(lambda x,y:x+y, [year.count for year in self.image_years()])
                contents.sort()
                contents.reverse()
                return DynamicContainerItem(path,
                                            'Browse by date',
                                            contents=contents,
                                            count=count,
                                            viewpath=STORE.find_template('bydate.html'),
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
                return DynamicContainerItem(path,
                                            str(year),
                                            contents=contents,
                                            count=yr.count,
                                            viewpath=STORE.find_template('bydate.html'),
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
                return DynamicContainerItem(path,
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
    def __init__(self):
        self._sets = {}
        self._load()        

    def _load(self):
        if os.path.exists(os.path.join(STORE.root, '_singleshot.py')):
            gl = {'ALBUMS' : self,
                  'Album' : DynamicAlbum}
            lc = {}
            execfile(os.path.join(STORE.root, '_singleshot.py'),
                     gl, lc)
        

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



