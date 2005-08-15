#!/usr/bin/env python2.3


import sys
import os
import fnmatch
import re
import shutil
from albums import *

from ssconfig import SecurityError, STORE

def http_respond_image(path, output):
    try:
        import msvcrt
        msvcrt.setmode(output.fileno(), os.O_BINARY)
    except:
        pass

    l = os.stat(path).st_size
    output.write("Content-Type: image/jpeg\r\n")
    output.write("Content-Length: %s\r\n" % str(l))
    output.write("\r\n")
    shutil.copyfileobj(open(path, 'rb'), output)


def act(path, form):    
    ROOT, VIEW_ROOT = STORE.image_root, STORE.view_root
    size = form.getfirst('size')
    flt = form.getfirst('filter')
    
    mypath = STORE.check_path(path)
    
    if size == 'full':
        size = max(CONFIG.availableSizes)
        
    size = int(size)
    image = create_item(mypath)
    if not image or not size:
        raise SecurityError, 'Path did not map to image: %s' % mypath
    
    
    serveimage = image
    if image.width > size or image.height > size:
        serveimage = image.sizes[size]
        serveimage.ensure()
    if flt:
        serveimage = serveimage.filtered(flt=flt)
        serveimage.ensure()
    http_respond_image(serveimage.path, sys.stdout)
            
