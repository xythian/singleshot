#
# Switch to wsgiref for the bare bones running.
#
import singleshot.serve
import singleshot.ssconfig
import os
import sys

root = os.path.abspath(sys.argv[1])
store = singleshot.ssconfig.create_store(root, template_root=':internal:')
singleshot.serve.serve_http(store, addr='', port=8080)
