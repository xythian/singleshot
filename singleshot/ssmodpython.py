from singleshot.properties import AutoPropertyMeta
from singleshot import sshandler
from mod_python import util, apache
import logging

import os
import mmap
from datetime import datetime
import time

class ModPythonRequest(sshandler.Request):
    def __init__(self, store, req):
        super(ModPythonRequest, self).__init__(store)
        self.__req = req
        self.__commonvars = False

    def _get_path_info(self):
        return self.__req.path_info[1:]

    def _load_form(self):
        return util.FieldStorage(self.__req)
    
    def _set_content_type(self, ct):
        self.__req.content_type = ct

    def _get_uri(self):
        if not self.__commonvars:
            self.__req.add_common_vars()
            self.__commonvars = True
        return self.__req.subprocess_env['REQUEST_URI']

    def _get_content_type(self):
        return self.__req.content_type

    def _set_content_length(self, l):
        self.__cl = l
    #        self.__req.set_content_length(l)  # this doesn't work??

    def _get_content_length(self):
        return self.__cl

    def getfirst(self, name):
        try:
            return self.form[name]
        except KeyError:
            return ''

    def redirect(self, location, perm=0, text=None):
        self.__req.redirect(location, perm=perm, text=text)

    def set_status(self, code):
        self.__req.status = code

    def send_headers(self):
        self.__req.send_http_header()

    def write(self, bytes):
        self.__req.write(bytes)

    def find_action(self, action):
        return apache.import_module('singleshot.action_' + action)        


store = None

def handler(req):
    global store
    ssconfig = apache.import_module('singleshot.ssconfig')
    if not store:
        options = req.get_options()        
        store = ssconfig.create_store(root=options['root'],
                                      baseurl=options['baseurl'],
                                      template_root=options['template_root'])
    request = ModPythonRequest(store, req)
    sshandler.handle(request)
    return apache.OK    
