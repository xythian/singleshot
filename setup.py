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
      """,
      url= 'http://www.singleshot.org/'
)
