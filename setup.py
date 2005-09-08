from distutils.core import setup

setup(name = 'singleshot', version="2.0.0rc5",
      packages=["singleshot", "singleshot.templates", "simpletal", ""],
      author = "Ken Fox",
      author_email = "fox@mars.org",
      scripts = ['scripts/singleshotinit.py'],
      url= 'http://www.singleshot.org/',
      py_modules = ['PyRSS2Gen'],
      package_dir = {"simpletal" : 'lib/simpletal',
                     '' : 'lib',
                     'singleshot' : 'src/singleshot'}
)
