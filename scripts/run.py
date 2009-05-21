#
# Switch to wsgiref for the bare bones running.
#
import singleshot.serve
import singleshot.ssconfig
import os

jroot = '../../sites/photos.xythian.com'
root = '../singleshot_testroot'
root = os.path.abspath(root)
templates = os.path.join(root, 'templates')

store = singleshot.ssconfig.create_store(root, template_root=templates)
singleshot.serve.serve_http(store, addr='', port=8080)