from rpython.rlib import jit

class KernelTypeError(Exception):
    def __init__(self, msg):
        self.msg = msg

class KernelValue(object):
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
    def combine(self, operands, env, cont):
        raise KernelTypeError("%s %s is not callable"
                              % (self.__class__.__name__,
                                 self.tostring()))

#XXX: Unicode
class String(KernelValue):
    _immutable_fields_ = ['value']
    def __init__(self, value):
        assert isinstance(value, str)
        self.value = value
    @jit.elidable
    def tostring(self):
        return '"%s"' % self.value

#XXX: Unicode
class Symbol(KernelValue):

    _immutable_fields_ = ['value']

    def __init__(self, value):
        assert isinstance(value, str)
        self.value = value

    @jit.elidable
    def tostring(self):
        return self.value

    def interpret_simple(self, env):
        return env.lookup(self)

_symbol_table = {}

def get_interned(name):
    try:
        return _symbol_table[name]
    except KeyError:
        ret = _symbol_table[name] = Symbol(name)
        return ret

class Nil(KernelValue):
    @jit.elidable
    def tostring(self):
        return "()"

nil = Nil()

class Boolean(KernelValue):
    _immutable_fields_ = ['value']
    def __init__(self, value):
        assert isinstance(value, bool)
        self.value = value
    @jit.elidable
    def tostring(self):
        return '#t' if self.value else '#f'

true = Boolean(True)
false = Boolean(False)

class Pair(KernelValue):
    _immutable_fields_ = ['car', 'cdr']
    def __init__(self, car, cdr):
        # XXX: specialize for performance?
        assert isinstance(car, KernelValue)
        assert isinstance(cdr, KernelValue)
        self.car = car
        self.cdr = cdr
    def tostring(self):
        return "(%s . %s)" % (self.car.tostring(), self.cdr.tostring())

class Program(KernelValue):
    """Not a real Kernel value; just to keep RPython happy."""
    def __init__(self, exprs):
        self.exprs = exprs
    def tostring(self):
        return str([expr.tostring() for expr in self.exprs])
