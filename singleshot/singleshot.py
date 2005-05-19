#!/usr/bin/env python2.3

import os
import os.path
import sys
import cgi
import cgitb
import Cookie
import traceback

# just in case
cgitb.enable()
# trick to find out where our base directory is
executedir = os.path.dirname(sys.argv[0])
sys.path.insert(0, executedir)

# next two imports are in the above-added executedir
from albums import *
from templates import create_template

sys.path.insert(1, STORE.template_root)

# create a cookie and load it if we've got one
cookie = Cookie.SimpleCookie()
try:
    cookie.load(os.environ['HTTP_COOKIE'])
except KeyError:
    pass

# load cgi vars
form = cgi.FieldStorage()

# figure out what kind of item we're handling
item = create_item(get_path_info())
if item.isdir:
    directory = item
    image = None
else:
    directory = item.album
    image = item

# if an action is specified, we should use it; if not use
# the default action
# TODO: default action should be spec'd in CONFIG
action = os.path.basename(form.getfirst('action', 'view'))


# load the correct action module
try:
    # TODO this is bogus but the unrestricted passing in of form argument
    # to import made Ken nervous and he did not want to think through a more modular
    # but safer approach at that time
    if action not in ('view', 'edit'):        
        raise 'Invalid action', 'Action is neither edit nor view (see singleshot.py): %s' % action
    actionmodule = __import__(action, globals(), locals()) 
except:
    print "Content-type: text/html\n\nNo such action: %s" % action
    print "<!-- "
    traceback.print_exc(sys.stdout)
    print "-->"
    sys.exit(0)

# invoke the action handler
actionmodule.invoke(directory, image, form, cookie)

