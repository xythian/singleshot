#!/usr/bin/env python

import sys
from optparse import OptionParser
import re
import os
from stat import *
from glob import glob

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
PythonOption template_root @templatedir@
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

# Requesting the whole image only gets you the '1200' pixel size, not the full
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

# change show_exceptions to True to enable cgitb exceptions
sscgi.main(show_exceptions=False, @mainargs@)
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

def build_zip(dest):
    print 'Writing',dest
    from zipfile import PyZipFile
    f = PyZipFile(dest, 'w')
    f.writepy('src/singleshot')
    f.writepy('lib')
    f.writepy('lib/simpletal')    
    f.close()
        
def main():
    path, fn = os.path.split(__file__)
    parent, name = os.path.split(path)
    unpack_root = None
    if name == 'scripts':
        unpack_root = parent
        # probably running in the unpacked source tree
        # add lib and src to path
        sys.path.insert(0, os.path.join(parent, 'lib'))
        sys.path.insert(0, os.path.join(parent, 'src'))
        from singleshot import templates
        
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
                      help="Include directory on the path")
    parser.add_option('--templatedir',
                      action="store",
                      type="string",
                      dest="templatedir",
                      help="Use templates in this directory rather than copying defaults into new web root"),
    parser.add_option('--cginame',
                      type="string",
                      dest="cginame",
                      default="singleshot.cgi",
                      help="Sets the name of the singleshot CGI script")
    parser.add_option('--standalone',
                      action='store_true',
                      help="Package up the singleshot and support libraries and put them in the web root as standalone libraries (this only works when run from the unpacked tarball.")
    parser.add_option('--modpython',
                      action='store_true',
                      default=False,
                      help="Includes the mod_python directives in .htaccess")
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

    pathparts = options.path

    if pathparts:
        pathparts.reverse()
        for part in pathparts: sys.path.insert(0, part)
    else:
        pathparts = []

    try:
        pp = os.environ['PYTHONPATH']
        pp = pp.split(os.path.sep)
        pathparts += pp
    except KeyError:
        pass

    if options.url[0] != '/':
        parser.error('URL should be absolute from the domain root (start with /)')

    if options.url[-1] != '/':
        options.url += '/'

    mainargs = ['baseurl=%s' % repr(options.url),
                'root=%s' % repr(os.path.abspath(options.root))]
    if options.standalone and options.modpython:
        parser.error('--standalone and --modpython are not compatible :-(')

    if options.standalone:
        if unpack_root is None:
            parser.error("It doesn't look like I'm being run from the tarball unpack directory.  I don't know how to build the zip file.")
        dest = os.path.join(options.root, '.singleshot')
        if not os.path.exists(dest):
            os.makedirs(dest)
        zippath = os.path.join(dest, 'singleshot.zip')
        build_zip(zippath)
        pathparts.insert(0, zippath)

    if pathparts:
        pathparts = [os.path.abspath(path) for path in pathparts]
        pathhack = "import sys\n" + "\n".join(["sys.path.insert(0, %s)" % repr(path) for path in pathparts])
    else:
        pathhack = ''


    if options.templatedir:
        tmplroot = os.path.abspath(options.templatedir)
        mainargs.append('template_root=%s' % repr(tmplroot))
    else:
        tmplroot = os.path.abspath(os.path.join(options.root, 'templates'))
        if not os.path.exists(tmplroot):
            os.makedirs(tmplroot)
        for path in pathparts:
            if path not in sys.path:                
                sys.path.insert(0, path)
                
        try:
            from singleshot import templates
            for name, data in templates.all_templates():
                path = os.path.join(tmplroot, name)
                if not os.path.exists(path):
                    print 'Writing',path,'...'
                    open(path, 'w').write(data)
                else:
                    print 'Skipping',path,'...'
        except ImportError:
            print >>sys.stderr, 'Unable to find templates.  Ensure singleshot is on the path?'

            
        
    subs = {'python' : sys.executable,
            'rewritebase' : options.url[:-1],
            'baseurl' : options.url,
            'root' : os.path.abspath(options.root),
            'templatedir' : tmplroot,
            'cgi' : cgipath,
            'cginame' : cginame,
            'pathparts' : repr(pathparts).replace(' ',''),
            'pathhack' : pathhack,
            'mainargs' : ','.join(mainargs)}

    httmpl = HTACCESS_TEMPLATE
    if options.modpython:
        httmpl = MODPYTHON_CLAUSE + httmpl
    httmpl = "### begin singleshot\n" + httmpl + "### end singleshot"
    write_template(subs, httmpl, options.force,
                   os.path.join(options.root, '.htaccess'))

    cgi = os.path.join(options.root, cgipath)
    write_template(subs, CGI_TEMPLATE, options.force,
                   cgi)


    os.chmod(cgi, S_IREAD|S_IWRITE|S_IEXEC|S_IRGRP|S_IXGRP|S_IROTH|S_IXOTH)

    viewpath = os.path.join(options.root, 'view')
    if not os.path.exists(viewpath):
        os.makedirs(viewpath)

    
if __name__ == '__main__':
    main()
