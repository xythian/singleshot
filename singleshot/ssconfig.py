from ConfigParser import ConfigParser
from properties import *
from storage import FilesystemEntity
import os
import fnmatch

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


class Store(object):
    def __init__(self):
        root = os.path.dirname(sys.argv[0]) # the cgi path
        root = os.path.abspath(root)        # the cgi directory
        root = os.path.dirname(root)        # its parent
        self.root = root                    # is the root
        
        self.ss_root = os.path.join(root, 'singleshot')
        self.template_root = os.path.join(self.ss_root, 'templates')
        self.image_root = root
        self.view_root = os.path.join(root, 'view')

    def within_root(self, dirname):
        return os.path.abspath(dirname).startswith(self.image_root)

    def find_template(self, filename):
        return os.path.join(self.template_root, filename)

STORE = Store()


class SingleshotConfig(ConfiguredEntity):
    defaults = { 'singleshot': { 'url_prefix' : '/singleshot/',
                                 'ss_uri' : ''
                               },
                 'templates' : { 'view' : 'view.tmpl',
                                 'album' : 'album.tmpl',
                                 'albumedit' : 'albumedit.tmpl',
                               },
                     'paths' : { 'imagemagick' : '/usr/bin',
                                 'libjpegbin' : '/usr/bin',
                                 'invokepath' : '/bin:/usr/bin',
                                },
                      'edit' : { 'password' : 'singleshot',
                                 'enabled' : 'false'
		               }
              }
    _default_imagesizes =  {  'mini' : 40,
                             'thumb' : 200,
                              'view' : 600,
                              'full' : 1200
                           }

    def _get_ssuri(self):
        result = self.config.get('singleshot', 'ss_uri')
	if result:
	    return result
	return self.url_prefix + 'singleshot'

    config_filename = '_singleshot.cfg'
    url_prefix = config_property('url_prefix', 'singleshot')
    ssuri = property(_get_ssuri)

    viewTemplate = config_property('view', 'templates')
    albumTemplate = config_property('album', 'templates')
    albumEditTemplate = config_property('albumedit', 'templates')

    imagemagickPath = config_property('imagemagick', 'paths')
    libjpegbinPath = config_property('libjpegbin', 'paths')
    invokePath = config_property('invokepath', 'paths')

    editPassword = config_property('password', 'edit')
    editEnabled = config_property('enabled', 'edit')

    def getInvokeEnvironment(self):
        return {'PATH' : self.invokePath}

    def _load_config(self):
        cfg = super(SingleshotConfig, self)._load_config()
        if not cfg.has_section('imagesizes'):
            cfg.add_section('imagesizes')
            for size in self._default_imagesizes.keys():
                cfg.set('imagesizes', size, str(self._default_imagesizes[size]))
        return cfg

    def _get_availableSizes(self):
        return tuple(self.sizeNames.keys())
        # keep this because, quoth Ken: "availalbe sizes may be a superset of named sizes"
        opts = self.config.options('imagesizes')
        return [int(self.config.get('imagesizes', key)) for key in opts]
            
    availableSizes = demand_property('availableSizes', _get_availableSizes)

    def _get_sizeNames(self):
        opts = self.config.options('imagesizes')
        return dict([(int(self.config.get('imagesizes', key)), key) for key in opts ])

    sizeNames = demand_property('sizeNames', _get_sizeNames)

    def ignore_path(self, path):
        name = os.path.basename(path).lower()
        if name == 'cvs':
            return True
        elif path in (STORE.view_root, STORE.ss_root):
            return True
        elif fnmatch.fnmatch(name, '.*'):
            return True
        else:
            return False

CONFIG = SingleshotConfig(STORE.root)
