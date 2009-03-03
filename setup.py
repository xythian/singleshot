#!/usr/bin/python
from setuptools import setup, find_packages

# need more than one packaging
# the all-egg packaging with all dependencies suitable for PyPI
# the debian packages

# depends on pytz, imagemagick

setup(name = 'singleshot', version="3.0.0",
      packages=find_packages(),
      author = "Ken Fox",
      author_email = "fox@mars.org",
      scripts = ['scripts/singleshotinit.py'],
      install_requires = ["shotweb", "shotlib"],
      entry_points = """
         [singleshot.actions]
         rss = singleshot.action_rss:handle

         [singleshot.handlers]
         .flv = singleshot.handlers.flv:FLVHandler
         image/jpeg = singleshot.handlers.magick:ImageMagickHandler
         image/png = singleshot.handlers.magick:ImageMagickHandler
         image/gif = singleshot.handlers.magick:ImageMagickHandler         

         [singleshot.readers]
         image/jpeg = singleshot.jpeg:JpegHeader
      """,
      url= 'http://www.singleshot.org/'
)
