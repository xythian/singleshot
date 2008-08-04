
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

def template_handler(path):
    def handle(request):
        page = StaticPage(request, path)
        page.store = request.store
        return page.request_view(request)
    return handle

