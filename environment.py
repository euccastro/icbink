#XXX: proper exception handling
class NotFound(Exception):
    def __init__(self, val):
        self.val = val

class Environment(object):
    def __init__(self, parents, bindings):
        self.parents = parents
        assert isinstance(bindings, dict)
        self.bindings = bindings
    def lookup(self, symbol):
        try:
            return self.bindings[symbol]
        except KeyError:
            for parent in self.parents:
                try:
                    return parent.lookup(symbol)
                except NotFound:
                    pass
            raise NotFound(symbol)

def empty_environment():
    return Environment([], {})

