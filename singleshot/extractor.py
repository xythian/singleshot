#!/usr/bin/python2.3

from jpeg import JpegHeader, JpegImage
import time

import EXIF

#data = JpegHeader('../2005/07/20D_2202037.jpg')
#data = JpegHeader('../2000/10/106_0688_IMG.jpg')
#data = JpegHeader('../1989/abby_3_89_3.jpg')
#data = JpegHeader('../2004/10/_MG_0801.jpg')
#print data.xmp.keywords
#print data.xmp.Headline
#print data.xmp.DateCreated
#print dir(data.xmp)
#data = JpegImage('../2004/10/_MG_0801.jpg')
#data = JpegImage('../2004/05/CRW_2020241.jpg')
#print data._exif['EXIF DateTimeDigitized']
#print data.xmp

from albums import ITEMLOADER

def main():
    from albums import ITEMLOADER
    data =ITEMLOADER.itemData

def main():
    from albums import ITEMLOADER
    data = ITEMLOADER.itemData
    data.query(['publish:2004'])
    data.query(['publish:2003', 'dog'])
    data.query(['publish:2002'])


def warmup():
    data = ITEMLOADER.itemData
    data.query(['publish:2004'])


if 1:
    warmup()
    import hotshot, hotshot.stats
    prof = hotshot.Profile('load4.prof')
    prof.runcall(main)
    prof.close()
    stats = hotshot.stats.load('load4.prof')
    stats.strip_dirs()
    stats.sort_stats('time', 'calls')
    stats.print_stats(20)
else:
    main()

