#
# Define plugin mechanism for actions
#

from pkg_resources import iter_entry_points

def find_action(name):
    candidates = list(iter_entry_points("singleshot.actions", name))
    if candidates:
        return candidates[-1].load()
    return None


def load_actions():
    actions = {}
    for act in iter_entry_points("singleshot.actions"):
        actions[act.name] = act.load()
    return actions

    
