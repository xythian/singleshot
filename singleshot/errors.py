from singleshot.taltemplates import ViewableObject
from singleshot import pages

from simpletal.simpleTALES import PathFunctionVariable

import sys

class MessagePage(ViewableObject):
    viewname = 'message'
    
    def __init__(self, request, **other):
        self.path = request.uri
        self.store = request.store
        self.config = request.store.config
        self.form = request.form
        self.other = other
        
    def create_context(self):
        context = super(MessagePage, self).create_context()
        config = self.config
        context.addGlobal("form", self.form)
        context.addGlobal("config", self.config)
        context.addGlobal("ssroot", PathFunctionVariable(lambda x:self.store.full_href(x)))
        for key, val in self.other.items():
            context.addGlobal(key, val)
        return context

class PageNotFound(MessagePage):
    viewname = '404'
    http_status = '404 Not Found'


def return_404(path, request):
    page = pages.create(request, '404')
    if not page:
        page = PageNotFound(request, path=request.uri)
    return page.request_view(request)
