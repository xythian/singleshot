from ConfigParser import ConfigParser
import os
import fnmatch

from singleshot.storage import FilesystemEntity
from singleshot.properties import demand_property


def read_config(fspath, defaults):
    cfg = ConfigParser()
    for section in defaults.keys():
        cfg.add_section(section)
    for option in defaults[section].keys():
        cfg.set(section, option, str(defaults[section][option]))
    try:
        cfg.read(fspath)
    except:
        pass
    return cfg

class ConfiguredEntity(FilesystemEntity):
    config_filename = None
    defaults = {}

    def _load_config(self):
        cfg = ConfigParser()
        for section in self.defaults.keys():
            cfg.add_section(section)
	    for option in self.defaults[section].keys():
	        cfg.set(section, option, str(self.defaults[section][option]))
        try:
            cfg.read(self._config_path())
        except:
            pass
        return cfg

    def __load_config(self):
        return self._load_config()

    def _config_path(self):
        return [os.path.join(self.path, self.config_filename)]
    
    config = demand_property('config', __load_config)    


class SecurityError(Exception):
    pass



class Store(object):
    def __init__(self, root, template_root=None):
        
        self.root = root                    # is the root
        
        if template_root:
            self.template_root = template_root
        else:
            self.template_root = os.path.join(self.root, 'templates')
        self.image_root = root        
        self.view_root = os.path.join(root, 'view')
        self.page_root = os.path.join(root, 'pages')
        self.static_root = os.path.join(root, 'static')

    def within_root(self, dirname):
        return os.path.abspath(dirname).startswith(self.image_root)

    def check_path(self, path):
        "Note: now accepts URI path instead of %{REQUEST_FILENAME}"
        if path.startswith(CONFIG.url_prefix):
            path = path[len(CONFIG.url_prefix):]
        path = os.path.join(self.image_root, os.path.normpath(path))
        if os.path.isabs(path):
            path = os.path.normpath(path)
        else:
            path = os.path.normpath('/' + path)        
        if not self.within_root(path):
            raise SecurityError, '%s does not start with ROOT (%s)' % (path, self.image_root)
        return path

    def find_template(self, filename):
        return os.path.join(self.template_root, filename)

class SingleshotConfig(ConfiguredEntity):
    defaults = {    'paths' : { 'invokePath' : '/bin:/usr/bin' },
                    'feed' : { 'title' : '',
                              'description' : '',
                               'recentcount' : '10'
                              }
               }
    _default_imagesizes =  {  'mini' : 40,
                             'thumb' : 200,
                          'bigthumb' : 350,
                              'view' : 600,
                             'large' : 1200
                           }

    def __init__(self, store, baseurl='/'):
        super(SingleshotConfig, self).__init__(store.root)
        self.url_prefix = baseurl
        self.store = store


    config_filename = '_singleshot.cfg'

    def getInvokeEnvironment(self):
        return {'PATH' : self.config.get('paths', 'invokePath')}

    def _load_config(self):
        cfg = super(SingleshotConfig, self)._load_config()
        if not cfg.has_section('imagesizes'):
            cfg.add_section('imagesizes')
            for size in self._default_imagesizes.keys():
                cfg.set('imagesizes', size, str(self._default_imagesizes[size]))
        return cfg

    def _get_availableSizes(self):
        return tuple(self.sizeNames.keys())
            
    availableSizes = demand_property('availableSizes', _get_availableSizes)

    def _get_sizeNames(self):
        opts = self.config.options('imagesizes')
        return dict([(int(self.config.get('imagesizes', key)), key) for key in opts ])

    sizeNames = demand_property('sizeNames', _get_sizeNames)

    def ignore_path(self, path):
        name = os.path.basename(path).lower()
        if name == 'cvs':
            return True
        elif path.startswith(self.store.view_root):
            return True
        elif path.startswith(self.store.template_root):
            return True
        elif path.startswith(self.store.page_root):
            return True
        elif path.startswith(self.store.static_root):
            return True
        elif fnmatch.fnmatch(name, '.*'):
            return True
        else:
            return False

def default_loader(store):
    from singleshot.fsloader import FilesystemLoader, SingleshotLoader
    
    fl = FilesystemLoader(store)
    ssl = SingleshotLoader(store, fl)
    return ssl

def create_store(root,
                 baseurl='/singleshot',
                 template_root=None,
                 loader=default_loader):
    from singleshot.views import ViewLoader
    from singleshot import imageprocessor

    store = Store(root, template_root=template_root)    
    store.config = SingleshotConfig(store, baseurl=baseurl)    
    store.loader = loader(store)
    store.load_view = ViewLoader(store).load_view
    store.processor = imageprocessor.create(store)
    return store



