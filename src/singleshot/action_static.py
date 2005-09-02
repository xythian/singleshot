
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
    root = store.static_root
    htmlpath = join(root, actionpath + '.html')
    pypath = join(root, actionpath + '.py')
    if actionpath.endswith('/'):
        actionpath = actionpath[:-1]

    if exists(htmlpath):
        item = StaticPage(request, htmlpath)
        item.store = store
        return item
    elif exists(pypath):
        return StaticModule(actionpath, pypath, request)
    return None
    

def act(actionpath, request):
    item = create(request, actionpath)
    if item:
        item.request_view(request)
    else:
        # do this here to avoid circular import...
        from singleshot.errors import return_404                
        return_404(actionpath, request)
