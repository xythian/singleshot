#!/usr/bin/env python2.3
#


#
# A single entry point for Singleshot CGI
#

#
# Interface: sscgi.py/action/...args...
#

import os
import sys
import cgi
import cgitb
import traceback

# just in case
cgitb.enable()

from ssconfig import SecurityError



# update our path with the execution directory and the zpt.zip library stored within
executedir = os.path.dirname(sys.argv[0])
sys.path.insert(0, executedir)
from ssconfig import STORE
sys.path.insert(1, os.path.join(STORE.ss_root, 'simpletal-3.13.zip'))  # SimpleTAL

form = cgi.FieldStorage()
path = os.environ['PATH_INFO'][1:]

try:
    slash = path.index('/')
    action = path[:slash]
    path = path[slash+1:]
except ValueError:
    action = 'view'
    path = '/'

# load the correct action module
try:
    # TODO this is bogus but the unrestricted passing in of form argument
    # to import made Ken nervous and he did not want to think through a more modular
    # but safer approach at that time
    actionmodule = __import__('action_' + action, globals(), locals()) 
except:
    print "Content-type: text/html\n\nNo such action: %s" % action
    print "<!-- "
    traceback.print_exc(sys.stdout)
    print "-->"
    sys.exit(0)

try:
    # invoke the action handler
    actionmodule.act(path, form)
except SecurityError, msg:
    print 'Content-Type: text/plain'
    print ''
    print 'Exit with security error: ', msg
    sys.exit(1)
    


    
    


