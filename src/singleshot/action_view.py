from singleshot.errors import return_404

import os
import sys

def act(actionpath, request):
    if not do_view(actionpath, request):
        return_404(actionpath, request)

def do_view(path, request):
    if path.endswith('.html'):
        path = path[:-5]
    try:
        ctxname = request.form['in']
        try:
            ctxname = ctxname.value
        except:
            pass
    except KeyError:
        ctxname = ''
    parent = None
    load_view = request.store.load_view
    if ctxname:
        parent = load_view(ctxname)
    view = load_view(path, parent=parent)
    if view:
        view.request_view(request)
    return view

        

