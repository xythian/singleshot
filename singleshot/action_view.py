#!/usr/bin/env python2.2

import os
import os.path
import sys
import cgi
import cgitb
import Cookie
import traceback

from albums import *
from taltemplates import write_template
from ssconfig import STORE

def act(path, form):
    # create a cookie and load it if we've got one
    cookie = Cookie.SimpleCookie()
    try:
        cookie.load(os.environ['HTTP_COOKIE'])
    except KeyError:
        pass
    path = STORE.check_path(path)
    item = create_item(path)
    if item.isdir:
        tmplname = 'album'
    else:
        tmplname = 'view'
    print 'Content-type: text/html'
    print
    write_template(templatekey=tmplname, item=item)
        

def invoke(dir, item, form):
    if item:
        tmplname = 'view'
    else:
        tmplname = 'album'
    if dir and not item:
        item = dir
    print 'Content-type: text/html'
    print
    write_template(templatekey=tmplname, item=item)

