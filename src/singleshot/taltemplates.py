from __future__ import nested_scopes
import imp

import sys

from simpletal import simpleTAL, simpleTALES
from simpletal.simpleTALES import PathFunctionVariable, CachedFuncResult
from simpletal.simpleTALUtils import TemplateCache, FastStringOutput

from singleshot.properties import *

TEMPLATE_CACHE = TemplateCache()

class ViewableObject(object):
    viewname = 'view'
    macrostemplate = 'page'
    http_status = ''
    
    def load_template(self, path):
        if not path:
            return None
        return TEMPLATE_CACHE.getTemplate(path)

    def find_template(self, name):
        return self.store.find_template(name + '.html')        

    def find_view_template(self):        
        return self.find_template(self.viewname)

    def find_macros_template(self):
        return self.find_template(self.macrostemplate)

        

    def create_context(self):
        context = simpleTALES.Context()
        context.addGlobal("macros",
                          self.load_template(self.find_macros_template()))        
        return context


    def view(self, output, viewname=None, contextdata=None):
        if not viewname:
            viewpath = self.find_view_template()
        else:
            viewpath = self.find_template(viewname)            
        view = self.load_template(viewpath)
        context = self.create_context()
        if contextdata:
            for key, val in contextdata.items():
                context.addGlobal(key, val)
        view.expand(context, output)

    content_type = 'text/html'

    def request_view(self, request, **kw):
        f = FastStringOutput()
        self.view(f, **kw)
        s = f.getvalue()
#        if self.http_status:
#            output.write("Status: %s\n" % self.http_status)
        request.content_type = self.content_type
        request.content_length = len(s)
        request.send_headers()
        request.write(s)

        

class ViewableContainerObject(ViewableObject):
    items = ()
    
    def itemsbyrows(self, path):
        n = int(path)
        hasmore = [True]
        it = iter(self.items)
        def row(g, i):
            for x in xrange(i):
                try:
                    yield g.next()
                except StopIteration:
                    hasmore[0] = False
                    yield None
        while hasmore[0]:
            yield row(it, n)

    def itemsbycolumns(self, path):
        n = int(path)
        hasmore = [True]
        l = len(self.items)
        n1 = l / n
        if n1 * n < l:
            n1 += 1
        n = n1
        it = iter(self.items)
        def row(g, i):
            for x in xrange(i):
                try:
                    yield g.next()
                except StopIteration:
                    hasmore[0] = False
                    yield None
        while hasmore[0]:
            yield row(it, n)
        

    def create_context(self):
        context = super(ViewableContainerObject, self).create_context()
        context.addGlobal("itemsbyrows", PathFunctionVariable(self.itemsbyrows))
        context.addGlobal("itemsbycolumns", PathFunctionVariable(self.itemsbycolumns))        
        return context
