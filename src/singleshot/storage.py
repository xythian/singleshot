from singleshot.properties import demand_property, delegate_property

from os import stat
from os.path import basename, dirname, splitext, isdir, exists, join

class FileInfo(object):
    def __init__(self, path, rest=None):
        if rest:
            path = join(path, rest)
        self.__path = path
        super(FileInfo, self).__init__()        

    def _get_path(self):
        return self.__path

    def _get_basename(self):
        return basename(self.path)

    def _get_dirname(self):
        return dirname(self.path)

    def _get_filename(self):
        return splitext(self.basename)[0]

    def _get_extension(self):
        return splitext(self.basename)[1]

    def _load_st_info(self):
        return self.stat()

    def _get_isdir(self):
        return isdir(self.path)

    def _get_exists(self):
        return exists(self.path)

    def isa(self, ext):
        return self.extension.lower() == ext

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
        return stat(self.path)

class FilesystemEntity(FileInfo):
    pass
