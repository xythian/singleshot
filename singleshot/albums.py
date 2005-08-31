# $Id$

from views import ViewLoader
from fsloader import FilesystemLoader, load_item, MemoizeLoader

li = MemoizeLoader(load_item).load_item

ITEMLOADER = FilesystemLoader(load_item=li)

load_view = ViewLoader(ITEMLOADER.load_item).load_view
create_item = load_view
