#
# Handles 'files' that are figments of Singleshot's imagination
#

from singleshot.errors import return_404
from singleshot.action_view import do_view
import os
import sys

def act(path, request):
    realpath = path
    if do_view(path, request):
        return
    try:
        path = path[1:]
        slash = path.index('/')
        action = path[:slash]
        path = path[slash+1:]
    except ValueError:
        return return_404(realpath, request)
    try:
        actionmodule = request.find_action(action)
    except ImportError:
        return return_404(realpath, request)

    # invoke the action handler
    actionmodule.act(path, request)
    
    
