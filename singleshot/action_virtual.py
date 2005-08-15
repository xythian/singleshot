#
# Handles 'files' that are figments of Singleshot's imagination
#

#
# For example, tag
#

from ssconfig import CONFIG, STORE

from simpletal import simpleTAL, simpleTALES

from simpletal.simpleTALES import PathFunctionVariable

from taltemplates import load_template
import sys

def return_404(path, form):
    print 'Content-type: text/html'
    print 'Status: 404 Not Found'
    print
    tl = load_template(STORE.find_template('404.html'))
    context = simpleTALES.Context()
    context.addGlobal("path", path)
    context.addGlobal("form", form)
    context.addGlobal("config", CONFIG)
    context.addGlobal("ssuri", PathFunctionVariable(lambda x:CONFIG.ssuri + '/' + x))
    context.addGlobal("ssroot", PathFunctionVariable(lambda x:CONFIG.url_prefix + x))
    tl.expand(context, sys.stdout)
    

def act(path, form):
    from action_view import invoke
    realpath = path
    if path.startswith(CONFIG.url_prefix):
        path = path[len(CONFIG.url_prefix):]
    try:
        slash = path.index('/')
        action = path[:slash]
        path = path[slash+1:]
    except ValueError:
        return return_404(realpath, form)

    try:
        actionmodule = __import__('action_' + action, globals(), locals())
    except ImportError:
        return return_404(realpath, form)

    # invoke the action handler
    actionmodule.act(path, form)
    
    
