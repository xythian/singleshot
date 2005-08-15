from __future__ import nested_scopes
import os
import fnmatch
import sys
import EXIF
import re
import struct
from ConfigParser import ConfigParser
from jpeg import JpegHeader
from properties import *
from albums import *
import imp

from simpletal import simpleTAL, simpleTALES
from simpletal.simpleTALES import PathFunctionVariable

def load_template(path):
    f = open(path, 'rt')
    try:
        return simpleTAL.compileXMLTemplate(f)
    finally:
        f.close()
    

def write_template(templatekey='view', item=None):
#     filename = directory.config.get('templates', templatekey)
#     tmplfile = STORE.find_template(filename)
     context = simpleTALES.Context()
     page = load_template(STORE.find_template('page.html'))
     context.addGlobal("macros", page)

     def rows(it, n):
         hasmore = [True]
         def row(g, i):
             for x in xrange(i):
                 try:
                     yield g.next()
                 except StopIteration:
                     hasmore[0] = False
                     yield None
         while hasmore[0]:
             yield row(it, n)
         raise StopIteration

     context.addGlobal("item", item)
     if item.isdir:
         context.addGlobal("directory", item)
         context.addGlobal("image", None)
         context.addGlobal("rows", rows(iter(item.items), 3))
     else:
         context.addGlobal("directory", item.parent)
         context.addGlobal("image", item)

     def make_crumbs():
         path = item.path
         image_root = STORE.image_root
         path = path[len(image_root)+1:]
         urlprefix = CONFIG.url_prefix
         return Breadcrumbs(image_root, urlprefix, path)
     context.addGlobal("crumbs", make_crumbs())
     context.addGlobal("title", item.title)
     context.addGlobal("ssuri", PathFunctionVariable(lambda x:CONFIG.ssuri + '/' + x))
     context.addGlobal("ssroot", PathFunctionVariable(lambda x:CONFIG.url_prefix +  x))

     
     
     view = load_template(STORE.find_template(templatekey + '.html'))

     view.expand(context, sys.stdout)
    

class AlbumPageTemplate(Cheetah.Template.Template):
    def __init__(self, directory=None, image=None, **kw):
        # le sigh, new style properties don't work
        # on CHeetah.Template .. because it's not a new-style
        # type
        if image:
             self.item = image
        else:
             self.item = directory
        self.url_prefix = self._get_url_prefix()
        self.ssuri = self._get_ssuri()
        self.path = self._load_path()
        self.crumbs = self._load_crumbs()
        self.directory = directory
        self.image = image
        Cheetah.Template.Template.__init__(self, **kw)

    def imgForSize(self, size, clss=''):
         altT = size.image.title
         if clss:
              clss = ' class="%s"' % clss         
         return '<img src="%s" height="%s" width="%s" alt="%s"%s>' % (size.href,
                                                                    size.height,
                                                                    size.width,
                                                                    altT,
                                                                    clss)
                                                                    

    def _includeCheetahSource(self, srcArg, trans=None,
                              includeFrom='file', raw=False, _includeID=None):
         if includeFrom == 'file':
              srcArg = STORE.find_template(srcArg)
         sclass = Cheetah.Template.Template
         return sclass._includeCheetahSource(self,
                                             srcArg,
                                             trans=trans,
                                             includeFrom=includeFrom,
                                             raw=raw,
                                             _includeID=_includeID)
    def hasCrumbs(self):
	return bool(self.crumbs.parents);

    def _load_crumbs(self):
        path = self.path
        image_root = STORE.image_root
        path = path[len(image_root)+1:]
        urlprefix = CONFIG.url_prefix
        return Breadcrumbs(image_root, urlprefix, path)

    def _get_url_prefix(self):
        return CONFIG.url_prefix

    def _get_ssuri(self):
        return CONFIG.ssuri

    def _load_path(self):
        return get_path_info()

    def _load_item(self):
        return create_item(self.path)
