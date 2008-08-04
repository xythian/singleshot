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
from StringIO import StringIO
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

def wrapzor(handlers, wrap):
    h = iter(handlers)
    while True:
        yield h.next()
        yield wrap(h.next())

VERSION = pkg_resources.get_distribution('singleshot').version

def create_404_image():
    msg = Image.new("RGB", (100, 20), (0, 0, 0))
    draw = ImageDraw.Draw(msg)
    draw.text((5, 5), "404 Not found", fill=(255, 255, 255))
    del draw
    f = StringIO()
    msg.save(f, "JPEG")
    del msg
    app = DataApp(content=f.getvalue(), content_type='image/jpeg')
    app.cache_control(public=True, max_age=86400*36500)
    return app

IMAGE_404 = create_404_image()

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

def image_handler(request):
    path, size = request.urlmatch.group('path', 'size')
    if not size:
        size = '1200'
    size = int(size)
    image = request.store.load_view(path)
    if not image or not size:
        return request.wsgi_pass(IMAGE_404)
    serveimage = image
    path = image.rawimagepath
    if image.width > size or image.height > size:
        serveimage = image.sizes[size]
        serveimage.ensure()
        path = serveimage.path
    if image.width > size or image.height > size:
        serveimage = image.sizes[size]
        serveimage.ensure()
        path = serveimage.path
    return request.wsgi_pass(FileApp(path))

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
        return create_handler(os.path.join(request.store.root, 'templates'), '404')
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
            
def create(store=None, middleware=(), error_handler=shotweb.debug_error_handler):
    # TODO: pre-load pages/ and static/ for pages
    urls = (
        r'/(?P<static>static/.+)', static_handler,
        r'(?P<path>.+?)(-(?P<size>[0-9]+))?\.jpg', image_handler,
        r'(?P<path>.+)\.html', view_handler,
        r'(?P<path>.+)', view_handler
    )

    # insert handlers for each other action

    urls = list(page_handlers(os.path.join(store.root, 'pages'))) + list(urls)
    for name, act in actions.load_actions().items():
        urls.insert(0, act)
        urls.insert(0, r'/%s(/(?P<path>.+))?' % name)

    urls = wrapzor(urls, store_wrapper(store))
    
    ui_app = shotweb.create_application(urls, requestType=UIRequest, error_handler=error_handler, middleware=middleware)

    return ui_app
    

def configure_debug_logging():
    hdlr = logging.StreamHandler(sys.stderr)
    rl = logging.getLogger()
    rl.addHandler(hdlr)
    fmt = logging.Formatter('[%(name)s/%(asctime)s/%(levelname)s] %(message)s')
    hdlr.setFormatter(fmt)
    rl.setLevel(logging.DEBUG) 

def serve_http(store=None, addr='', port=8080, configure_logging=configure_debug_logging):
    configure_logging()
    from wsgiref.simple_server import make_server, demo_app
    application = create(store)
    application = shotweb.time_request()(application)
    server = make_server(addr, port,  application)
    server.serve_forever()
