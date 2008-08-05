from singleshot.storage import FilesystemEntity
from singleshot.properties import ViewMeta

import time
import os
import sys
from singleshot.model import Item, ImageItem, ContainerItem
from singleshot.taltemplates import ViewableObject, ViewableContainerObject, PathFunctionVariable
from urlparse import urlsplit, urlunsplit
from singleshot.fsloader import ImageSizes

import logging
LOG = logging.getLogger('singleshot')


class Crumb(object):
    def __init__(self, link=None, item=None):
        self.link = link
        self.item = item
        self.title = item.title
        
class Breadcrumbs(object):
    def __init__(self, item, context=None):
        if not context:
            context = item
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

    def __init__(self, o, store, parent=None, load_view=None):
        self._of = o
        self.store = store
        self.config = store.config
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
        url = self.config.url_prefix + self.path[1:]
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
        context.addGlobal("lastimage", PathFunctionVariable(lambda x:self._load_view('/recent').items[0]))
        def load_lastitem(subpath):
            path = self.store.loader.recent_items(1)[0]
            if path.startswith('/album'):
                parent = None
            else:
                parent = self._load_view('/recent')
            return self._load_view(path, parent=parent)
        context.addGlobal("lastitem",  PathFunctionVariable(load_lastitem))
        context.addGlobal("ssroot",
                          PathFunctionVariable(lambda x:self.config.url_prefix +  x))
        def make_crumbs():
            return Breadcrumbs(self)
        context.addGlobal("crumbs", make_crumbs())        
        return context

    def view(self, output, viewname=None, contextdata=None):
        if viewname:
            view = self.load_template(self.store.find_template(viewname + '.html'))
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
        url = self.config.url_prefix + self.path[1:] + '.html'
        if self.ctxparent:
            url += '?in=%s' % (self.parent.path,)        
        return url
    
    def _get_image(self):
        return self

    def _get_viewpath(self):
        return self.parent.imageviewpath

    def _load_sizes(self):
        return ImageSizes(self)

    @property
    def viewbody(self):
        sv = self.sizes['view']
        if self.rawimagepath.endswith('.flv'):            
            return """<div id="videocontent"></div>
<script>
flashembed("videocontent", {src : "/static/FlowPlayerLight.swf",
                            width : %(width)d, height : %(height)d},
                           {config : {autoPlay : false, autoBuffering : true, initialScale : 'scale',
                            videoFile : "%(href)s"}});
</script>""" % {'height' : self.height, 'width' : self.width, 'href' : self.path + '.flv'}
        else:
            return '<img src="%s" height="%s" width="%s" class="thumbnail" border="0">' % (sv.href, str(sv.height), str(sv.width))


    
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
        result = []
        for path in self.contents:
            view = self._load_view(path, parent=self)
            if not view:
                LOG.warn('Path in contents returned no view: %s', path)
            else:
                result.append(view)
        items = OrderedItems(result, *orders)
        return items

    def _load_image(self):
        if self.highlightpath:
            return self._load_view(self.highlightpath).image
        else:
            for child in self.items:
                if child.image:
                    return child.image
            return None

    def view_page(self, pn):
        return ContainerPageView(self._of,
                                 self.store,
                                 page=pn,
                                 parent=self.parent,
                                 load_view=self._load_view)

class PageEntry(object):
    def __init__(self, name, current=False, href=None):
        self.name = name
        self.current = current
        self.href = href
        

class Paginator(object):
    def __init__(self, items, page, href, pagesize=24):
        self.__items = items
        self.currentpage = page
        self.pageno = page + 1
        self.count = len(items)
        self.pages = self.count / pagesize
        if self.pages * pagesize < self.count:
            self.pages += 1
        self.startitem = self.currentpage * pagesize
        self.enditem = self.startitem + pagesize
        self.items = items[self.startitem:self.enditem]
        scheme, network, path, query, fragment = urlsplit(href)
        if query:
            self.href = urlunsplit((scheme, network, path, query + '&', fragment))
        else:
            self.href = href + '?'

    def pageitems(self):
        if self.pages <= 13:
            for i in xrange(self.pages):
                current = self.currentpage == i
                yield PageEntry(str(i+1), current=current, href=self.href + 'p=%d' % i)
        elif self.currentpage <= 7:
            for i in xrange(9):
                current = self.currentpage == i
                yield PageEntry(str(i+1), current=current, href=self.href + 'p=%d' % i)
            yield PageEntry('. . .')
            for i in xrange(self.pages - 3, self.pages):
                current = self.currentpage == i
                yield PageEntry(str(i+1), current=current, href=self.href + 'p=%d' % i)
        elif self.currentpage >= (self.pages - 8):
            for i in xrange(4):
                current = self.currentpage == i
                yield PageEntry(str(i+1), current=current, href=self.href + 'p=%d' % i)
            yield PageEntry('. . .')
            for i in xrange(self.pages - 9, self.pages):
                current = self.currentpage == i
                yield PageEntry(str(i+1), current=current, href=self.href + 'p=%d' % i)
        else:
            for i in xrange(4):
                current = self.currentpage == i
                yield PageEntry(str(i+1), current=current, href=self.href + 'p=%d' % i)
            yield PageEntry('. . .')
            for i in xrange(self.currentpage - 3, self.currentpage + 3):
                current = self.currentpage == i                
                yield PageEntry(str(i+1), current=current, href=self.href + 'p=%d' % i)
            yield PageEntry('. . .')
            for i in xrange(self.pages - 3, self.pages):
                current = self.currentpage == i                
                yield PageEntry(str(i+1), current=current, href=self.href + 'p=%d' % i)


class ContainerPageView(ContainerView):
    __of__ = ContainerItem

    def __init__(self, o, store, page=None, pagesize=24, **kw):
        super(ContainerPageView, self).__init__(o, store, **kw)
        self.page = page
        self.setpagesize(pagesize)


    def _load_items(self):
        return self.paginator.items

    def setpagesize(self, path):
        p = int(path)
        self.paginator = Paginator(super(ContainerPageView, self)._load_items(), self.page, self.href, pagesize=p)

    def getpaginator(self, path):
        return self.paginator

    def create_context(self):
        context = super(ContainerPageView, self).create_context()
        # gross like cooties
        context.addGlobal('setpagesize', PathFunctionVariable(self.setpagesize))
        context.addGlobal('paginator', PathFunctionVariable(self.getpaginator))
        return context

class ViewLoader(object):
    def __init__(self, store):
        self.__store = store
        self.__load_item = store.loader.load_item

    def load_view(self, path, parent=None):
        if not path:
            path = '/'
        elif path.endswith('/') and len(path) > 1:
            path = path[:-1]
        elif path[0] != '/':
            path = '/' + path
        item = self.__load_item(path)
        return self._create_view(item, parent)

    def _create_view(self, item, parent):
        cls = ItemView
        if not item:
            return None
        elif isinstance(item, ContainerItem):
            cls = ContainerView
        elif isinstance(item, ImageItem):
            cls = ImageView
        return cls(item, self.__store, parent=parent, load_view=self.load_view)
    
        
class CachingViewLoader(ViewLoader):
    def __init__(self, store):
        super(CachingViewLoader, self).__init__(store)
        self.__cache = {}    

    def load_view(self, path, parent=None):
        if not path:
            path = '/'
        elif path.endswith('/') and len(path) > 1:
            path = path[:-1]
        elif path[0] != '/':
            path = '/' + path
        try:
            result = self.__cache[path]
            item = self.__load_item(path)
            if result._of is item:
                return result
            else:
                result = self._create_view(item, None)
                if result:
                    self.__cache[path] = result            
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
            return super(CachingViewLoader, self).load_view(path, parent=parent)


def init_orders():
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
