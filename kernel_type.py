from rpython.rlib import jit


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
        raise KernelTypeError("%s is not callable" % self.tostring())

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

class Ignore(KernelValue):
    @jit.elidable
    def tostring(self):
        return '#ignore'

ignore = Ignore()

class Inert(KernelValue):
    @jit.elidable
    def tostring(self):
        return '#inert'

inert = Inert()

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
    simple = False
    def __init__(self, car, cdr):
        # XXX: specialize for performance?
        assert isinstance(car, KernelValue)
        assert isinstance(cdr, KernelValue)
        self.car = car
        self.cdr = cdr
    def tostring(self):
        return "(%s . %s)" % (self.car.tostring(), self.cdr.tostring())
    def interpret(self, env, cont):
        return self.car, env, CombineCont(self.cdr, env, cont)

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

class ContWrapper(Operative):
    def __init__(self, cont):
        self.cont = cont
    def combine(self, operands, env, cont):
        return abnormally_pass(operands, cont, self.cont)

def abnormally_pass(operands, src_cont, dst_cont):
    dst_cont.mark(True)
    exiting = select_interceptors(src_cont, InnerGuardCont)
    dst_cont.mark(False)
    src_cont.mark(True)
    entering = select_interceptors(dst_cont, OuterGuardCont)
    src_cont.mark(False)
    cont = dst_cont
    for outer, interceptor in entering:
        cont = InterceptCont(interceptor, cont, outer)
    for outer, interceptor in reversed(exiting):
        cont = InterceptCont(interceptor, cont, outer)
    return cont.plug_reduce(operands)

def select_interceptors(cont, cls):
    ls = []
    while cont is not None and not cont.marked:
        if isinstance(cont, cls):
            for guard in iter_list(cont.guards):
                selector, interceptor = pythonify_list(guard)
                if selector.marked:
                    outer_cont = cont if isinstance(cont, OuterGuardCont) else cont.prev
                    ls.append((outer_cont, interceptor))
                    break
        cont = cont.prev
    return ls

class Applicative(Combiner):
    def __init__(self, combiner):
        #XXX: rename to wrapped_combiner
        self.wrapped_combiner = combiner
    def combine(self, operands, env, cont):
        return evaluate_arguments(operands,
                                  env,
                                  ApplyCont(self.wrapped_combiner, env, cont))

class Program(KernelValue):
    """Not a real Kernel value; just to keep RPython happy."""
    def __init__(self, exprs):
        self.data = exprs
    def tostring(self):
        return str([expr.tostring() for expr in self.data])

class NotFound(KernelError):
    def __init__(self, val):
        self.val = val

class Environment(KernelValue):
    def __init__(self, parents, bindings):
        self.parents = parents
        self.bindings = bindings
    def set(self, name, value):
        self.bindings[name] = value
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

class Continuation(KernelValue):
    _immutable_args_ = ['prev']
    def __init__(self, prev):
        self.prev = prev
        self.marked = False
    def plug_reduce(self, val):
        return self.prev.plug_reduce(val)
    def mark(self, boolean):
        self.marked = boolean
        if self.prev is not None:
            self.prev.mark(boolean)

class Done(Exception):
    def __init__(self, value):
        self.value = value

class TerminalCont(Continuation):
    def __init__(self):
        Continuation.__init__(self, None)
    def plug_reduce(self, val):
        raise Done(val)

def evaluate_arguments(vals, env, cont):
    if isinstance(vals, Pair):
        return vals.car, env, EvalArgsCont(vals.cdr, env, cont)
    else:
        return cont.plug_reduce(nil)

class EvalArgsCont(Continuation):
    def __init__(self, exprs, env, prev):
        Continuation.__init__(self, prev)
        self.exprs = exprs
        self.env = env
    def plug_reduce(self, val):
        return evaluate_arguments(self.exprs,
                                  self.env,
                                  GatherArgsCont(val, self.prev))

class GatherArgsCont(Continuation):
    def __init__(self, val, prev):
        Continuation.__init__(self, prev)
        self.val = val
    def plug_reduce(self, val):
        return self.prev.plug_reduce(Pair(self.val, val))

class ApplyCont(Continuation):
    def __init__(self, combiner, env, prev):
        Continuation.__init__(self, prev)
        self.combiner = combiner
        self.env = env
    def plug_reduce(self, args):
        return self.combiner.combine(args, self.env, self.prev)

class CombineCont(Continuation):
    def __init__(self, operands, env, prev):
        Continuation.__init__(self, prev)
        self.operands = operands
        self.env = env
    def plug_reduce(self, val):
        return val.combine(self.operands, self.env, self.prev)

class GuardCont(Continuation):
    def __init__(self, guards, env, prev):
        Continuation.__init__(self, prev)
        self.guards = guards
        self.env = env

class SequenceCont(Continuation):
    def __init__(self, exprs, env, prev):
        Continuation.__init__(self, prev)
        self.exprs = exprs
        self.env = env
    def plug_reduce(self, val):
        return sequence(self.exprs, self.env, self.prev)

def sequence(exprs, env, cont):
    assert isinstance(exprs, Pair)
    if exprs.cdr is nil:
        return exprs.car, env, cont
    else:
        return exprs.car, env, SequenceCont(exprs.cdr, env, cont)

def match_parameter_tree(param_tree, operand_tree, env):
    if isinstance(param_tree, Symbol):
        env.set(param_tree, operand_tree)
    elif param_tree is ignore:
        pass
    elif param_tree is nil:
        assert operand_tree is nil
    elif isinstance(param_tree, Pair):
        assert isinstance(operand_tree, Pair)
        match_parameter_tree(param_tree.car, operand_tree.car, env)
        match_parameter_tree(param_tree.cdr, operand_tree.cdr, env)

class InnerGuardCont(GuardCont):
    pass

class OuterGuardCont(GuardCont):
    pass

class InterceptCont(Continuation):
    def __init__(self, interceptor, next_cont, outer_cont):
        # The outer continuation is the parent of this one for the purposes of
        # abnormal passes, but normal return from this continuation goes to the
        # next interceptor (or to the destination, if this is the last one)
        # instead.
        Continuation.__init__(self, outer_cont)
        self.next_cont = next_cont
        assert isinstance(interceptor, Applicative)
        self.interceptor = interceptor.wrapped_combiner

    def plug_reduce(self, val):
        outer_cont = self.prev
        return self.interceptor.combine(Pair(val, ContWrapper(outer_cont)),
                                        outer_cont.env,
                                        self.next_cont)

def iter_list(vals):
    while isinstance(vals, Pair):
        yield vals.car
        vals = vals.cdr
    assert vals is nil

def pythonify_list(vals):
    ret = []
    for item in iter_list(vals):
        ret.append(item)
    return ret
