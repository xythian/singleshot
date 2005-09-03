
#
# Provide access to the templates to the initweb script
#


# todo, integrate support for pkg_resources (setuptools)

import os

def all_templates():
    mydir, myname = os.path.split(__file__)
    for name in os.listdir(mydir):
        if name.endswith('.html'):
            yield name, open(os.path.join(mydir, myname)).read()
