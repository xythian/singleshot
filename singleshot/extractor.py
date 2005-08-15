#!/usr/bin/python2.3

from jpeg import JpegHeader

import EXIF

data = JpegHeader('../2005/07/20D_2202037.jpg')

print data.xmp.keywords
print data.xmp.Headline

