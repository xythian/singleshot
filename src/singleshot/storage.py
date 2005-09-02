from singleshot.properties import *
import os

class FilesystemEntity(object):
    def __init__(self, path):
        self.__path = path
        super(FilesystemEntity, self).__init__()        

    def _get_path(self):
        return self.__path

    def _get_basename(self):
        return os.path.basename(self.path)

    def _get_dirname(self):
        return os.path.dirname(self.path)

    def _get_filename(self):
        return os.path.splitext(self.basename)[0]

    def _get_extension(self):
        return os.path.splitext(self.basename)[1]

    def _load_st_info(self):
        return self.stat()

    def _get_isdir(self):
        return os.path.isdir(self.path)

    def _get_exists(self):
        return os.path.exists(self.path)

    st_info = demand_property('st_info', _load_st_info)
    mtime = delegate_property('st_info', 'st_mtime')
    dirname = property(_get_dirname)
    basename = property(_get_basename)
    extension = property(_get_extension)
    filename = property(_get_filename)
    path = property(_get_path)
    isdir = property(_get_isdir)
    exists = property(_get_exists)

    def stat(self):
        return os.stat(self.path)
