#!/usr/bin/env python2.2

from templates import create_template

def invoke(dir, item, form, cookie):

    if item:
        tmplname = 'view'
    else:
        tmplname = 'album'
    tmpl = create_template(templatekey=tmplname, image=item, directory=dir)
    print 'Content-type: text/html'
    print
    print tmpl

