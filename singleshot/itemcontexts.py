
#
# Introduce the notion of multiple contexts an item can be in
#
from albums import ITEMLOADER, create_item, ImageItem
from properties import *
from ssconfig import STORE, CONFIG
from taltemplates import ViewableObject, ViewableContainerObject

class ContainerItemContext(object):
    def __init__(self, container, item):
        self.container = container
        self._item = item

    def _get_hasNext(self):
        return bool(self.nextItem)
    
    def _get_hasPrev(self):
        return bool(self.prevItem)


    name = virtual_readonly_property('name')
    hasNext = virtual_readonly_property('hasNext')
    hasPrev = virtual_readonly_property('hasPrev')
    nextItem = virtual_demand_property('nextItem')
    prevItem = virtual_demand_property('prevItem')

    def _get_parents(self):
        p = self.container
        while p:
            yield p
            p = p.parent

    def _get_parent(self):
        return self.container

    parents = virtual_readonly_property('parents')
    parent = virtual_readonly_property('parent')

    def _get_name(self):
        return self.container.title

    def _load_nextItem(self):
        if self.container:
            return self.container.items.nextItemFor(self._item)
        else:
            return None

    def _load_prevItem(self):
        if self.container:
            return self.container.items.prevItemFor(self._item)
        else:
            return None
    
class ItemContexts(object):
    def __init__(self, context):        
        self.contexts = []
        self.context = None

    def add(self, context):
        self.contexts.add(context)

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


class ContextWrapper(ViewableObject):
    def __init__(self, item, context, contexts):
        self._item = context._item
        self.context = context
        self.contexts = contexts
        self.find_template = context._item.find_template
        self.find_view_template = context._item.find_view_template
        self.find_macros_template = context._item.find_macros_template
        

    def create_context(self):
        context = self._item.create_context()
        context.addGlobal("contexts", self.contexts)
        context.addGlobal("context", self.context)        
        def make_crumbs():
            image_root = STORE.image_root
            urlprefix = CONFIG.url_prefix
            return Breadcrumbs(image_root, urlprefix, self._item, self.context)
        context.addGlobal("crumbs", make_crumbs())        
        return context

def wrap_context(item, form):    
    pctx = ContainerItemContext(item.parent, item)
    if not isinstance(item, ImageItem):        
        return ContextWrapper(item, pctx, [pctx])
    try:
        ctxname = form.getfirst('in')
    except KeyError:
        ctxname = ''
    if not ctxname:
        context = pctx
    else:
        context = create_item(ctxname)
        if context:
            context = ContainerItemContext(context, item)
        else:
            context = pctx
    contexts = [pctx]
    if not context in contexts:
        contexts.append(context)    
    return ContextWrapper(item, context, contexts)
    
    
