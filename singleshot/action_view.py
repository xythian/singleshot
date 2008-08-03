from singleshot.errors import return_404
from singleshot import pages

import os
import sys

def act(actionpath, request):
    if actionpath.startswith('/'):
        actionpath = actionpath[1:]
    if actionpath.endswith('/'):
        actionpath = actionpath[:-1]    
    if do_view(actionpath, request):
        return
    try:
        pathsegments = actionpath.split('/')
        actionname = pathsegments[0]
        actionmodule = request.find_action(actionname)
        restpath = '/'.join(pathsegments[1:])
        actionmodule.act(restpath, request)
        return
    except ImportError:
        pass    
    return_404(actionpath, request)

def do_view(path, request):
    if path.endswith('.html'):
        path = path[:-5]
    ctxname = request.getfirst('in')
    pn = request.getfirst('p')
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
        view = pages.create(request, path)
    if not view:
        return view    
    elif hasattr(view, 'view_page'):
        view = view.view_page(pn)
    view.request_view(request)
    return view

        

