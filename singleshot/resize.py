#!/usr/bin/env python2.2

class SecurityError(Exception):
    pass

import sys
import os
executedir = os.path.dirname(sys.argv[0])
sys.path.insert(0, executedir)

import fnmatch
import re
import shutil

try:
    from albums import *
    ROOT, VIEW_ROOT = STORE.image_root, STORE.view_root
    path_info = os.environ['PATH_INFO']

    sizes = "|".join(map(lambda x: '(%s)' % x,
                         CONFIG.availableSizes + ('full',)))

    pre = re.compile('^/+(?P<size>%s)/+(?P<path>.+)' % sizes)
    m = pre.match(path_info)
    if not m:
       raise SecurityError, 'Unknown invocation does not match path regexp: %s' % path_info
    else:
       size, path = m.group('size', 'path')
       if os.path.isabs(path):
           mypath = os.path.normpath(path)
       else:
           mypath = os.path.normpath('/' + path)
    if not mypath.startswith(ROOT):
      raise SecurityError, '%s does not start with ROOT (%s)' % (mypath, ROOT)
    if size == 'full':
        size = max(CONFIG.availableSizes)

    size = int(size)

    image = create_item(mypath)
    if not image:
        raise SecurityError, 'Path did not map to image: %s' % mypath
    if image.width > size or image.height > size:
        serveimage = image.sizes[size]
        serveimage.ensure()
    else:
        serveimage = image
    
    http_respond_image(serveimage.path, sys.stdout)

except SecurityError, msg:
    print 'Content-Type: text/plain'
    print ''
    print 'Exit with security error: ', msg
    trace('resize failing with security error: %s', msg)
    raise SystemExit, 1
except:
    print 'Content-Type: text/plain'
    print ''
    import traceback
    traceback.print_exc()
