import xml.sax
import xml.sax.handler
#from cStringIO import StringIO
from StringIO import StringIO


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
    __elements__ = ['Headline']

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

class XMPHeader(EmptyXMPHeader):
    def __init__(self, body):
#        print body
        class RDFReader(xml.sax.handler.ContentHandler):
            def startDocument(self):
                self._cdata = StringIO()
                
            def startElementNS(self, name, qname, attrs):
                if name == RDF_NS.Description:
                    for uri, qn in attrs.getNames():
                        if uri in (EXIF_NS.URI, TIFF_NS.URI, Photoshop_NS.URI):
                            setattr(self.target, str(qn), str(attrs.getValue((uri, qn))))                        
                elif name == RDF_NS.Bag:
                    self._value = []
                elif name == RDF_NS.Alt:
                    self._value = []
                elif name == RDF_NS.Seq:
                    self._value = []
                elif name == RDF_NS.li:
                    self._cdata = StringIO()
                elif name == DC_NS.subject:
                    self._pname = 'keywords'
                elif name == DC_NS.description:
                    self._pname = 'caption'

            def endElementNS(self, name, qname):
                if name == RDF_NS.li:
                    self._value.append(self._cdata.getvalue())
                    self._cdata = StringIO()
                elif name == DC_NS.subject:
                    setattr(self.target, self._pname, self._value)
                    self._value = []
                elif name == DC_NS.description:
                    setattr(self.target, self._pname, self._value)
                    self._value = []


            def characters(self, content):
                self._cdata.write(content)
        parser = xml.sax.make_parser()
        parser.setFeature(xml.sax.handler.feature_namespaces, 1)
        rdr = RDFReader()
        rdr.target = self
        parser.setContentHandler(rdr)
        parser.parse(StringIO(body))
