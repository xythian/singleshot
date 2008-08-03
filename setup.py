#!/usr/bin/python
from setuptools import setup, find_packages

setup(name = 'singleshot', version="3.0.0",
      packages=find_packages()
      author = "Ken Fox",
      author_email = "fox@mars.org",
      scripts = ['scripts/singleshotinit.py'],
      install_requires = ["shotweb", "shotlib"],
      url= 'http://www.singleshot.org/'
)
