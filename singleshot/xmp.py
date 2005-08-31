import xml.sax
import xml.sax.handler
#from cStringIO import StringIO
from StringIO import StringIO
import time
import re
import sys

class NamespaceMeta(type):
    def __new__(cls, name, bases, dict):
        try:
            uri = unicode(dict['__uri__'])
            elts = dict['__elements__']
            dict['URI'] = uri
            for name in elts:
                dict[name] = (uri, unicode(name))
        except KeyError:
            pass
        return super(NamespaceMeta, cls).__new__(cls, name, bases, dict)

class Namespace(object):
    __metaclass__ = NamespaceMeta

class RDF_NS(Namespace):
    __uri__ = u'http://www.w3.org/1999/02/22-rdf-syntax-ns#'
    __elements__ = ['RDF', 'Description', 'Seq', 'li', 'Bag', 'Alt']

class Photoshop_NS(Namespace):
    __uri__ = u'http://ns.adobe.com/photoshop/1.0/'
    __elements__ = ['Headline', 'DateCreated']

class TIFF_NS(Namespace):
    __uri__ = u'http://ns.adobe.com/tiff/1.0/'
    __elements__ = ['BitsPerSample', 'ImageWidth', 'ImageLength', 'Make', 'Model']

class EXIF_NS(Namespace):
    __uri__ = u'http://ns.adobe.com/exif/1.0/'
    __elements__ = ['ExifVersion', 'DateTimeOriginal', 'DateTimeDigitized', 'ExposureTime',
                    'FNumber', 'ISOSpeedRatings', 'Flash', 'Fired', 'Return', 'Mode', 'RedEyeMode']
class DC_NS(Namespace):
    __uri__ = u'http://purl.org/dc/elements/1.1/'
    __elements__ = ['subject', 'description']

class EmptyXMPHeader(object):
    Headline = ''
    keywords = ()

XMPDT = re.compile(r'(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)T(?P<hour>\d\d):(?P<minute>\d\d):(?P<second>\d\d)(?P<tzsign>[-+])(?P<tzhours>\d\d):(?P<tzminutes>\d\d)')

XMPDT1 = re.compile(r'(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)T(?P<hour>\d\d):(?P<minute>\d\d)(?P<tzsign>[-+])(?P<tzhours>\d\d):(?P<tzminutes>\d\d)')

XMPDT2 = re.compile(r'(?P<year>\d\d\d\d)-(?P<month>\d\d)-(?P<day>\d\d)')

def parse_xmp_datetime(dt):
    m = XMPDT.match(dt)
    if m:
        year, month, day, hour, minute, second, tzsign, tzhours, tzminutes = m.groups()
    else:
        m = XMPDT1.match(dt)
        if m:
            second = 0
            year, month, day, hour, minute, tzsign,  tzhours, tzminutes = m.groups()
        else:
            m = XMPDT2.match(dt)
            if m:
                second = 0
                hour = 0
                minute = 0
                tzsign = '+'
                tzhours = 0
                tzminutes = 0
                year, month, day = m.groups()
    tzsign = int(tzsign + '1')
    [year, month, day, hour, minute, second] = map(int, [year, month, day, hour, minute, second])
    tzhours, tzminutes = int(tzhours), int(tzminutes)
    t = time.mktime((year, month, day, hour, minute, second, -1, -1, 0))
    tzoffset = tzsign * (tzhours * 3600. + tzminutes * 60.)
    gmt = t + tzoffset
    return gmt

class RDFReader(xml.sax.handler.ContentHandler):
    def startDocument(self):
        self._cdata = []
        
    def startElementNS(self, name, qname, attrs):
        uri, qn = name
        if uri == RDF_NS.URI:
            if qn == RDF_NS.Description[1]:
                for uri, qn in attrs.getNames():
                    if uri in (EXIF_NS.URI, TIFF_NS.URI, Photoshop_NS.URI):
                        setattr(self.target, str(qn), str(attrs.getValue((uri, qn))))
            elif qn in (RDF_NS.Bag[1], RDF_NS.Alt[1], RDF_NS.Seq[1]):
                self._value = []
            elif qn == RDF_NS.li[1]:                
                self._cdata = []
        elif name == DC_NS.subject:
            self._pname = 'keywords'
        elif name == DC_NS.description:
            self._pname = 'caption'

    def endElementNS(self, name, qname):
        if name == RDF_NS.li:
            self._value.append(''.join(self._cdata))
            self._cdata = []
        elif name == DC_NS.subject:
            setattr(self.target, self._pname, self._value)
            self._value = []
        elif name == DC_NS.description:
            setattr(self.target, self._pname, self._value)
            self._value = []
            

    def characters(self, content):
        self._cdata.append(content)


class XMPHeader(EmptyXMPHeader):
    def __init__(self, body):
#        print body
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_namespaces, 1)
        rdr = RDFReader()
        rdr.target = self
        parser.setContentHandler(rdr)
        parser.parse(StringIO(body))
        for attr in ('DateTimeDigitized', 'DateCreated', 'DateTimeOriginal'):
            try:
                setattr(self, attr, parse_xmp_datetime(getattr(self, attr)))
            except AttributeError:
                pass
