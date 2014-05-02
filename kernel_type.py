from itertools import product

from rpython.rlib import jit
from rpython.rlib import rstring


class KernelError(Exception):
    def __init__(self, msg):
        self.msg = msg
    def __str__(self):
        return self.msg

class KernelTypeError(KernelError):
    pass

class KernelValue(object):
    simple = True
    def __init__(self, source_pos=None):
        self.source_pos = source_pos
    def equal(self, other):
        return other is self
    def tostring(self):
        return str(self)
    def todisplay(self):
        return self.tostring()
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
    def __init__(self, value, source_pos=None):
        assert isinstance(value, str)
        self.value = value
        self.source_pos = source_pos
    @jit.elidable
    def tostring(self):
        return '"%s"' % self.value
    def todisplay(self):
        return self.value
    def equal(self, other):
        return isinstance(other, String) and other.value == self.value

#XXX: Unicode
class Symbol(KernelValue):

    _immutable_fields_ = ['value']

    def __init__(self, value, source_pos=None):
        assert isinstance(value, str)
        self.value = value
        self.source_pos = source_pos

    @jit.elidable
    def tostring(self):
        return self.value

    def interpret_simple(self, env):
        return env.lookup(self)

    def equal(self, other):
        return isinstance(other, Symbol) and other.value == self.value

_symbol_table = {}

def get_interned(name):
    try:
        return _symbol_table[name]
    except KeyError:
        ret = _symbol_table[name] = Symbol(name)
        return ret

class Null(KernelValue):
    @jit.elidable
    def tostring(self):
        return "()"
    def equal(self, other):
        return isinstance(other, Null)

nil = Null()

def is_nil(kv):
    return nil.equal(kv)

class Ignore(KernelValue):
    @jit.elidable
    def tostring(self):
        return '#ignore'
    def equal(self, other):
        return isinstance(other, Ignore)

ignore = Ignore()

def is_ignore(kv):
    return ignore.equal(kv)

class Inert(KernelValue):
    @jit.elidable
    def tostring(self):
        return '#inert'
    def equal(self, other):
        return isinstance(other, Inert)

inert = Inert()

def is_inert(kv):
    return inert.equal(kv)

class Boolean(KernelValue):
    _immutable_fields_ = ['value']
    def __init__(self, value, source_pos=None):
        assert isinstance(value, bool)
        self.value = value
        self.source_pos = source_pos
    @jit.elidable
    def tostring(self):
        return '#t' if self.value else '#f'
    def equal(self, other):
        return isinstance(other, Boolean) and other.value == self.value

true = Boolean(True)
false = Boolean(False)

def is_true(kv):
    return true.equal(kv)

def is_false(kv):
    return false.equal(kv)

class Pair(KernelValue):
    _immutable_fields_ = ['car', 'cdr']
    simple = False
    def __init__(self, car, cdr, source_pos=None):
        # XXX: specialize for performance?
        assert isinstance(car, KernelValue)
        assert isinstance(cdr, KernelValue)
        self.car = car
        self.cdr = cdr
        self.source_pos = source_pos
    def tostring(self):
        s = rstring.StringBuilder()
        s.append("(")
        pair = self
        while True:
            assert isinstance(pair, Pair)
            s.append(pair.car.tostring())
            if isinstance(pair.cdr, Pair):
                pair = pair.cdr
                s.append(" ")
            else:
                if pair.cdr is not nil:
                    s.append(" . ")
                    s.append(pair.cdr.tostring())
                break
        s.append(")")
        return s.build()
    def interpret(self, env, cont):
        return self.car, env, CombineCont(self.cdr, env, cont)
    def equal(self, other):
        return (isinstance(other, Pair)
                and self.car.equal(other.car)
                and self.cdr.equal(other.cdr))

class Combiner(KernelValue):
    def combine(self, operands, env, cont):
        raise NotImplementedError

class Operative(Combiner):
    pass

class CompoundOperative(Operative):
    def __init__(self, formals, eformal, exprs, static_env, source_pos=None):
        self.formals = formals
        self.eformal = eformal
        self.exprs = exprs
        self.static_env = static_env
        self.source_pos = source_pos
    def combine(self, operands, env, cont):
        eval_env = Environment([self.static_env])
        match_parameter_tree(self.formals, operands, eval_env)
        match_parameter_tree(self.eformal, env, eval_env)
        return sequence(self.exprs, eval_env, cont)

class Primitive(Operative):
    def __init__(self, code):
        self.code = code
        self.source_pos = None
    def combine(self, operands, env, cont):
        return self.code(operands, env, cont)

class SimplePrimitive(Operative):
    def __init__(self, code):
        self.code = code
        self.source_pos = None
    def combine(self, operands, env, cont):
        return cont.plug_reduce(self.code(operands))

class ContWrapper(Operative):
    def __init__(self, cont, source_pos=None):
        self.cont = cont
        self.source_pos = source_pos
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
    def __init__(self, combiner, source_pos=None):
        #XXX: rename to wrapped_combiner
        assert isinstance(combiner, Combiner)
        self.wrapped_combiner = combiner
        self.source_pos = source_pos
    def combine(self, operands, env, cont):
        return evaluate_arguments(operands,
                                  env,
                                  ApplyCont(self.wrapped_combiner, env, cont))

class Program(KernelValue):
    """Not a real Kernel value; just to keep RPython happy."""
    def __init__(self, exprs):
        self.data = exprs
        self.source_pos = None
    def tostring(self):
        return str([expr.tostring() for expr in self.data])

class NotFound(KernelError):
    _immutable_vars_ = ['val']
    def __init__(self, val):
        assert isinstance(val, str)
        self.val = val
    def __str__(self):
        return "Symbol not found: %s" % self.val

class Environment(KernelValue):
    def __init__(self, parents, bindings=None, source_pos=None):
        self.parents = parents
        self.bindings = bindings or {}
        self.source_pos = source_pos
    def set(self, symbol, value):
        assert isinstance(symbol, Symbol)
        self.bindings[symbol.value] = value
    def lookup(self, symbol):
        assert isinstance(symbol, Symbol)
        try:
            ret = self.bindings[symbol.value]
            return ret
        except KeyError:
            for parent in self.parents:
                try:
                    ret = parent.lookup(symbol)
                    return ret
                except NotFound:
                    pass
            raise NotFound(symbol.value)

class Continuation(KernelValue):
    _immutable_args_ = ['prev']
    def __init__(self, prev, source_pos=None):
        self.prev = prev
        self.marked = False
        self.source_pos = source_pos
    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        return self.prev.plug_reduce(val)
    def mark(self, boolean):
        self.marked = boolean
        if self.prev is not None:
            self.prev.mark(boolean)

def trace(*args):
    import primitive
    primitive.trace(*args)

class Done(Exception):
    def __init__(self, value):
        self.value = value

class TerminalCont(Continuation):
    def __init__(self, source_pos=None):
        Continuation.__init__(self, None)
        self.source_pos = source_pos
    def plug_reduce(self, val):
        raise Done(val)

def evaluate_arguments(vals, env, cont):
    if isinstance(vals, Pair):
        return vals.car, env, EvalArgsCont(vals.cdr, env, cont)
    else:
        return vals, env, cont

class EvalArgsCont(Continuation):
    def __init__(self, exprs, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.exprs = exprs
        self.env = env
        self.source_pos = source_pos
    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        return evaluate_arguments(self.exprs,
                                  self.env,
                                  GatherArgsCont(val, self.prev))

class GatherArgsCont(Continuation):
    def __init__(self, val, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.val = val
        self.source_pos = source_pos
    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        return self.prev.plug_reduce(Pair(self.val, val))

class ApplyCont(Continuation):
    def __init__(self, combiner, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.combiner = combiner
        self.env = env
        self.source_pos = source_pos
    def plug_reduce(self, args):
        trace(":: plugging", args.tostring())
        return self.combiner.combine(args, self.env, self.prev)

class CombineCont(Continuation):
    def __init__(self, operands, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.operands = operands
        self.env = env
        self.source_pos = source_pos
    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        return val.combine(self.operands, self.env, self.prev)

class GuardCont(Continuation):
    def __init__(self, guards, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.guards = guards
        self.env = env
        self.source_pos = source_pos

class SequenceCont(Continuation):
    def __init__(self, exprs, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.exprs = exprs
        self.env = env
        self.source_pos = source_pos
    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        return sequence(self.exprs, self.env, self.prev)

def sequence(exprs, env, cont):
    assert isinstance(exprs, Pair)
    if is_nil(exprs.cdr):
        return exprs.car, env, cont
    else:
        return exprs.car, env, SequenceCont(exprs.cdr, env, cont)

class IfCont(Continuation):
    def __init__(self, consequent, alternative, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.consequent = consequent
        self.alternative = alternative
        self.env = env
        self.source_pos = source_pos
    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        if is_true(val):
            return self.consequent, self.env, self.prev
        elif is_false(val):
            return self.alternative, self.env, self.prev
        else:
            assert False

class CondCont(Continuation):
    def __init__(self, clauses, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.clauses = clauses
        self.env = env
        self.prev = prev
        self.source_pos = source_pos
    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        if is_true(val):
            return sequence(cdar(self.clauses), self.env, self.prev)
        else:
            return cond(cdr(self.clauses), self.env, self.prev)

def cond(vals, env, cont):
    if is_nil(vals):
        return cont.plug_reduce(inert)
    return caar(vals), env, CondCont(vals, env, cont)

class DefineCont(Continuation):
    def __init__(self, definiend, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.definiend = definiend
        self.env = env
        self.source_pos = source_pos
    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        match_parameter_tree(self.definiend, val, self.env)
        return self.prev.plug_reduce(inert)

def match_parameter_tree(param_tree, operand_tree, env):
    if isinstance(param_tree, Symbol):
        env.set(param_tree, operand_tree)
    elif is_ignore(param_tree):
        pass
    elif is_nil(param_tree):
        assert is_nil(operand_tree)
    elif isinstance(param_tree, Pair):
        assert isinstance(operand_tree, Pair)
        match_parameter_tree(param_tree.car, operand_tree.car, env)
        match_parameter_tree(param_tree.cdr, operand_tree.cdr, env)

class InnerGuardCont(GuardCont):
    pass

class OuterGuardCont(GuardCont):
    pass

class InterceptCont(Continuation):
    def __init__(self, interceptor, next_cont, outer_cont, source_pos=None):
        # The outer continuation is the parent of this one for the purposes of
        # abnormal passes, but normal return from this continuation goes to the
        # next interceptor (or to the destination, if this is the last one)
        # instead.
        Continuation.__init__(self, outer_cont)
        self.next_cont = next_cont
        assert isinstance(interceptor, Applicative)
        self.interceptor = interceptor.wrapped_combiner
        self.source_pos = source_pos

    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        outer_cont = self.prev
        return self.interceptor.combine(
                Pair(val, Pair(Applicative(ContWrapper(outer_cont)), nil)),
                outer_cont.env,
                self.next_cont)

class ExtendCont(Continuation):
    def __init__(self, receiver, env, cont_to_extend, source_pos=None):
        Continuation.__init__(self, cont_to_extend)
        assert isinstance(receiver, Applicative)
        self.receiver = receiver.wrapped_combiner
        self.env = env
        self.source_pos = source_pos
    def plug_reduce(self, val):
        trace(":: plugging", val.tostring())
        return self.receiver.combine(val, self.env, self.prev)

class DebugWrapCont(Continuation):
    def __init__(self, header, prev):
        Continuation.__init__(self, prev)
        self.header = header
    def plug_reduce(self, val):
        print "<<", self.header, "returns", val.tostring()
        return Continuation.plug_reduce(self, val)

def car(val):
    assert isinstance(val, Pair)
    return val.car
def cdr(val):
    assert isinstance(val, Pair)
    return val.cdr

# caar, cadr, ..., caadr, ..., cdddddr.
for length in range(2, 6):
    for absoup in product('ad', repeat=length):
        exec("def c%sr(val): return %sval%s"
             % (''.join(absoup),
                ''.join('c%sr(' % each for each in absoup),
                ''.join(')' for each in absoup)))

def iter_list(vals):
    while isinstance(vals, Pair):
        yield vals.car
        vals = vals.cdr
    assert is_nil(vals)

def pythonify_list(vals):
    ret = []
    for item in iter_list(vals):
        ret.append(item)
    return ret
