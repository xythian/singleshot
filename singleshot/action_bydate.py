
#!/usr/bin/env python2.2

import os
import sys
import traceback

from albums import create_item
from ssconfig import STORE
from action_view import view_item
from errors import return_404

def act(actionpath, form):
    item = create_item(STORE.image_root)
    def foo(x=None):
        return STORE.find_template('bydate.html')
    item.find_view_template = foo
    item.__dict__['title'] = 'Photos by date'
    view_item(item, form)

        

