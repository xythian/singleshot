from datetime import datetime
from StringIO import StringIO

from xml.etree.ElementTree import ElementTree, Element, SubElement, tostring

class Convenience(object):
    def __init__(self, name, uri):
        if uri:
            self.name = u"{%s}%s" % (uri, name)
        else:
            self.name = name

    def create(self, **kw):
        return Element(self.name, **kw)

    def add(self, parent, _text=None, **attrs):
        elt = SubElement(parent, self.name, **attrs)
        if _text:
            elt.text = _text
        return elt

    __call__ = add

class NSMetaHack(type):
    def __new__(cls, name, bases, dct):
        ns = dct['URI']
        elts = dct['elts']
        del dct['elts']
        for elt in elts:
            dct[str(elt)] = Convenience(elt, ns)
        return type.__new__(cls, name, bases, dct)

class NSHack(object):
    __metaclass__ = NSMetaHack
    URI = u''
    elts = ()

class RSS2(NSHack):
    URI = None
    elts = ('rss',
            'channel',
            'title',
            'link',
            'description',
            'language',
            'pubDate',
            'lastBuildDate',
            'category',
            'docs',
            'generator',
            'managingEditor',
            'webMaster',
            'item',
            'comments',
            'guid')

class DCElement(NSHack):
    URI = u'http://purl.org/dc/elements/1.1/'
    elts = ('subject','creator')

class Content(NSHack):
    URI = u'http://purl.org/rss/1.0/modules/content/'
    elts = ('encoded',)


class RSS2Feed(object):
    # ew, there's no default namespace
    nsmap = {'content' : Content.URI,
             'dc' : DCElement.URI}

    def __init__(self, request):
        self.request = request

    def creator(self, item, author):
        if not author:
            author = self.author
        DCElement.creator(item, author.name)

    def date(self, elt, dt):
        elt.text = dt.strftime("%a, %d %b %H:%M:%S %Y +0000")
        return elt
    
    def entry(self, channel, image):
        s = StringIO()
        image.view(s, viewname='rssitem',
                   contextdata={'absoluteitemhref' : self.request.full_url(image.href)})
        try:
            desc = unicode(s.getvalue())
        except:
            desc = ''

        item = RSS2.item.add(channel)
        RSS2.title.add(item, image.title)
        RSS2.link.add(item, self.request.full_url(image.href))
        self.date(RSS2.pubDate.add(item), image.publish_time)
        RSS2.guid.add(item, self.request.full_url(image.href), isPermaLink='true')
        if desc:
            Content.encoded.add(item, desc)
        # we don't have comment RSS feeds
        return item

    def feed(self, photos):
        root = RSS2.rss.create(version='2.0') #, nsmap=self.nsmap)
        channel = RSS2.channel.add(root)
        config = self.request.store.config.config
        RSS2.title.add(channel, config.get('feed', 'title'))
        RSS2.link.add(channel, self.request.full_url('/'))
        RSS2.description.add(channel, config.get('feed', 'description'))
#        self.date(RSS2.pubDate(channel), data.updated)
#        self.date(RSS2.lastBuildDate(channel), data.updated)
#        if data.agent and data.agent_version:
 #           RSS2.generator.add(channel, "%s %s" % (data.agent, data.agent_version))
#        RSS2.language.add(channel, data.lang)
        for photo in photos:
            self.entry(channel, photo)
        return root


import codecs
import os
import sys

def handle(request):
    feedzor = RSS2Feed(request)
    load_view = request.store.load_view
    config = request.store.config.config
    rsstitle = config.get('feed', 'title')
    rssdesc = config.get('feed', 'description')
    rsscount = int(config.get('feed', 'recentcount'))

    store = request.store
    photos = [load_view(path) for path in store.loader.recent_items(rsscount)]
    result = tostring(feedzor.feed(photos), encoding='utf-8')
#    f = StringIO()    
#    out = codecs.getwriter('utf-8')(f)
#    handler.processingInstruction('xml-stylesheet', 'type="text/xsl" href="%s"' % (request.full_url('/static/rssformat.xsl')))
#    rss.publish(handler)
#    handler.endDocument()
#    s = f.getvalue()
    request.content_type = 'text/xml'
    request.write(result)
    
                                   
        

if __name__ == '__main__':
    pass
