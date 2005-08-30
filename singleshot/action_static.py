
#
# "static" pages
#

from taltemplates import ViewableObject, PathFunctionVariable
from ssconfig import STORE, CONFIG
import os
import imp

class StaticPage(ViewableObject):
    viewname = 'message'
    
    def __init__(self, form, viewpath=None, **other):
        self.form = form
        self.__viewpath = viewpath
        self.other = other


    def find_view_template(self, name='view'):
        return self.__viewpath
    
    def create_context(self):
        context = super(StaticPage, self).create_context()
        context.addGlobal("form", self.form)
        context.addGlobal("config", CONFIG)
        context.addGlobal("ssuri", PathFunctionVariable(lambda x:CONFIG.ssuri + '/' + x))
        context.addGlobal("ssroot", PathFunctionVariable(lambda x:CONFIG.url_prefix + x))
        for key, val in self.other.items():
            context.addGlobal(key, val)
        return context

def exists(actionpath):
    if actionpath.endswith('/'):
        actionpath = actionpath[:-1]
    if os.path.exists(os.path.join(STORE.static_root, actionpath + '.html')):
        return True
    elif os.path.exists(os.path.join(STORE.static_root, actionpath + '.py')):
        return True
    else:
        return False
    

def act(actionpath, form):
    if actionpath.endswith('/'):
        actionpath = actionpath[:-1]
    if os.path.exists(os.path.join(STORE.static_root, actionpath + '.html')):
        item = StaticPage(form, os.path.join(STORE.static_root, actionpath + '.html'))
        item.cgi_view()
    elif os.path.exists(os.path.join(STORE.static_root, actionpath + '.py')):
        path = os.path.join(STORE.static_root, actionpath + '.py')
        f = open(path, 'U')
        try:
            m = imp.load_source('staticmodule', path, f)
            m.act(actionpath, form)
        finally:
            f.close()
    else:
        from errors import return_404        
        return_404(actionpath, form)
