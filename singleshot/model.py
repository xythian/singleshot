from ssconfig import CONFIG, STORE, read_config
from jpeg import JpegHeader, parse_exif_date, load_exif, calculate_box
from storage import FilesystemEntity
from properties import ViewMeta, AutoPropertyMeta
import imageprocessor
import time
import os

MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']

class Item(object):
#    __metaclass__ = AutoPropertyMeta
    
    "Basic properties of an item"
    iscontainer = False
    path = ''           # the logical path to this item
    title = ''
    caption = ''
    publish_time = None    # the time an image is considered 'published'

class Location(object):
#    __metaclass__ = ModelMeta    
    "Represents a location"

    name = None
    city = None
    state = None
    postal = None
    latitude = None
    longitude = None

class ContainerItem(Item):
    __metaclass__ = AutoPropertyMeta
    "Meta information about a Container"
    order = 'dir,-publishtime'
    highlightpath = ''  # the highlight image path

    iscontainer = True
    viewpath = ''       # path to view template to use
    imageviewpath = ''  # path to view template for a photo in this album

    def _get_count(self):
        return len(contents)

    contents = ()

class DynamicContainerItem(ContainerItem):
    __metaclass__ = AutoPropertyMeta

    __contents = ()
    __contentsfunc = None

    def __init__(self, path, title, count=-1, contents=None, contentsfunc=None, pt=None, viewpath='', imageviewpath='', order=None, caption='', highlightpath=''):
        self.path = path
        self.title = title
        if highlightpath:
            self.highlightpath = highlightpath
        if pt:
            self.publish_time = pt
        else:
            self.publish_time = time.time()
        if order != None:
            self.order = order
        self.__count = count
        self.caption = caption
        if contentsfunc:
            self.__contentsfunc = contentsfunc
        else:
            self.__contents = contents
        if viewpath:
            self.viewpath = viewpath
        else:
            self.viewpath = STORE.find_template('album.html')
        if imageviewpath:
            self.imageviewpath = imageviewpath
        else:
            self.imageviewpath = STORE.find_template('view.html')

    def _get_count(self):
        if self.__count > -1:
            return self.__count
        else:
            return len(self.contents)

    def _load_contents(self):
        if self.__contentsfunc:
            return self.__contentsfunc()
        else:
            return self.__contents

class ImageItem(Item):
    "Meta information about an image"
    
    keywords = ()
    height = 0
    width = 0
    rawimagepath = ''      # a filesystem path, relative to STORE.root

    filename = ''
    viewfilepath = ''

    capture_time = None    # datetime image was captured
    camera_name = None
    exposure_time = None   # 
    aperture = None

    capture_location = None




