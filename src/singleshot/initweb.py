#!/usr/bin/env python

import sys
from optparse import OptionParser
import re
import os
from stat import *

#
# A script to initialize a singleshot image root
#

#
# Creates the CGI script entry point
# Generates .htaccess
# Copies default templates into the root
#

#
# template variables
#    baseurl
#    cgi
#

MODPYTHON_CLAUSE = """
AddHandler python-program .py
PythonPath @pathparts@+sys.path
PythonOption root @root@
PythonOption template_root @templateroot@
PythonOption baseurl @baseurl@
PythonHandler singleshot.ssmodpython

"""

HTACCESS_TEMPLATE = """RewriteEngine on

# Change this to match the URI path to this directory (probably an Alias
# unless you are in the DocumentRoot)
RewriteBase @rewritebase@

# Disallow access to certain files (CVS, Makefile, *.cfg)
RewriteRule (^CVS/.*) $1 [F]
RewriteRule (^Makefile) - [F]
RewriteRule (\.cfg) - [F]

RewriteRule ^static/.*.(jpg|css|js|gif)$ - [L]
RewriteRule ^static/(.*) @cgi@/view/$1 [L]

RewriteRule ^@cgi@.* - [L]

# Prevent URIs that arrive directly from view/ from being rewritten
# below to a CGI which will generate the resized image.  Only allow
# resized images accessed through /
RewriteRule ^view/.* - [L]

# A -nnn suffix requests a cached resized version
# Critical that this rule [S]kip any other match-all-images rule
RewriteRule ^(.*)-([1-9][0-9]+)(\.jpg)$ view/$1-$2$3  [NC,S=1]

# Requesting the whole image only gets you the 'full' pixel size, not the full
# file (comment this out if you want to allow access to the large file)
RewriteCond %{REQUEST_FILENAME} -f
RewriteRule ^(.*)(\.jpg)$ view/resize/$1-1200$2 [NC]

# If it's a -nnn suffix request for a cached resized version *AND* that
# size is not yet cached, rewrite to a cgi which will produce it
RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule ^view/(.*)-([1-9][0-9]+)(\.jpg)$   @cgi@/resize/$1$3?size=$2 [L]

RewriteCond %{REQUEST_FILENAME} !-f
RewriteRule .*        @cgi@/view/%{REQUEST_URI} [L,NS]
"""


CGI_TEMPLATE = """#!@python@

@pathhack@

from singleshot import sscgi

sscgi.main(@mainargs@)
"""

SUB_PATTERN = re.compile('@(?P<name>[^@]+)@')

def write_template(subs, template, force, path):
    if os.path.exists(path) and not force:
        print >>sys.stderr, '(not overwriting %s, use --force to force overwrite)' % path
        return

    print 'Writing %s...' % path

    def subrepl(m):
        key = m.group(1)
        return subs[key]

    text = SUB_PATTERN.sub(subrepl, template)
    
    f = open(path, 'w')
    f.write(text)
    f.close()
    

def main():
    parser = OptionParser("usage: %prog [options] --url urlprefix --root directory")
    parser.add_option("--url",
                      action="store",
                      type="string",
                      dest="url",
                      help="(required) The URL prefix for the specified directory (as seen by the web server")
    parser.add_option("--root",
                      action="store",
                      type="string",
                      help="(required) The directory to initialize as a singleshot directory")
    parser.add_option('--path',
                      action="append",
                      type="string",
                      dest="path",
                      help="Prepend path to sys.path for CGI")
    parser.add_option('--templatedir',
                      action="store",
                      type="string",
                      dest="templatedir",
                      help="Use templates in this directory rather than copying defaults into new web root"),
    parser.add_option('--cginame',
                      type="string",
                      dest="cginame",
                      default="singleshot.py",
                      help="Sets the name of the singleshot CGI script")
    parser.add_option("--force",
                      action="store_true",
                      default=False,
                      help="Force overwrite of generated and copied files even if they exist in the destination directory")
                      
    (options, args) = parser.parse_args()

    if not options.root or not options.url:
        parser.error("Please specify both url and root")

#    cgipath = 'singleshot/' + options.cginame
    cgipath = options.cginame    
    cginame = options.cginame

    pathhack = options.path

    if pathhack:
        pathhack.reverse()
    

    try:
        pp = os.environ['PYTHONPATH']
        pp = pp.split(os.path.sep)
        pathhack += pp
    except KeyError:
        pass
            

    if pathhack:
        pathhack = [os.path.abspath(path) for path in pathhack]
        pathhack = "import sys\n" + "\n".join(["sys.path.insert(0, %s)" % repr(path) for path in pathhack])
    else:
        pathhack = ''

    if options.url[0] != '/':
        parser.error('URL should be absolute from the domain root (start with /)')

    if options.url[-1] != '/':
        options.url += '/'

    mainargs = ['baseurl=%s' % repr(options.url),
                'root=%s' % repr(os.path.abspath(options.root))]

    if options.templatedir:
        d = os.path.abspath(options.templatedir)
        mainargs.append('template_root=%s' % repr(d))
    
    subs = {'python' : sys.executable,
            'rewritebase' : options.url[:-1],
            'baseurl' : options.url,
            'cgi' : cgipath,
            'cginame' : cginame,
            'pathhack' : pathhack,
            'mainargs' : ','.join(mainargs)}

#    ssdir = os.path.join(options.root, 'singleshot')
    
#    if not os.path.exists(ssdir):
#        os.makedirs(ssdir)

    write_template(subs, "### begin singleshot\n" + HTACCESS_TEMPLATE + "### end singleshot", options.force,
                   os.path.join(options.root, '.htaccess'))

    cgi = os.path.join(options.root, cgipath)
    write_template(subs, CGI_TEMPLATE, options.force,
                   cgi)


#    write_template(subs, CGI_DIR_HTACCESS, options.force,
#                   os.path.join(ssdir, '.htaccess'))

    os.chmod(cgi, S_IREAD|S_IWRITE|S_IEXEC|S_IRGRP|S_IXGRP|S_IROTH|S_IXOTH)

    viewpath = os.path.join(options.root, 'view')
    if not os.path.exists(viewpath):
        os.makedirs(viewpath)
    
if __name__ == '__main__':
    main()
