from __future__ import with_statement
import time
from datetime import date, datetime
import os
import logging
import shotweb
from shotlib.util import copyinfo
from Cookie import SimpleCookie
import pytz
from PIL import Image, ImageDraw

import time
import sys
import re
from itertools import chain
import mimetypes

import pkg_resources
from shotweb import WSGIRequest as UIRequest

import imp
from singleshot import actions, pages

#
# shortcut to get this working
#
from paste.httpheaders import CACHE_CONTROL, IF_NONE_MATCH, IF_MODIFIED_SINCE, ETAG, CONTENT_DISPOSITION, LAST_MODIFIED
from paste.fileapp import FileApp, DataApp

VERSION = pkg_resources.get_distribution('singleshot').version


#
# Create an app to serve singleshot, built on shotweb only
# Try to reduce dependency on the relatively hairy rewrite rules at the expense of doing more
# in python rather than Apache.  This is also necessary to have access rules...
#

#
# image fetch/resize requests
#   /path/to/image.jpg     
#   /path/to/image-nnn.jpg
# item view request
#   /path/to
#   /path/to/image.html
#
#
# root/
#     static/ -- static files
#     templates/ -- templates
#     view/ -- generated files
#     pages/ -- pages
#      
#

def store_wrapper(store):
    def _wrap(app):
        @copyinfo(app)
        def _wrapped(request):
            request.store = store
            request.store.full_href = request.full_path
            return app(request)
        return _wrapped
    return _wrap

def static_handler(request):
    path = request.urlmatch.group('static')
    # TODO: fix security checks, maybe preload static?
    target_path = os.path.normpath(os.path.join(request.store.root, path))
    app = FileApp(target_path)
    app.cache_control(public=True, max_age=3600)
    return request.wsgi_pass(app)

def view_handler(request):
    path = request.urlmatch.group('path')
    ctxname = request.form.getfirst('in')
    pn = request.form.getfirst('p')
    if not pn:
        pn = 0
    else:
        pn = int(pn)
    parent = None
    load_view = request.store.load_view
    if ctxname:
        parent = load_view(ctxname)
    view = load_view(path, parent=parent)
    if not view:
        return create_handler(os.path.join(request.store.root, 'templates'), '404')(request)
    if hasattr(view, 'view_page'):
        view = view.view_page(pn)
    return view.request_view(request)

def path_act(target):
    def handle(request):
        return target(request.urlmatch.group('path'), request)
    return handle

def create_handler(path, name):
    target_path = os.path.join(path, name)
    if os.path.exists(target_path + '.py'):
        f = open(target_path, 'U')
        try:
            target = imp.load_source('singleshotstatic%s' % name, target_path, f)
        finally:
            f.close()
        return path_act(target.act)
    else:
        return pages.template_handler(target_path + '.html')

def page_handlers(path):
    for item in os.listdir(path):
        name, ext = os.path.splitext(item)
        target_path = os.path.join(path, item)
        if ext == '.py':
            f = open(target_path, 'U')
            try:
                target = imp.load_source('singleshotstatic%s' % name, target_path, f)
            finally:
                f.close()
            yield r'/%s(/(?P<path>.*))?' % name
            yield path_act(target.act)
        elif ext == '.html':
            yield r'/%s(/(?P<path>.*))?' % name
            yield pages.template_handler(target_path)

def create_handlers(store=None):
    # TODO: pre-load pages/ and static/ for pages
    urls = [r'/(?P<static>static/.+)', static_handler]
    urls.extend(store.handler.url_handlers())
    urls.extend((
        r'(?P<path>.+)\.html', view_handler,
        r'(?P<path>.+)', view_handler
    ))

    # insert handlers for each other action

    urls = list(page_handlers(os.path.join(store.root, 'pages'))) + list(urls)
    for name, act in actions.load_actions().items():
        urls.insert(0, act)
        urls.insert(0, r'/%s(/(?P<path>.+))?' % name)
    return shotweb.wrap_handlers(urls, store_wrapper(store))
    
            
def create(store=None, middleware=(), error_handler=shotweb.debug_error_handler):
    urls = create_handlers(store=store)
    ui_app = shotweb.create_application(urls, requestType=UIRequest, error_handler=error_handler, middleware=middleware)
    return ui_app
    

def configure_debug_logging():
    hdlr = logging.StreamHandler(sys.stderr)
    rl = logging.getLogger()
    rl.addHandler(hdlr)
    fmt = logging.Formatter('[%(name)s/%(asctime)s/%(levelname)s] %(message)s')
    hdlr.setFormatter(fmt)
    rl.setLevel(logging.WARNING) 

def serve_http(store=None, addr='', port=8080, configure_logging=configure_debug_logging):
    configure_logging()
    from wsgiref.simple_server import make_server, demo_app
    application = create(store)
    application = shotweb.time_request()(application)
    server = make_server(addr, port,  application)
    server.serve_forever()
