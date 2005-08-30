#!/usr/bin/env python
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
import time

# just in case
cgitb.enable()

n = time.time()

executedir = os.path.dirname(sys.argv[0])
sys.path.insert(0, executedir)

from ssconfig import STORE, SecurityError

def main():
    form = cgi.FieldStorage()
    path = os.environ['PATH_INFO'][1:]

    try:
        slash = path.index('/')
        action = path[:slash]
        path = path[slash+1:]
    except ValueError:
        action = 'view'
        path = '/'

    actionmodule = __import__('action_' + action, globals(), locals()) 
    try:
        # invoke the action handler
        actionmodule.act(path, form)
    except SecurityError, msg:
        print 'Content-Type: text/plain'
        print ''
        print 'Exit with security error: ', msg
        sys.exit(1)

if 1:
    import hotshot, hotshot.stats
    prof = hotshot.Profile('/tmp/ss.prof')
    prof.runcall(main)
    prof.close()
else:
    main()

print >>sys.stderr, 'Render time: %s %.2fms' % (os.environ['PATH_INFO'][1:], (time.time() - n) * 1000.)


    
    


