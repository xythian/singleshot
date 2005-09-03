from distutils.core import setup

setup(name = 'singleshot', version="2.0.0rc1",
      packages=["singleshot", "simpletal", ""],
      author = "Ken Fox",
      author_email = "fox@mars.org",
      scripts = ['scripts/singleshotinit.py'],
      url= 'http://www.singleshot.org/',
      py_modules = ['EXIF', 'PyRSS2Gen'],
      package_dir = {"simpletal" : 'lib/simpletal',
                     '' : 'lib',
                     'singleshot' : 'src/singleshot'},
)
