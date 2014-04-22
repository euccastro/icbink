import kernel_type as kt

#XXX: proper exception handling
class NotFound(Exception):
    def __init__(self, val):
        self.val = val

class Environment(object):
    def __init__(self, parents, bindings):
        self.parents = parents
        self.bindings = bindings
    def lookup(self, symbol):
        try:
            ret = self.bindings[symbol]
            assert isinstance(ret, kt.KernelObject)
            return ret
        except KeyError:
            for parent in self.parents:
                try:
                    ret = parent.lookup(symbol)
                    assert isinstance(ret, kt.KernelObject)
                    return ret
                except NotFound:
                    pass
            raise NotFound(symbol)

def empty_environment():
    return Environment([], {})

