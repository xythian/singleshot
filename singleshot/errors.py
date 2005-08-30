from ssconfig import CONFIG, STORE
from simpletal.simpleTALES import PathFunctionVariable
from taltemplates import ViewableObject
import action_static
import sys

class MessagePage(ViewableObject):
    viewname = 'message'
    
    def __init__(self, form, **other):
        self.form = form
        self.other = other
        
    def create_context(self):
        context = super(MessagePage, self).create_context()
        context.addGlobal("form", self.form)
        context.addGlobal("config", CONFIG)
        context.addGlobal("ssuri", PathFunctionVariable(lambda x:CONFIG.ssuri + '/' + x))
        context.addGlobal("ssroot", PathFunctionVariable(lambda x:CONFIG.url_prefix + x))
        for key, val in self.other.items():
            context.addGlobal(key, val)
        return context

class PageNotFound(MessagePage):
    viewname = '404'
    http_status = '404 Not Found'


def return_404(path, form):
    if action_static.exists('404'):
        action_static.act('404', form)
    else:
        page = PageNotFound(form, path=path)
        page.cgi_view(sys.stdout)
