import os
import sys
import traceback
import time
import cgi
import cgitb
import logging
import socket
import asyncore

from singleshot import ssconfig, sshandler
from BaseHTTPServer import BaseHTTPRequestHandler
from datetime import datetime

from singleshot.fastcgi import Server, Connection, DataPromise
from singleshot.errors import return_404
from ssconfig import disable_logger
from singleshot import sshandler
import signal

QUIT = False

def give_up(*args, **kwargsx):
    asyncore.close_all()
    QUIT = True

signal.signal(signal.SIGPIPE, signal.SIG_IGN)
signal.signal(signal.SIGUSR1, signal.SIG_IGN)
signal.signal(signal.SIGTERM, give_up)

responses = BaseHTTPRequestHandler.responses

LOG = logging.getLogger('singleshot')

CHILDREN_PIDS = {}

class FastCGIResizeAction(object):
    def generate(self, config, img, readyfunc, sharpen='0.9x80'):
        if not os.path.exists(img.image.viewfilepath):
            os.makedirs(img.image.viewfilepath)
        source = img.image.rawimagepath
        dest = img.path
        size = img
        LOG.debug('IM Generating image %s -> %s (%dx%d)',
                  source,
                  dest,
                  size.width,
                  size.height)
        cmd = 'convert'
        size = size.size
        sizespec = '%sx%s' % (size, size)
        args = [cmd, '-size', sizespec, '-scale', sizespec, '-unsharp', sharpen, source, dest]
        
        pid = os.spawnvpe(os.P_NOWAIT,
                          cmd,
                          args,
                          config.getInvokeEnvironment())
        LOG.debug('[%d] ImageMagickProcessor: "%s"', pid, '" "'.join(args))
        CHILDREN_PIDS[pid] = readyfunc
    
    def act(self, path, request):
        size = request.getfirst('size')
        flt = None
        
        if size == 'full':
            # todo: this should just redirect, so the image gets cached
            size = max(request.config.availableSizes)
        
        size = int(size)
        image = request.store.load_view('/' + path[:-4])    
        if not image or not size:
            return return_404(path, request)
    
        serveimage = image
        path = image.rawimagepath
        if image.width > size or image.height > size:
            serveimage = image.sizes[size]
            path = serveimage.path
            if serveimage.uptodate:
                request.respond_file(path, 'image/jpeg')
            else:
                def ready():
                    request.respond_file(path, 'image/jpeg')
                    request.fcgirequest.end()
                request.fcgirequest.deferred = True
                self.generate(request.config,
                              serveimage,
                              ready)
        else:
            request.respond_file(path, 'image/jpeg')            
            
            


class FCGIRequest(sshandler.Request):
    def __init__(self, store, request):
        super(FCGIRequest, self).__init__(store)
        self.content_type = 'text/html'
        self.content_length = 0
        self.path_info = request.environ['PATH_INFO'][1:]
        self.host = request.environ['HTTP_HOST']
        self.uri = request.environ['REQUEST_URI']
        self.__sent_headers = False
        self.__status_code = 200
        self.__location = ''
        self.__request = request
        self.fcgirequest = request

    def _load_form(self):
        return cgi.FieldStorage(fp=self.__request.stdin,
                                environ=self.__request.environ)
    
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
        self.__status_code = code

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
            self.__request.stdout.write(hdrs)
            
    def write(self, bytes):
        if not self.__sent_headers:
            self.send_headers()
        self.__request.stdout.write(bytes)

    def find_action(self, action):
        if action == 'resize':
            return FastCGIResizeAction()
        else:
            actionmodule = __import__('singleshot.action_' + action,
                                      globals(),
                                      locals())
            actionmodule = getattr(actionmodule, 'action_' + action)
            return actionmodule


class SSConnection(Connection):
    def __init__(self, store, *args, **kwargs):
        self.store = store
        Connection.__init__(self, *args, **kwargs)

    def run_request(self, request):
        rq = FCGIRequest(self.store, request)
        LOG.debug('About to handle %s',rq.path_info)
        sshandler.handle(rq)

    def handle_traceback(self, request, exc_info):
        now = datetime.now()
        s = "[singleshot exception: %s]" % str(now)
        s += cgitb.text(exc_info)
        s += "[end singleshot exception]\n"
        LOG.error(s)
        out = request.stdout
        out.write("""<!--: spam
Content-type: text/html

-->
An error has occured during processing.  :-(""")


class SServer(Server):
    def __init__(self, store, *args, **kwargs):
        Server.__init__(self, *args, **kwargs)
        self.__store = store

    def _start_connection(self, sock):
        ssc = SSConnection(self.__store, sock=sock)

HANDLER = None

def fcgi_logging(root, log_level):
    global HANDLER
    hdlr = logging.FileHandler(os.path.join(root, 'view/.ssfcgi.log'))
    HANDLER = hdlr
    rl = logging.getLogger()
    rl.addHandler(hdlr)
    fmt = logging.Formatter('[singleshot/%(asctime)s/%(levelname)s] %(message)s')
    hdlr.setFormatter(fmt)
    rl.setLevel(log_level)
    disable_logger('singleshot.trace')
    disable_logger('simpleTAL')
    logging.getLogger('simpleTAL').propagate = False

def main(show_exceptions=False, root=None, **config):    
    store = ssconfig.create_store(root, configure_logging=fcgi_logging, **config)
    LOG.info('Singleshot FastCGI startup')
    sock = socket.fromfd(0, socket.AF_INET, socket.SOCK_STREAM)
    server = SServer(store, sock=sock)
    # TODO check for FCGI environment
    while asyncore.socket_map or CHILDREN_PIDS:
        if QUIT:
            break
        if CHILDREN_PIDS:
            result = os.waitpid(0, os.WNOHANG)
            if result[0]:
                pid, status = result
                try:
                    CHILDREN_PIDS[pid]()
                    del CHILDREN_PIDS[pid]
                    LOG.debug('Child %d complete', pid)
                except KeyError:
                    LOG.warn('Unexpected child process %d ended', pid)
            asyncore.poll(.1)                    
        else:
            asyncore.poll(30.)
        server.listen(5)
    LOG.info('Singleshot FastCGI shutdown')
    handler.flush()


