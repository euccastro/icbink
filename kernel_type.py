from rpython.rlib import jit

class KernelObject(object):
    simple = True
    def equal(self, other):
        return other is self
    @jit.elidable
    def eq(self, other):
        return other is self
    def tostring(self):
        return str(self)
    def interpret(self, env, cont):
        assert self.simple
        return cont.plug_reduce(self.interpret_simple(env))
    def interpret_simple(self, env):
        return self

#XXX: Unicode
class String(KernelObject):
    _immutable_fields_ = ['value']
    def __init__(self, value):
        assert isinstance(value, str)
        self.value = value
    @jit.elidable
    def tostring(self):
        return '"%s"' % self.value

#XXX: Unicode
class Symbol(KernelObject):

    _immutable_fields_ = ['value']

    def __init__(self, value):
        assert isinstance(value, str)
        self.value = value

    @jit.elidable
    def tostring(self):
        return self.value

    symbol_table = {}
    @classmethod
    @jit.elidable
    def get_interned(cls, name):
        try:
            return cls.symbol_table[name]
        except KeyError:
            ret = cls.symbol_table[name] = Symbol(name)
            return ret
    def interpret_simple(self, env):
        return env.lookup(self)

class Nil(KernelObject):
    @jit.elidable
    def tostring(self):
        return "()"

nil = Nil()

class Boolean(KernelObject):
    _immutable_fields_ = ['value']
    def __init__(self, value):
        assert isinstance(value, bool)
        self.value = value
    @jit.elidable
    def tostring(self):
        return '#t' if self.value else '#f'

true = Boolean(True)
false = Boolean(False)

class Pair(KernelObject):
    _immutable_fields_ = ['car', 'cdr']
    def __init__(self, car, cdr):
        # XXX: specialize for performance?
        assert isinstance(car, KernelObject)
        assert isinstance(cdr, KernelObject)
        self.car = car
        self.cdr = cdr
    def tostring(self):
        return "(%s . %s)" % (self.car.tostring(), self.cdr.tostring())

class Program(KernelObject):
    """Not a real Kernel value; just to keep RPython happy."""
    def __init__(self, exprs):
        self.exprs = exprs
    def tostring(self):
        return str([expr.tostring() for expr in self.exprs])
