#!/usr/bin/env python2.3


import sys
import os
import fnmatch
import re
import shutil
from albums import *

from errors import return_404
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
    
    if size == 'full':
        size = max(CONFIG.availableSizes)
        
    size = int(size)
    image = create_item('/' + path[:-4])    
    if not image or not size:
        return return_404(path, form)
    
    serveimage = image
    path = image.rawimagepath
    if image.width > size or image.height > size:
        serveimage = image.sizes[size]
        serveimage.ensure()
        path = serveimage.path
    if flt:
        serveimage = serveimage.filtered(flt=flt)
        serveimage.ensure()
        path = serveimage.path        
    http_respond_image(path, sys.stdout)
            
