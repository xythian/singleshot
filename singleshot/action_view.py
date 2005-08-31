#!/usr/bin/env python2.2

import os
import sys
from albums import load_view
from ssconfig import STORE, CONFIG
from errors import return_404

def act(actionpath, form):
    if not do_view(actionpath, form):
        return_404(actionpath, form)

def do_view(path, form):
    if path.endswith('.html'):
        path = path[:-5]
    try:
        ctxname = form.getfirst('in')
    except KeyError:
        ctxname = ''
    parent = None
    if ctxname:
        parent = load_view(ctxname)
    view = load_view(path, parent=parent)
    if view:
        view.cgi_view()
    return view

        

