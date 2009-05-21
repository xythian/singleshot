import PyRSS2Gen as RSS2

from datetime import datetime
from StringIO import StringIO
from xml.sax import saxutils
import codecs
import os
import sys

def handle(request):
    load_view = request.store.load_view
    config = request.store.config.config
    rsstitle = config.get('feed', 'title')
    rssdesc = config.get('feed', 'description')
    rsscount = int(config.get('feed', 'recentcount'))

    store = request.store
    items = [load_view(path) for path in store.loader.recent_items(rsscount)]
    
    def toitem(image):
        s = StringIO()
        image.view(s, viewname='rssitem',
                   contextdata={'absoluteitemhref' : request.full_url(image.href)})
        try:
            desc = unicode(s.getvalue())
        except:
            desc = ''
        lnk = request.full_url(image.href)
        return RSS2.RSSItem(title = image.title,
                            link = lnk,
                            description = unicode(desc),
                            guid = RSS2.Guid(lnk),
                            pubDate = image.publish_time)
    rss = RSS2.RSS2(
        title = rsstitle,
        link = request.full_url('/'),
        description = rssdesc,
        lastBuildDate = datetime.now(),
        items = [toitem(image) for image in items]
        )
    f = StringIO()    
    out = codecs.getwriter('iso-8859-1')(f)
    handler = saxutils.XMLGenerator(f)
    handler.startDocument()
    handler.processingInstruction('xml-stylesheet', 'type="text/xsl" href="%s"' % (request.full_url('/static/rssformat.xsl')))
    rss.publish(handler)
    handler.endDocument()
    s = f.getvalue()
    request.content_type = 'text/xml'
    request.write(s)
    
                                   
        

