#!/usr/bin/env python
#


#
# A single entry point for Singleshot CGI
#

import os
import sys
import cgi
import cgitb
import traceback
import time
import logging

from singleshot import ssconfig, sshandler
from BaseHTTPServer import BaseHTTPRequestHandler
from datetime import datetime

responses = BaseHTTPRequestHandler.responses

LOG = logging.getLogger('singleshot')


class CGIRequest(sshandler.Request):
    def __init__(self, store, path, out=sys.stdout):
        super(CGIRequest, self).__init__(store)
        self.content_type = 'text/html'
        self.content_length = 0
        self.path_info = path
        self.host = os.environ['HTTP_HOST']
        self.uri = os.environ['REQUEST_URI']
        self.__sent_headers = False
        self.__status_code = 200
        self.__location = ''


    def _load_form(self):
        return cgi.FieldStorage()
    
    def redirect(self, location, perm=0, text=None):
        self.__location = location
        self.__status_code = 301
        if not text:
            text = 'Redirect'
        self.write(text)
        raise sshandler.EndRequestException, 'Redirect'

    def getfirst(self, name):
        return self.form.getfirst(name)

    def set_status(self, code):
        self.__req.status = code

    def send_headers(self):
        if not self.__sent_headers:
            self.__sent_headers = True
            hdrs = []
            hdrs.append(('Content-type', self.content_type))
            if self.content_length:
                hdrs.append(('Content-length', str(self.content_length)))
            if self.__status_code != 200:
                hdrs.append(('Status',
                             '%d %s' % (self.__status_code,
                                        responses[self.__status_code][0])))
            if self.__location:
                hdrs.append(('Location', self.__location))
            hdrs = '\n'.join([('%s: %s' % hdr) for hdr in hdrs]) + '\n\n'
            sys.stdout.write(hdrs)
            
    def write(self, bytes):
        if not self.__sent_headers:
            self.send_headers()
        sys.stdout.write(bytes)

def exception_handler(etype, evalue, etb):
    out = sys.stdout
    out.write("""<!--: spam
Content-type: text/html

-->
An error has occured during processing.  :-(""")
    out.flush()
    now = datetime.now()
    s = "[singleshot exception: %s]" % str(now)
    s += cgitb.text((etype, evalue, etb))
    s += "[end singleshot exception]\n"
    LOG.error(s)

def main(show_exceptions=False,
         root=None, path=os.environ['PATH_INFO'][1:], **config):
    if show_exceptions:
        cgitb.enable()
    else:
        sys.excepthook = exception_handler
    store = ssconfig.create_store(root, **config)
    request = CGIRequest(store, path)
    sshandler.handle(request)

