from __future__ import nested_scopes
import imp

import sys

from simpletal import simpleTAL, simpleTALES
from simpletal.simpleTALES import PathFunctionVariable, CachedFuncResult
from simpletal.simpleTALUtils import TemplateCache, FastStringOutput

from singleshot.properties import *

from itertools import chain

TEMPLATE_CACHE = TemplateCache()

class ViewableObject(object):
    viewname = 'view'
    macrostemplate = 'macros'
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
        context = simpleTALES.Context(allowPythonPath=True)
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

def group_item(seq, n):
    l = len(seq)
    if not l:
        return
    groups = len(seq) / n
    for group in xrange(groups):
        begin = group * n
        end = group * n + n
        yield seq[begin:end]
    if groups*n < l:
        yield (seq[groups*n:] +  [None]*n)[:n]

class ViewableContainerObject(ViewableObject):
    items = ()
    
    def itemsbyrows(self, path):
        n = int(path)
        return group_item(self.items, n)

    def itemsbycolumns(self, path):
        n = int(path)
        l = len(self.items)
        n1 = l / n
        if n1 * n < l:
            n1 += 1
        n = n1
        return group_item(self.items, n)

    

    def create_context(self):
        context = super(ViewableContainerObject, self).create_context()
        context.addGlobal("itemsbyrows", PathFunctionVariable(self.itemsbyrows))
        context.addGlobal("itemsbycolumns", PathFunctionVariable(self.itemsbycolumns))        
        return context


