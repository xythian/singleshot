from singleshot import ssconfig
from singleshot.properties import AutoPropertyMeta
from singleshot.ssconfig import SecurityError
from time import time
import mmap
import os
import logging
LOG = logging.getLogger('singleshot')

class EndRequestException:
    def __init__(self, reason):
        self.reason = reason

class Request(object):
    __metaclass__ = AutoPropertyMeta

    def __init__(self, store):
        self.store = store

    def _get_config(self):
        return self.store.config

    def _get_loader(self):
        return self.store.loader

    def _get_processor(self):
        return self.store.processor        


    def respond_file(self, path, ct):
        fd = os.open(path, os.O_RDONLY)
        l = os.fstat(fd).st_size
        LOG.debug('respond_file(%s[%d], %s)', path, l, ct)
        data = mmap.mmap(fd, l, access=mmap.ACCESS_READ)
        self.content_type = ct
        self.content_length = l
        self.write(data)



    def log(self, message, *args, **kwargs):
        if LOG.isEnabledFor(logging.INFO):
            LOG.info('[%s] ' + message,self.path_info, *args, **kwargs)


def handle(request):
    n = time()
    path = request.path_info
    try:
        slash = path.index('/')
        action = path[:slash]
        path = path[slash+1:]
    except ValueError:
        action = 'view'
        path = '/'
    config = request.config
    if path.startswith(config.url_prefix) and config.url_prefix != '/':
        path = path[len(config.url_prefix)-1:]
    elif path.startswith(config.url_prefix[1:]) and config.url_prefix != '/':
        path = path[len(config.url_prefix)-2:]
    if not path:
        path = '/'

    actionmodule = request.find_action(action)
    try:
        # invoke the action handler
        actionmodule.act(path, request)
    except SecurityError, msg:
        request.content_type = 'text/plain'
        request.write('Exit with security error: ' + msg)
    except EndRequestException:
        pass
    request.log('Render complete %.2fms', (time() - n)*1000.)
