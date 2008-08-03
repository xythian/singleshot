from singleshot.errors import return_404
import sys
import os

def act(path, request):
    size = request.getfirst('size')
    if size == 'full':
        # todo: this should just redirect, so the image gets cached
        size = max(request.config.availableSizes)
        
    size = int(size)
    image = request.store.load_view('/' + path[:-4])    
    if not image or not size:
        return return_404(path, request)
    
    serveimage = image
    path = image.rawimagepath
    if image.width > size or image.height > size:
        serveimage = image.sizes[size]
        serveimage.ensure()
        path = serveimage.path
    request.respond_file(path, 'image/jpeg')
            
