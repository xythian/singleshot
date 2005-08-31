from ssconfig import CONFIG, STORE, read_config
from jpeg import JpegHeader, parse_exif_date, load_exif, calculate_box
from storage import FilesystemEntity
from properties import ViewMeta
import fsloader
import imageprocessor
import time
import os
from model import Item, ImageItem, ContainerItem
from taltemplates import ViewableObject, ViewableContainerObject, PathFunctionVariable

IMAGESIZER = imageprocessor.select_processor()


class Crumb(object):
    def __init__(self, link=None, item=None):
        self.link = link
        self.item = item
        self.title = item.title
        
class Breadcrumbs(object):
    def __init__(self, fsroot, urlprefix, item, context):        
        self.crumbs = [Crumb(item=item, link=item.href)]
        for item in context.parents:
            self.crumbs.append(Crumb(item=item, link=item.href))
        self.crumbs.reverse()
    
    def _get_parents(self):
        return self.crumbs[:-1]
    
    def _get_current(self):
        return self.crumbs[-1]
    
    parents = property(_get_parents)
    current = property(_get_current)


class ItemView(object):
    __metaclass__ = ViewMeta
    __of__ = Item

    parent = None
    ctxparent = False

    def __init__(self, o, parent=None, load_view=None):
        self._of = o
        self._load_view = load_view
        calcparent = self.path[:self.path.rindex('/')]
        if not calcparent:
            calcparent = '/'
        if parent:
            self.parent = parent
            if parent and (parent.path != calcparent):
                self.ctxparent = parent
        else:
            if self.path != '/':
                self.parent = load_view(calcparent)
    def _get_parents(self):
        p = self.parent
        while p:
            yield p
            p = p.parent
        
    def _get_href(self):
        url = CONFIG.url_prefix + self.path[1:]
        if self.ctxparent:
            url += '?in=%s' % (self.parent.path,)
        return url

    def _get_image(self):
        return None

    def _load_nextItem(self):
        if self.parent:
            return self.parent.items.nextItemFor(self)
        return None

    def _load_prevItem(self):
        if self.parent:
            return self.parent.items.prevItemFor(self)
        return None

    def _get_name(self):
        return self.title

    def create_context(self):
        context = super(ItemView, self).create_context()
        context.addGlobal("item", self)
        def pathloader(path):
            return self._load_view('/' + path)
        context.addGlobal("title", self.title)
        context.addGlobal("data", PathFunctionVariable(pathloader))
        context.addGlobal("lastimage", PathFunctionVariable(lambda x:self._load_view('/recent/1').items[0]))
        context.addGlobal("ssuri",
                          PathFunctionVariable(lambda x:CONFIG.ssuri + '/' + x))
        context.addGlobal("ssroot",
                          PathFunctionVariable(lambda x:CONFIG.url_prefix +  x))
        def make_crumbs():
            image_root = STORE.image_root
            urlprefix = CONFIG.url_prefix
            return Breadcrumbs(image_root, urlprefix, self, self)
        context.addGlobal("crumbs", make_crumbs())        
        return context

    def view(self, output, viewname=None, contextdata=None):
        if viewname:
            view = self.load_template(STORE.find_template(viewname + '.html'))
        else:
            view = self.load_template(self.viewpath)
        context = self.create_context()
        if contextdata:
            for key, val in contextdata.items():
                context.addGlobal(key, val)
        view.expand(context, output)
    


class ImageView(ItemView, ViewableObject):
    __of__ = ImageItem

    def _get_href(self):
        url = CONFIG.url_prefix + self.path[1:] + '.html'
        if self.ctxparent:
            url += '?in=%s' % (self.parent.path,)        
        return url
    
    def _get_image(self):
        return self

    def _get_viewpath(self):
        return self.parent.imageviewpath

    def _load_sizes(self):
        return fsloader.ImageSizes(self)


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
        assert None not in items
        if orders:
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

class ContainerView(ItemView, ViewableContainerObject):
    __of__ = ContainerItem
        
    def _load_items(self):
        if not self.order:
            orders = ()
        else:
            orders = self.order.split(',')
            orders = [ORDERS[order] for order in orders]
        items = OrderedItems([self._load_view(path, parent=self) for path in self.contents],
                             *orders)
        return items

    def _load_image(self):
        if self.highlightpath:
            return self._load_view(self.highlightpath).image
        else:
            for child in self.items:
                if child.image:
                    return child.image
            return None

import sys

class ViewLoader(object):
    def __init__(self, loaditem):
        self.__cache = {}
        self.__load_item = loaditem

    def _load_view(self, path, parent=None):
        item = self.__load_item(path)
        if not item:
            return None
        elif isinstance(item, ContainerItem):
            return ContainerView(item, parent=parent, load_view=self.load_view)
        elif isinstance(item, ImageItem):
            return ImageView(item, parent=parent, load_view=self.load_view)
        else:
            return ItemView(item, parent=parent, load_view=self.load_view)

    def load_view(self, path, parent=None):
        if not path:
            path = '/'
        elif path.endswith('/') and len(path) > 1:
            path = path[:-1]
        elif path[0] != '/':
            path = '/' + path
        try:
            result = self.__cache[path]
        except KeyError:
            result = self._load_view(path)
            self.__cache[path] = result
        if not result:
            return None
        elif not parent:
            return result
        elif result.parent == parent.path:
            return result
        else:
            return self._load_view(path, parent=parent)


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
              'dir'   : lambda x,y:cmp(x.iscontainer, y.iscontainer),
              'name'  : lambda x,y:cmp(x.name, y.name),
              'mtime' : lambda x,y:cmp(x.publish_time,y.publish_time),
              'publishtime' : lambda x,y:cmp(x.publish_time,y.publish_time)}

    for key, item in ORDERS.items():
        ORDERS['-' + key] = reverse(item)
    return ORDERS

ORDERS = init_orders()
