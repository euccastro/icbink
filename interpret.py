from rpython.rlib import jit

import parse


class KernelError(Exception):
    def __init__(self, msg):
        self.msg = msg

class KernelTypeError(KernelError):
    pass

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

class Combiner(KernelValue):
    pass

class Operative(Combiner):
    pass

class Primitive(Operative):
    def __init__(self, code):
        self.code = code
    def combine(self, operands, env, cont):
        return self.code(operands, env, cont)

class SimplePrimitive(Operative):
    def __init__(self, code):
        self.code = code
    def combine(self, operands, env, cont):
        return cont.plug_reduce(self.code(operands))

class Applicative(Combiner):
    def __init__(self, combiner):
        self.combiner = combiner
    def combine(self, operands, env, cont):
        return evaluate_arguments(operands,
                                  env,
                                  ApplyContinuation(self.combiner, env, cont))

class Program(KernelValue):
    """Not a real Kernel value; just to keep RPython happy."""
    def __init__(self, exprs):
        self.exprs = exprs
    def tostring(self):
        return str([expr.tostring() for expr in self.exprs])

class Continuation(KernelValue):
    pass

class NotFound(KernelError):
    def __init__(self, val):
        self.val = val

class Environment(KernelValue):
    def __init__(self, parents, bindings):
        self.parents = parents
        self.bindings = bindings
    def lookup(self, symbol):
        try:
            ret = self.bindings[symbol]
            return ret
        except KeyError:
            for parent in self.parents:
                try:
                    ret = parent.lookup(symbol)
                    return ret
                except NotFound:
                    pass
            raise NotFound(symbol)

def empty_environment():
    return Environment([], {})

def _simple_applicative(fn):
    return Applicative(SimplePrimitive(fn))

_ground_environment = Environment(
    [],
    {'string-append': _simple_applicative(string_append)})


class Done(Exception):
    def __init__(self, value):
        self.value = value

class TerminalCont(Continuation):
    def plug_reduce(self, val):
        raise Done(val)

class EvalArgsCont(Continuation):
    def __init__(self, vals, env, cont):
        self.vals = vals
        self.env = env
        self.prev = cont
    def plug_reduce(self, val):
        return evaluate_arguments(self.vals.cdr,
                                  self.env,
                                  GatherArgsCont(val, self.prev))

class GatherArgsCont(Continuation):
    def __init__(self, val, prev):
        self.val = val
        self.prev = prev
    def plug_reduce(self, val):
        return self.prev.plug_reduce(Pair(self.val, val))


class ApplyCont(Continuation):
    def __init__(self, combiner, env, prev):
        self.combiner = combiner
        self.env = env
        self.prev = prev
    def plug_reduce(self, args):
        return self.combiner.combine(args, self.env, self.prev)

def run_one_expr(val, env):
    cont = continuation.TerminalContinuation()
    try:
        while True:
            driver.jit_merge_point(val=val, env=env, cont=cont)
            val, env, cont = val.interpret(env, cont)
    except continuation.Done as e:
        return e.value

def get_printable_location(green_val):
    if green_val is None:
        return "No green val"
    else:
        return green_val.tostring()
driver = jit.JitDriver(reds=['env', 'cont'],
                       greens=['val'],
                       get_printable_location=get_printable_location)

def evaluate_arguments(vals, env, cont):
    if isinstance(vals, Pair):
        return vals.car, env, continuation.EvalArgsCont(vals, env, cont)
    else:
        return cont.plug_reduce(nil)

if __name__ == '__main__':
    expr, = parse.parse('"test"').exprs
    result = run_one_expr(expr, environment.empty_environment())
    assert isinstance(result, String)
    assert result.value == 'test'
    print "All OK."
