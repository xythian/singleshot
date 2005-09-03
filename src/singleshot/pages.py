
#
# "static" pages
#

from singleshot.taltemplates import ViewableObject, PathFunctionVariable

import os
import imp

from os.path import join, exists

class StaticPage(ViewableObject):
    viewname = 'message'
    
    def __init__(self, request, viewpath=None, **other):
        self.form = request.form
        self.__viewpath = viewpath
        self.other = other


    def find_view_template(self, name='view'):
        return self.__viewpath
    
    def create_context(self):        
        context = super(StaticPage, self).create_context()
        config = self.store.config
        context.addGlobal("form", self.form)
        context.addGlobal("ssroot", PathFunctionVariable(lambda x:config.url_prefix + x))
        for key, val in self.other.items():
            context.addGlobal(key, val)
        return context

class StaticModule(object):
    def __init__(self, path, pypath, request):
        self.path = path
        self.pypath = pypath
        self.request = request

    def load_module(self):
        f = open(self.pypath, 'U')
        try:
            return imp.load_source('staticmodule', self.pypath, f)
        finally:
            f.close()

    def request_view(self, request, viewname=None):
        module = self.load_module()
        module.act(self.path, self.request)

def create(request, actionpath):
    store = request.store
    if actionpath.startswith('/'):
        actionpath = actionpath[1:]
    if actionpath.endswith('/'):
        actionpath = actionpath[:-1]
    pathsegments = actionpath.split('/')
    restpath = '/'.join(pathsegments[1:])
    pagename = pathsegments[0]
    for root in (store.page_root, store.static_root):
        htmlpath = join(root, pagename + '.html')
        pypath = join(root, pagename + '.py')                
        if exists(htmlpath):
            item = StaticPage(request, htmlpath)
            item.store = store
            return item
        elif exists(pypath):
            return StaticModule(restpath, pypath, request)
    return None
    
