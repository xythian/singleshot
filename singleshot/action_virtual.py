#
# Handles 'files' that are figments of Singleshot's imagination
#

from ssconfig import CONFIG
from albums import create_item
from errors import return_404
from action_view import view_item
import os


def act(path, form):
    realpath = path
    if path.startswith(CONFIG.url_prefix):
        path = path[len(CONFIG.url_prefix):]
    if not os.path.exists('/' + path):
        item = create_item('/' + path)
        if item:
            view_item(item, form)
    try:
        slash = path.index('/')
        action = path[:slash]
        path = path[slash+1:]
    except ValueError:
        return return_404(realpath, form)

    try:
        actionmodule = __import__('action_' + action, globals(), locals())
    except ImportError:
        return return_404(realpath, form)

    # invoke the action handler
    actionmodule.act(path, form)
    
    
