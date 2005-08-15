from ssconfig import STORE
from albums import create_item, ItemBase, OrderedItems, ORDERS
from properties import virtual_demand_property
import os
from sets import Set


from taltemplates import write_template

class Tag(object):
    ID = 0
    def __init__(self, name):
        self.name = name
        self.id = Tag.ID
        Tag.ID += 1
        self.items = Set()

    def add(self, item):
        self.items.add(item.path)
    

class TagData(object):
    def __init__(self):
        self._load()

    def _load(self):
        self.tags = {}
        count = 0
        for root, dirs, files in os.walk(STORE.root):            
            for dir in dirs:
                path = os.path.join(root, dir)
                item = create_item(path)
                if not item:
                    # don't visit directories that aren't albums
                    dirs.remove(dir)
            for file in files:
                path = os.path.join(root, file)
                item = create_item(path)
                count += 1
                try:                    
                    for tag in item.keywords:
                        try:
                            self.tags[tag].add(item)
                        except KeyError:
                            t = Tag(tag)
                            t.add(item)
                            self.tags[tag] = t
                except TypeError:
                    pass
                except AttributeError:
                    pass
#        print 'count = %d<br />' % count
#        for key, v in self.tags.items():
#            print '%s = %d<br />' % (key, len(v.items))

    def query(self, tags):
        data = [self.tags[tag].items for tag in tags]
        return reduce(lambda x,y: x.intersection(y), data)        
            
class ImagesByTagItem(ItemBase):
    def __init__(self, tag):
        self.tag = tag
        self.isdir = True
        self.path = '/tag/' + self.tag

    def _load_parent(self):
        return create_item(STORE.root)

    def _get_title(self):
        return 'Tagged with %s' % self.tag

    def _load_items(self):
        items = TagData().query(self.tag.split(','))
        return OrderedItems([create_item(item) for item in items], ORDERS['-mtime'])

    items = virtual_demand_property('items')
    
    def _load_config(self):
        return create_item(STORE.root).config
    
    config = virtual_demand_property('config')


def act(path, form):
    from action_view import invoke
    tag = path
    item = ImagesByTagItem(tag)
    print 'Content-type: text/html'
    print
    write_template(templatekey='album', item=item)
    
