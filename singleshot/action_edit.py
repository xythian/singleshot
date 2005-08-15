#!/usr/bin/env python2.2

import shutil
import os.path
from templates import create_template
import albums
from action_view import act

def invoke(dir, image, form, cookie):

    print 'Content-type: text/html'

    if albums.CONFIG.editEnabled != 'true':
        print """
<html>
<head>
<title>Edit mode is disabled</title>
<body>
<h1>Edit mode is disabled</h1>

To enable it, add lines to _singleshot.cfg like this:
<blockquote>
<pre>
[edit]
password=*a password*
enabled=true
</pre>
</blockquote>

</body>
"""
        return 0

    # get the password
    password = form.getfirst('password')
    if not password:
        try:
            password = cookie['password'].value
        except KeyError:
            password = ""

    if password != albums.CONFIG.editPassword:
        # wrong or no password supplied, ask again
        print '''
              <form method="post">
              <input type=hidden name="action" value="edit">
              Password: <input type=text name=password value="%s">
              </form>
              ''' % password
    else:
        # save the password so we don't have to re-enter it
        cookie["password"] = password

        if dir and image and form.has_key("highlightimage"):
            dir.highlightimagename = form.getfirst("highlightimage","")

        if dir and form.has_key("uploadfile"):
            uploadedfiles = form["uploadfile"]
	    if not isinstance(uploadedfiles, type([])):
    	        uploadedfiles = [ uploadedfiles ]

            for newfile in uploadedfiles:
                if newfile.file and newfile.filename:
                    outfilename = os.path.join(dir.path,os.path.basename(newfile.filename))
                    outfile = open(outfilename, "wb")
                    # It's an uploaded file; keep from having to hold the entire thing in memory
		    shutil.copyfileobj(newfile.file, outfile)
                    outfile.close()

        # handle image-only modifications
        if image and form.has_key("rotate"):
            if image.rotate(int(form.getfirst('rotate',''))):
                #'Invalid rotation spec.'
                pass

        # handle image-or-dir modifications
        item = image or dir
        if form.has_key("savecomment"):
            item.update_comment(form.getfirst("comment",""))

        print cookie
        print
        print create_template(templatekey='albumedit', image=image, directory=dir)




