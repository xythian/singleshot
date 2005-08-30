
from albums import ITEMLOADER, create_item
from ssconfig import CONFIG
from datetime import datetime
from StringIO import StringIO
import PyRSS2Gen as RSS2
import codecs
import os
import sys

def act(actionpath, form):
    absoluteurl = 'http//%s' % (os.environ['HTTP_HOST'],)
    images = [create_item(path) for path in ITEMLOADER.itemData.recent_images(10)]
    def toitem(image):
        s = StringIO()
        image.view(s, viewname='rssitem',
                   contextdata={'absoluteitemhref' : absoluteurl + image.href})
        desc = s.getvalue()
        lnk = absoluteurl + image.href
        return RSS2.RSSItem(title = image.title,
                            link = lnk,
                            description = unicode(desc),
                            guid = RSS2.Guid(lnk),
                            pubDate = datetime.fromtimestamp(image.publish_time))
    rss = RSS2.RSS2(
        title = "Ken's recent photos feed",
        link = absoluteurl,
        description = "Recently published photos from Ken Fox",
        lastBuildDate = datetime.now(),
        items = [toitem(image) for image in images]
        )
    out = codecs.getwriter('iso-8859-1')(sys.stdout)
    f = StringIO()
    rss.write_xml(f)
    s = f.getvalue()
    out.write('Content-type: %s\nContent-length: %d\n\n' % ('text/xml',
                                                                   len(s)))
    out.write(s)       
    
                                   
        

