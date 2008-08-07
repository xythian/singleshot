#!/usr/bin/env python2.2

import os
import sys
import time
import re
import shutil
import unittest
import Image
from cStringIO import StringIO

#
# Tests for singleshot
#
#

class CommandFailed(object):
    pass

def run_command(cmd):
    r = os.system(cmd)
    if r != 0:
        raise CommandFailed, 'Command failed: %s' % cmd

def sub_httpconf(filename):
    subre = re.compile('@(?P<key>[a-z]+)@')
    subs = {'documentroot' : os.path.abspath('./wwwroot')}
    def replace_key(matchobj):
        key = matchobj.group('key')
        return subs[key]        
    data = open(filename).read()
    data = subre.sub(replace_key, data)
    for tuple in subre.findall(data):
        print tuple
    open(filename, 'w').write(data)

def install_apache():
    os.mkdir("var")
    os.mkdir("logs")
    sub_httpconf('conf/httpd.conf')
    
def install_singleshot():
    if os.path.exists('wwwroot/singleshot'):
        shutil.rmtree('wwwroot/singleshot')
    os.makedirs("wwwroot/singleshot")
    shutil.copytree("singleshot-unpacked/singleshot", "wwwroot/singleshot/singleshot")
    shutil.copy2("singleshot-unpacked/root-htaccess", "wwwroot/singleshot/.htaccess")
    f = open("wwwroot/singleshot/_singleshot.cfg", 'w')
    f.write("""
[paths]
imagemagick=/usr/bin
libjpegbin=/usr/bin
""")
    f.close()
    install_albums('wwwroot/singleshot/')
    

def install_albums(root):
    def album(path, images=None):
        path = os.path.join(root, path)
        if not os.path.exists(path):
            os.makedirs(path)
        for image in images:
            shutil.copy2(image, os.path.join(path, os.path.basename(image)))
    images = os.listdir('images/')
    images = map(lambda x:os.path.join('images/', x), images)
    album('./', images)
    album('./album1', images)
    album('./album2', images)
    album('./album3/album4', images)
    album('./album3/album5', [])
    
    #
    #
    # root
    #   - album 1            # album with images and albums
    #     image1..n
    #     album 2            # album with just images
    #        image1..n
    #     album3             # album with just albums
    #        album4          # album with just images, two levels deep
    #           image1..n
    #        album5          # album with nothing in it
    #     image1             # an image in the root album
    #
    #



class SingleshotTestCase(unittest.TestCase):
    def setUp(self):
        install_singleshot()

    def albumdir(self, dir):
        return os.path.join('wwwroot/singleshot', dir)

    def viewdir(self, dir):
        return os.path.join('wwwroot/singleshot/view', dir)

    def do_url(self, url, comparefile=None, comparere=None):
        f = urllib.urlopen('http://127.0.0.1:58080' + url)
        result = f.read()
        f.close()
        if comparefile:
            self.assertEquals(open(comparefile).read(), result)
        if comparere:
            rex = re.compile(comparere, re.MULTILINE|re.I|re.DOTALL)
#            print comparere
#            print result
            self.assert_(rex.match(result))
        return result
        

    def do_image(self, url, expectWidth, expectHeight):
        f = urllib.urlopen('http://127.0.0.1:58080%s' % url)
        result = f.read()
        f.close()
#        wb = open('/home/fox/www/tmp.jpg', 'wb')
#        wb.write(result)
#        wb.close()
        img = Image.open(StringIO(result))
        width, height = img.size
        self.assertEquals(expectWidth, width)
        self.assertEquals(expectHeight, height)        
        return result

    
#
# Basic operation
# ---------------------------------

#
# Installation
#

class InstallTestCase(SingleshotTestCase):
    def testsimple(self):
        self.do_url('/singleshot/', comparere='.*"/singleshot/album1/".*')
        self.do_url('/singleshot/album1/', comparere='.*/singleshot/album1/rectangle1600x1200.html.*')

    def testresize200(self):
        self.do_image('/singleshot/album1/square400-200.jpg', 200, 200)

    def testresize40(self):
        self.do_image('/singleshot/album1/square400-40.jpg', 40, 40)

    def testresize600(self):
        self.do_image('/singleshot/album1/square400-600.jpg', 400, 400)        

ALLTESTS = [InstallTestCase]

#
# Verify edit mode disabled
#

class VerifyEditModeDisabled(SingleshotTestCase):
    def testeditmodedisabled(self):
        self.do_url('/singleshot/?action=edit', comparere='.*disabled.*')

ALLTESTS.append(VerifyEditModeDisabled)

#
# album tests
#

class AlbumTests(SingleshotTestCase):
    # Fetch album page
    def testalbumfetch(self):
        result = self.do_url('/singleshot/album1/',
                             comparere='.*/singleshot/album1/rectangle1600x1200.html.*')
        # verify links to everything that needs linking from for album1 (images)
        d = self.albumdir('album1')
        for name in os.listdir(d):
            bn, ext = os.path.splitext(name)
            rxp = re.compile('.*"/singleshot/album1/%s.html".*' % bn , re.DOTALL|re.MULTILINE)
            self.assert_(rxp.match(result))        

    def testphoto(self):
        #
        # Fetch photo page
        #    * no cached versions exist        
        result = self.do_url('/singleshot/album1/rectangle1600x1200.html',
                             comparere='.*/singleshot/album1/rectangle1600x1200-600.jpg.*')

        
        # fetch image (generate cached version)
        self.do_image('/singleshot/album1/rectangle1600x1200-600.jpg', 600, 450)

        #    * cached version exists
        self.do_image('/singleshot/album1/rectangle1600x1200-600.jpg', 600, 450)        

        # verify cached version exists
        rawpath = self.albumdir('album1') + '/rectangle1600x1200.jpg'
        cachepath = self.viewdir('album1') + '/rectangle1600x1200-600.jpg'
        self.assert_(os.path.exists(cachepath))

        #    * cached version exists
        self.do_image('/singleshot/album1/rectangle1600x1200-600.jpg', 600, 450)        

        # wait a second to allow the system time to advance...
        # the below test fails if not, since the install and above tests take less than
        # a second

        time.sleep(1.0)

        # touch the raw file
        os.utime(rawpath, None)

        # verify it's later than the cached version
        self.assert_(os.stat(rawpath).st_mtime >  os.stat(cachepath).st_mtime)

        # load the photo page again
        result = self.do_url('/singleshot/album1/rectangle1600x1200.html',
                             comparere='.*/singleshot/album1/rectangle1600x1200-600.jpg.*')

        # verify cached version is gone
        self.assert_(not os.path.exists(cachepath))


ALLTESTS.append(AlbumTests)


class PhotoTests(SingleshotTestCase):
    def testresizer(self):
        #
        # Fetch legal resized photos
        #    * no cached photo exists
        #    * cached photo exists
        #    * photo needs resize
        #    * photo is too small for size
        #
        pass
        
# Fetch illegal photo size
#

#
# Fetch full photo (& check auto-resize)
#    * photo smaller than limit
#    * photo larger than limit
#    * photo equal in size to limit
#

ALLTESTS.append(PhotoTests)

#
# Customizability
# -------------------

#
# _album.cfg
#
#   * title
#   * highlightimage
#   * templates
#   * order
#

def do_url(url, comparefile=None):
    f = urllib.urlopen('http://127.0.0.1:58080%s' % url)
    result = f.read()
    if comparefile:
        if result == open(comparefile).read():
            print '%s OK' % url
        else:
            print '%s FAILED' % url
            print result
    else:
        print result
    f.close()
    return result

    

def suite():
    suites = []
    for s in ALLTESTS:
        suite = unittest.makeSuite(s, 'test')
        suites.append(suite)
    return unittest.TestSuite(tuple(suites))

if __name__ == '__main__':
    install_apache()
    sys.path.insert(0, './singleshot-unpacked/singleshot')
    import process
    import urllib
    run_command("/usr/sbin/apache -d %s -f conf/httpd.conf" % os.path.abspath('.'))
    time.sleep(0.2)
    do_url("/", comparefile="wwwroot/index.html")

    unittest.TextTestRunner(verbosity=2).run(suite())

    time.sleep(0.4)
    run_command("kill `cat var/apache.pid`")
    time.sleep(1.0)
    print open("logs/error.log").read()
    

        
    
    
