import socket
import time
import os
import sys
import asyncore
from cgi import FieldStorage
from struct import pack, unpack, calcsize
from properties import PackedRecord
from cStringIO import StringIO
import logging
from dummy_threading import RLock, Thread # sigh

LOG = logging.getLogger('singleshot.fastcgi')


FCGI_LISTENSOCK_FILENO = 0   # Listening socket file number

#typedef struct {
#    unsigned char version;
#    unsigned char type;
#    unsigned char requestIdB1;
#    unsigned char requestIdB0;
#    unsigned char contentLengthB1;
#    unsigned char contentLengthB0;
#    unsigned char paddingLength;
#    unsigned char reserved;
#} FCGI_Header;

class Header(PackedRecord):
    __fields__ = ['version',
                  'type',
                  'request_id',
                  'body_length',
                  'padding_length']

    _format = '!BBHHBx'

    def _get_total_bytes(self):
        return self.body_length + self.padding_length

    total_bytes = property(_get_total_bytes)



FCGI_HEADER_LEN  = 8  # Header length, future versions will not reduce
FCGI_VERSION_1   = 1  # Value for version component of FCGI_Header

# Values for type component of FCGI_Header

FCGI_BEGIN_REQUEST     =  1
FCGI_ABORT_REQUEST     =  2
FCGI_END_REQUEST       =  3
FCGI_PARAMS            =  4
FCGI_STDIN             =  5
FCGI_STDOUT            =  6
FCGI_STDERR            =  7
FCGI_DATA              =  8
FCGI_GET_VALUES        =  9
FCGI_GET_VALUES_RESULT = 10
FCGI_UNKNOWN_TYPE      = 11
FCGI_MAXTYPE           = FCGI_UNKNOWN_TYPE 

FCGI_NULL_REQUEST_ID   = 0  # requestId component of FCGI_Header

#typedef struct {
#    unsigned char roleB1;
#    unsigned char roleB0;
#    unsigned char flags;
#    unsigned char reserved[5];
#} FCGI_BeginRequestBody;


#typedef struct {
#    FCGI_Header header;
#    FCGI_BeginRequestBody body;
#} FCGI_BeginRequestRecord;

FCGI_KEEP_CONN = 1 #  Mask for flags component of FCGI_BeginRequestBody

class BeginRequestBody(PackedRecord):
    __fields__ = ['role',
                  'flags']

    _format = '!HBxxxxx'

    def _get_shouldKeepConn(self):
        return self.flags & FCGI_KEEP_CONN

    shouldKeepConn = property(_get_shouldKeepConn)

# Values for role component of FCGI_BeginRequestBody

FCGI_RESPONDER  = 1
FCGI_AUTHORIZER = 2
FCGI_FILTER     = 3

#typedef struct {
#    unsigned char appStatusB3;
#    unsigned char appStatusB2;
#    unsigned char appStatusB1;
#    unsigned char appStatusB0;
#    unsigned char protocolStatus;
#    unsigned char reserved[3];
#} FCGI_EndRequestBody;

class EndRequestBody(PackedRecord):
    __fields__ = ['appStatus',
                  'protocolStatus']

    _format = '!IBxxx'

#typedef struct {
#    FCGI_Header header;
#    FCGI_EndRequestBody body;
#} FCGI_EndRequestRecord;

# Values for protocolStatus component of FCGI_EndRequestBody

FCGI_REQUEST_COMPLETE = 0
FCGI_CANT_MPX_CONN    = 1
FCGI_OVERLOADED       = 2
FCGI_UNKNOWN_ROLE     = 3

# Variable names for FCGI_GET_VALUES / FCGI_GET_VALUES_RESULT records

FCGI_MAX_CONNS =  "FCGI_MAX_CONNS"
FCGI_MAX_REQS  =  "FCGI_MAX_REQS"
FCGI_MPX_CONNS = "FCGI_MPXS_CONNS"

VALUES = {FCGI_MAX_CONNS : "50",
          FCGI_MAX_REQS : "50",
          FCGI_MPX_CONNS : "1"}


#typedef struct {
#    unsigned char type;    
#    unsigned char reserved[7];
#} FCGI_UnknownTypeBody;

class UnknownTypeBody(PackedRecord):
    __fields__ = ['type']

    _format = '!Bxxxxxxx'

#typedef struct {
#    FCGI_Header header;
#    FCGI_UnknownTypeBody body;
#} FCGI_UnknownTypeRecord;

            
class DataPromise(object):
    def __init__(self, l, source):
        self.length = l
        self.source = source

    def __iter__(self):
        return self.source


class Record(object):
    def __init__(self, header):
        self.header = header
        self.content = []
        self.bytes = 0

    def add(self, bytes):
        self.bytes += len(bytes)
        self.content.append(bytes)

    def _get_complete(self):
        return self.needs <= 0

    def _get_needs(self):
        return self.header.total_bytes - self.bytes

    
    needs = property(_get_needs)
    complete = property(_get_complete)

    request_id = property(lambda self:self.header.request_id)
    type = property(lambda self:self.header.type)

    def finish(self):        
        self.content_data = (''.join(self.content))[:self.header.body_length]
        del self.content

HIGH_BIT = 1L << 31
NOT_HIGH_BIT = ~HIGH_BIT

class NameValuePair(list):
    def __init__(self, name='', value=''):
        super(NameValuePair, self).__init__((name, value))

    name = property(lambda self:self[0], lambda self, v:self.__setitem__(0, v))
    value = property(lambda self:self[1], lambda self, v:self.__setitem(1, v))

    def unpack_length(data, offset):
        nl = ord(data[offset])
        if nl & 128:
            nl = unpack('!I', data[offset:offset+4])[0] & NOT_HIGH_BIT
            offset += 4
        else:
            offset += 1
        return nl, offset

    unpack_length = staticmethod(unpack_length)

    def pack_length(l):
        if l > 127:
            return pack('!I', l | HIGH_BIT)[0] 
        else:
            return chr(l)

    pack_length = staticmethod(pack_length)

    def read(data, offset):
        namel, offset = NameValuePair.unpack_length(data, offset)
        valuel, offset = NameValuePair.unpack_length(data, offset)
        name = data[offset:offset+namel]
        offset += namel
        value = data[offset:offset+valuel]
        offset += valuel
        return offset, NameValuePair(name, value)

    read = staticmethod(read)
    
    def pack(self):
        return self.pack_length(len(self.name)) + self.pack_length(len(self.value)) + self.name + self.value

    
class NameValuePairs(list):
    def __init__(self, data=''):
        if data:
            super(NameValuePairs, self).__init__(self.parse_pairs(data, 0))
        else:
            super(NameValuePairs, self).__init__()

    def add(self, name, value):
        self.append(NameValuePair(name, value))

    def unparse(self):
        return ''.join([pair.pack() for pair in self])
    
    def parse_pairs(self, data, offset):
        l = len(data) - 2
        while offset < l:
            offset, pair = NameValuePair.read(data, offset)
            yield pair

def pack_record(type, request_id, body):
    if isinstance(body, DataPromise):
        l = body.length
    else:
        l = len(body)
    padding = -l & 7
#    LOG.debug('body is %s', len(body))
    hdr = pack("!BBHHBB", FCGI_VERSION_1, type, request_id, l,
               padding, 0)
#    test = Header(hdr)
#    LOG.debug('header (%s)', repr(test._fields))
#    LOG.debug('header (%d, %d)', len(body), padding)
    yield hdr
#    LOG.debug('body')
    if isinstance(body, DataPromise):
        for chunk in body:
            yield chunk
    elif body:
        yield body
#    LOG.debug('padding')
    if padding:
        yield '\x00' * padding
#    LOG.debug('done')

class Recordinator(object):
    def __init__(self):
        self.__bytes = ''
        self.__record = None

    def feed(self, data):
        records = []
        if self.__bytes:
            data = self.__bytes + data
            self.__bytes = ''
        while data:            
            if self.__record:
                l = self.__record.needs
                if len(data) < l:
                    self.__record.add(data)
                    data = ''
                else:
                    self.__record.add(data[:l])
                    self.__record.finish()
                    records.append(self.__record)
                    self.__record = None
                    data = data[l:]
            else:
                if len(data) >= FCGI_HEADER_LEN:
                    header = Header(data[:FCGI_HEADER_LEN])
                    self.__record = Record(header)
                    data = data[FCGI_HEADER_LEN:]
                else:
                    self.__bytes = data
                    data = ''
        if self.__record:
            if self.__record.complete:
                records.append(self.__record)
                self.__record.finish()                
                self.__record = None
        return records


class RecordConnection(asyncore.dispatcher):
    def __init__(self, *args, **kargs):
        asyncore.dispatcher.__init__(self, *args, **kargs)
        self.__parser = Recordinator()
        self.__outbound = []
        self.__working_data = None
        self.__working_offset = 0
        self.__writable = False
        self.__close_when_flushed = False
        self.__buflock = RLock()

    def writable(self):
        return self.__writable

    def next_data(self):
        try:
            self.__buflock.acquire()        
            while True:
                if not self.__outbound:
                    return None
                try:
                    return self.__outbound[0].next()
                except StopIteration:
                    del self.__outbound[0]
        finally:
            self.__buflock.release()
                

    def handle_write(self):
        total = 0
        while True:
            if not self.__working_data:
                self.__working_data = self.next_data()
                if self.__working_data:
                    self.__working_offset = 0
#                    LOG.debug('got working data')
                    self.__working_length = len(self.__working_data)
#                    LOG.debug('New working data %d', self.__working_length)
            if not self.__working_data:
#                LOG.debug('Out of working data')
                self.__writable = False
                if self.__close_when_flushed:
                    self.close()
                return            
            try:
#                LOG.debug('Sending from %d', self.__working_offset)
                sent = self.send(self.__working_data[self.__working_offset:])
            except:
                LOG.warn('buffer write failed', exc_info=sys.exc_info())
#            LOG.debug('Sent %d', sent)
            if sent:
                self.__working_offset += sent
                total += sent
                if self.__working_offset >= self.__working_length:
                    self.__working_data = None
            else:
                break
        LOG.debug('Wrote %d bytes', total)

    def flush_close(self):
        if self.__writable:
            self.__close_when_flushed = True
        else:
            self.close()

    def send_buffered(self, data_source):
        if isinstance(data_source, str):
            data_source = iter((data_source,))
        else:
            data_source = iter(data_source)
        self.__buflock.acquire()
        try:            
            self.__outbound.append(data_source)
            self.__writable = True
        finally:
            self.__buflock.release()

    def send_record(self, type, request_id, data=None, rb=None):
#        LOG.debug('Connection.send_Record')
        if rb:
#            LOG.debug('Packing %s', repr(rb))
            data = rb.pack()
#        LOG.debug('Send record (%d, %d, %s)', type, request_id, repr(data))
        self.send_buffered(pack_record(type, request_id, data))
    

    def _get_values(self, record):
        request = NameValuePairs(data=record.content_data)
        result = NameValuePairs()
        for name, x in result:
            try:
                val = VALUES[name]
                result.add(name, val)
            except:
                pass
        LOG.debug('FCGI_GET_VALUES_RESULT sent')
        self.send_record(FCGI_GET_VALUES_RESULT,
                         record.request_id,
                         result.unparse())


    def dispatch_record(self, record):
        LOG.warn('Unhandled record: %d', record.type)
    
    def handle_read(self):
#        LOG.debug('Handle read')
        data = self.recv(1024)
        if not data:
            self.close()
        for record in self.__parser.feed(data):
            self.dispatch_record(record)

CONNECTION_COUNT = 0

class Connection(RecordConnection):
    def __init__(self, *args, **kargs):        
        RecordConnection.__init__(self, *args, **kargs)
        global CONNECTION_COUNT
        self.id = CONNECTION_COUNT
        CONNECTION_COUNT += 1
#        LOG.info('Connection %d opened', self.id)
        self.__requests = {}
        self.__dispatch = {FCGI_GET_VALUES : self._get_values,
                           FCGI_BEGIN_REQUEST : self._begin_request,
                           FCGI_ABORT_REQUEST : self._abort_request,
                           FCGI_PARAMS : self._request_params,
                           FCGI_STDIN : self._request_stdin}
        self.__request_dispatch = {FCGI_RESPONDER : self._begin_responder}
        
    def dispatch_record(self, record):
        try:
            handler = self.__dispatch[record.type]
            handler(record)
        except KeyError:
            # unknown record!
            pass


    def rqget(self, record):
        return self.__requests.get(record.request_id)

    def _abort_request(self, record):
        rq = self.rqget(record)
        if rq:
            rq.abort()

    def _request_params(self, record):
        rq = self.rqget(record)
        if not rq:
            return
        if record.content_data:
            rq.add_params(NameValuePairs(record.content_data))
        else:
            rq.finish_params()

    def _request_stdin(self, record):
        rq = self.rqget(record)
        if not rq:
            return
        if record.content_data:
            rq.add_stdin(record.content_data)
        else:
            rq.finish_stdin()
    
    def _begin_request(self, record):        
        beg = BeginRequestBody(_data=record.content_data)
#        LOG.debug('Begin request %d (%d)', record.request_id, beg.role)
        try:
            handler = self.__request_dispatch[beg.role]
            return handler(record, beg)
        except KeyError:
            pass
        LOG.warn('%d: Unknown request role %d',
                 record.request_id,
                 beg.role)
        self.send_record(FCGI_END_REQUEST,
                         record.request_id,
                         rb=EndRequestBody(appStatus=0,
                                           protocolStatus=FCGI_UNKNOWN_ROLE))

    def _begin_responder(self, req, body):
        LOG.debug('Start request %d.%d', self.id, req.request_id)
        request = Request(self, req.request_id, body)
        request.deferred = False
        request.begin_time = time.time()
        self.__requests[request.request_id] = request

    def finish_request(self, req):
        now = time.time()
        LOG.debug('End request %d.%d (%.2fms)', self.id, req.request_id,
                 (now - req.begin_time)*1000.)
        del self.__requests[req.request_id]

    def run_request(self, request):
        pass

    def handle_traceback(self, request, exc_info):
        pass

    def execute_request(self, request):
        def execute():
            try:
                self.run_request(request)
            except:
                self.handle_traceback(request, sys.exc_info())
            if not request.deferred:
                request.end()
        name = 'Execute request %d' % request.request_id
        execute()
#        Thread(target=execute, name=name).start()

    def handle_close(self):
        LOG.debug('Connection %d closed', self.id)
        for key, v in self.__requests:
            LOG.warn('Pending request %d.%d did not complete', self.id, key)
        self.close()



class RecordOutputStream(object):
    def __init__(self, request, type):
        self._type = type
        self._rq = request
        self._closed = False

    def write(self, data):
        if isinstance(data, DataPromise):
            self._rq.send_record(self._type, data=data)            
        elif data:
            if len(data) > 65536:
                for i in xrange((len(data) / 65535)+1):
                    self._rq.send_record(self._type,
                                         data=data[i*65535:(i+1)*65535])
            else:                    
                self._rq.send_record(self._type,
                                     data=data)

    def close(self):
        if not self._closed:
            self._closed = True
            self._rq.send_record(self._type,
                                 data='')
            

class Request(object):
    def __init__(self, conn, request_id, beginRequestBody):
        self._conn = conn
        self.request_id = request_id
        self.keepConnection = beginRequestBody.shouldKeepConn
        self.stdin = StringIO()
        self.environ = {}
        self.stdout = RecordOutputStream(self, FCGI_STDOUT)
        self.stderr = RecordOutputStream(self, FCGI_STDERR)
        self.__ended = False
        self._paramsDone = False
        self._stdinDone = False
        
    def add_params(self, params):
        for [name, val] in params:
            self.environ[name] = val

    def send_record(self, type, **kw):
        self._conn.send_record(type, self.request_id, **kw)
        
    def finish_params(self):
        if self._stdinDone:
            self._conn.execute_request(self)
        else:
            self._paramsDone = True

    def add_stdin(self, data):
        self.stdin.write(data)

    def finish_stdin(self):
        self.stdin.seek(0, 0)
        if self._paramsDone:
            self._conn.execute_request(self)
        else:
            self._stdinDone = True

    def abort(self):
        self.end()

    def end(self, code=0):
        if self.__ended:
            return
        self.stdout.close()
        self.send_record(FCGI_END_REQUEST,
                         rb=EndRequestBody(appStatus=code,
                                           protocolStatus=FCGI_REQUEST_COMPLETE))
        self._conn.finish_request(self)
        if not self.keepConnection:
            self._conn.flush_close()
        del self._conn
        del self.stdin
        del self.environ
        self.__ended = True

def check_address(address):
    # TODO: check addr against FCGI_WEB_SERVER_ADDRS    
    return True

class Server(RecordConnection):
    _start_connection = Connection

    accepting = True

    def handle_accept(self):
        (newsock, addr) = self.accept()
        if not check_address(addr):
            newsock.close()
            return
        self._start_connection(sock=newsock)


if __name__ == '__main__':
    foo = EndRequestBody(appStatus=2, protocolStatus=FCGI_REQUEST_COMPLETE)
    print foo.pack()
