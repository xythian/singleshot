#!/usr/bin/env python2.2

import os
import sys
import traceback

from albums import create_item
from ssconfig import STORE

from errors import return_404

def act(actionpath, form):
    path = STORE.check_path(actionpath)
    item = create_item(path)
    if item:
        view_item(item, form)
    else:
        return_404(actionpath, form)

def view_item(item, form):
    from itemcontexts import wrap_context
    item = wrap_context(item, form)
    item.cgi_view()
        

