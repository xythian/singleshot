#!/usr/bin/python

import sys
import os
from urlparse import urlsplit
from singleshot.views import ItemView, ViewableObject
from singleshot.errors import return_404
from cStringIO import StringIO
import cgi
import logging

from datetime import datetime
from pysqlite2 import dbapi2 as sqlite

LOG = logging.getLogger('singleshot')


def main():
    path = os.environ['PATH_INFO']
    store = object()
    request = CGIRequest(store, path)
    request.content_type = 'text/html'
    uri = request.getfirst('uri')
    comments = request.getfirst('comments')
    if comments:
        comment = comments
        save(uri, comments)
    else:
        comment = load(uri)
    request.write('<a href="#" onclick="comment_edit(document.getElementById(\'thecomments\')); return false;">edit</a> <div id="thecomments" ondblclick="comment_edit(this)">%s</div>' % comment)


SCHEMA = """

CREATE TABLE ss_schema_version (
   version integer
);

INSERT INTO ss_schema_version VALUES (0);

CREATE TABLE t_comment (
   commentid integer primary key autoincrement,
   visible text,
   comment_date timestamp,
   author_name text,
   author_url text,
   author_email text,
   author_ip text,
   path text,
   subject text,
   body text
);
"""

JAVASCRIPT = """

comment_object_path = %(comment_object_path)s;

function comment_new_request() {
    var result;
    try {
        result=new ActiveXObject("Msxml2.XMLHTTP");
    } catch (e) {
        try {
            result=new ActiveXObject("Microsoft.XMLHTTP");
        } catch (oc) {
            result=null;
        }
    }
    if(!result && typeof XMLHttpRequest != "undefined") {
        result = new XMLHttpRequest();
    }
    if (!result) {
        return null;
    }
    return result;
}

function _commentblock_refresh(arguments, ready) {
    var doc = document.getElementById('commentblock');
    var request = comment_new_request();
    request.onreadystatechange = function () {
        if (request.readyState != 4) {
		 return;
        }
        var data = request.responseText;
        doc.innerHTML = data;
        if(ready) {
           ready();
        }
    }
    var xuri = "%(rpc_url)s";
    request.open("POST", xuri, true);
    var frmbody = "path=" + escape(comment_object_path);
    if(arguments) {
        frmbody = frmbody + '&' + arguments
    }
    request.setRequestHeader("Method", "POST " + xuri + " HTTP/1.1");
    request.setRequestHeader("Content-Type", "application/x-www-form-urlencoded");
    request.send(frmbody);    
}

function comment_expand() {
    _commentblock_refresh('action=load')
    return false;
}

function comment_expand_add() {
    _commentblock_refresh('action=load', function() {
        comment_reveal_form(document.getElementById('commentlink'))
    })
    return false;
}

function _cmt_form_error(message) {
   elt = document.getElementById('comment_form_error')
   elt.innerHTML = message
   elt.style.display = 'block'
}

function _cmt_trim(v) {
  return v.replace(/(^\s+)|(\s+$)/g, '')
}

function _cmt_msg(infoeltid, message) {
   elt = document.getElementById(infoeltid)
   elt.innerHTML = message
}

function _cmt_valid_email(fld, infoeltid) { 
  var email = /^[^@]+@[^@.]+\.[^@]*\w\w$/
  var val = _cmt_trim(fld.value)
  fld.value = val
  if (!email.test(val)) {
     _cmt_msg(infoeltid, 'Email address does not appear to be valid.')
     return false;
  } else {
     _cmt_msg(infoeltid, '&nbsp;')
     return true;
  }
}

function _cmt_valid_require(fld, infoeltid) {
  var val = _cmt_trim(fld.value)
  fld.value = val
  if (val.length == 0) {
     _cmt_msg(infoeltid, 'Required.')
     return false;
  } else {
     _cmt_msg(infoeltid, '&nbsp;')
     return true;
  }
}

function _cmt_valid_url(fld, infoeltid) {
  var val = _cmt_trim(fld.value)
  // bah, forget it, just use it
  return true;
}

function comment_reveal_form(lnk) {
   var frm = document.getElementById('commitform')
   lnk.style.display = 'none'
   frm.style.display = 'block'
   document.getElementById('commentnamefield').focus()   
}

function comment_submit(elt) {
   var frm = document.getElementById('commitform')
   if(_cmt_valid_require(frm.n, 'n_inf') && _cmt_valid_url(frm.boffed, 'boffed_inf') && _cmt_valid_email(frm.snickerdoodle, 'snickerdoodle_inf') && _cmt_valid_require(frm.wifflebat, 'wifflebat_inf')) {
      elt.disabled = true;
      flds = { action : 'post',
               name : frm.n.value,
               url : frm.boffed.value,
               email : frm.snickerdoodle.value,
               comment : frm.wifflebat.value}
      var f1 = []
      for(var k in flds) {
         f1.push(k + '=' + escape(flds[k]))
      }
      _commentblock_refresh(f1.join('&'))
   }
   return false;
}

document.write(%(initial_html)s);

"""

class InitialHtmlBlock(ItemView, ViewableObject):
    viewname = 'comment_initial'

    def create_context(self):
        context = super(InitialHtmlBlock, self).create_context()
        count = self.store.comments.count_for(self.path)
        context.addGlobal('commentcount', count)
        return context

class ViewCommentBlock(ItemView, ViewableObject):
    viewname = 'comment_view'

    message = ''

    def create_context(self):
        context = super(ViewCommentBlock, self).create_context()
        comments = self.store.comments.load_for(self.path)
        context.addGlobal('commentcount', len(comments))
        context.addGlobal('comments', comments)
        context.addGlobal('submitmessage', self.message)
        return context

class Comment(object):
    comment_id = None
    comment_date = None
    author_name = None
    author_url = None
    author_email = None
    author_ip = None
    path = None
    visible = True
    body = None

    def insert(self, cursor):
        self.comment_date = datetime.now()
        cursor.execute("INSERT INTO t_comment (visible, comment_date, author_name, author_url, author_email, author_ip, path, body) VALUES (:visible, :comment_date, :author_name, :author_url, :author_email, :author_ip, :path, :body)",
                       {'comment_date' : self.comment_date,
                        'author_name' : self.author_name,
                        'author_url' : self.author_url,
                        'author_email' : self.author_email,
                        'author_ip' :  self.author_ip,
                        'visible' : self.visible,
                        'path' : self.path,
                        'body' : self.body})
        cursor.execute("SELECT last_insert_rowid()")        
        self.comment_id = cursor.fetchall()[0]

    def load_for(cls, path, cursor):
        cursor.execute("SELECT commentid, visible, comment_date, author_name, author_url, author_email, author_ip, path,body FROM t_comment WHERE path = :path ORDER BY comment_date ASC", {'path' : path})
        for row in cursor:
            self = Comment()
            self.commentid = row[0]
            self.visible = row[1]
            self.comment_date = row[2]
            self.author_name = row[3]
            self.author_url = row[4]
            self.author_email = row[5]
            self.author_ip = row[6]
            self.path = row[7]
            self.body = row[8]
            yield self

    load_for = classmethod(load_for)

class Commentor(object):
    def __init__(self, store):
        self.store = store
        self.datapath = os.path.join(store.root, '.singleshot')
        if not os.path.exists(self.datapath):
            os.makedirs(self.datapath)
        self.datapath = os.path.join(self.datapath, 'comments.sqlite')
        LOG.warn('Connecting to %s' % self.datapath)
        self.conn = sqlite.connect(self.datapath, detect_types=sqlite.PARSE_DECLTYPES|sqlite.PARSE_COLNAMES)
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name = 'ss_schema_version'")
            result = cursor.fetchall()
            if not result:
                # database isn't there!
                # create it
                cursor.executescript(SCHEMA)
            else:
                pass
            # pretend to verify the schema is up to date here, irrelevant until there's more versions of db
            self.conn.commit()
        finally:
            cursor.close()

    def count_for(self, path):
        cursor = self.conn.cursor()
        try:
            cursor.execute("SELECT count(*) FROM t_comment WHERE path = :path", {'path' : path})
            return cursor.fetchone()[0]
        finally:
            cursor.close()

    def insert(self, comment):
        cursor = self.conn.cursor()
        try:
            comment.insert(cursor)
            self.conn.commit()
        finally:
            cursor.close()

    def load_for(self, path):
        cursor = self.conn.cursor()
        try:
            return list(Comment.load_for(path, cursor))            
        finally:
            cursor.close()
        

def js_repr(v):
    v = v.replace("'", r"\'")
    v = v.replace("\n", r"\n")
    return "'" + v + "'"

def act(actionpath, request):
    if actionpath.startswith('/'):
        actionpath = actionpath[1:]
    if actionpath.endswith('/'):
        actionpath = actionpath[:-1]

    if hasattr(request.store, 'comments'):
        commentor = request.store.comments
    else:
        commentor = Commentor(request.store)
        request.store.comments = commentor

    path = request.getfirst('path')

    if actionpath == 'comments.js':
        item = request.store.loader.load_item(path)
        htmlb = InitialHtmlBlock(item, request.store, load_view=request.store.load_view)
        outf = StringIO()
        htmlb.view(outf, htmlb.viewname)        
        data = {'rpc_url' : 'http://%s%s' % (request.host,'/comment/rpc'),
                'comment_object_path' : js_repr(path),
                'initial_html' : js_repr(outf.getvalue())}
        request.content_type = 'text/javascript'
        request.write(JAVASCRIPT % data)    
    elif actionpath == 'rpc':
        action = request.getfirst('action')
        if action == 'load':
            item = request.store.loader.load_item(path)
            viewc = ViewCommentBlock(item, request.store, load_view=request.store.load_view)
            viewc.request_view(request, viewname=viewc.viewname)
        elif action == 'post':
            name = request.getfirst('name')
            url = request.getfirst('url')
            email = request.getfirst('email')
            comment = request.getfirst('comment')
            if name and email and comment:
                if url and not url.startswith('http'):
                    url = 'http://' + url 
                cm = Comment()
                cm.author_name = name
                cm.author_email = email
                cm.author_url = url
                cm.path = path
                cm.body = comment
                commentor.insert(cm)
            item = request.store.loader.load_item(path)
            viewc = ViewCommentBlock(item, request.store, load_view=request.store.load_view)
            viewc.message = 'Your comment has been posted.  Thank you.'
            viewc.request_view(request, viewname=viewc.viewname)
        else:
            return_404(actionpath, request)
    else:
        return_404(actionpath, request)




