from itertools import product

from rpython.rlib import jit, rarithmetic, rstring
from rpython.rlib.rbigint import rbigint

import debug


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
        assert self.simple, "expected simple value"
        return cont.plug_reduce(self.interpret_simple(env))
    def interpret_simple(self, env):
        return self
    def combine(self, operands, env, cont):
        signal_type_error(Combiner, self)

#XXX: Unicode
class String(KernelValue):
    type_name = 'string'
    _immutable_fields_ = ['strval']
    def __init__(self, value, source_pos=None):
        assert isinstance(value, str), "wrong value for String: %s" % value
        self.strval = value
        self.source_pos = source_pos
    def tostring(self):
        return '"%s"' % self.strval
    def todisplay(self):
        return self.strval
    def equal(self, other):
        return isinstance(other, String) and other.strval == self.strval

class Number(KernelValue):
    type_name = 'number'
    def lteq(self, other):
        return self.lt(other) or self.equal(other)
    def gt(self, other):
        return other.lt(self)
    def gteq(self, other):
        return self.gt(other) or self.equal(other)
    def sub(self, other):
        return self.add(other.neg())

class Infinity(Number):
    pass

class ExactPositiveInfinity(Infinity):
    def tostring(self):
        return "#e+infinity"
    def equal(self, other):
        return isinstance(other, ExactPositiveInfinity)
    def lt(self, other):
        return False
    def add(self, other):
        if isinstance(other, ExactNegativeInfinity):
            signal_add_positive_to_negative_infinity_error(self, other)
        else:
            return self
    def neg(self):
        return e_neg_inf

e_pos_inf = ExactPositiveInfinity()

class ExactNegativeInfinity(Infinity):
    def tostring(self):
        return "#e-infinity"
    def equal(self, other):
        return isinstance(other, ExactNegativeInfinity)
    def lt(self, other):
        return not isinstance(other, ExactNegativeInfinity)
    def add(self, other):
        if isinstance(other, ExactPositiveInfinity):
            signal_add_positive_to_negative_infinity_error(other, self)
        else:
            return self
    def neg(self):
        return e_pos_inf

e_neg_inf = ExactNegativeInfinity()

class Fixnum(Number):
    _immutable_fields_ = ['fixval']
    def __init__(self, fixval, source_pos=None):
        assert isinstance(fixval, int)
        self.fixval = fixval
        self.source_pos = source_pos
    def tostring(self):
        return str(self.fixval)
    def equal(self, other):
        return isinstance(other, Fixnum) and other.fixval == self.fixval
    def lt(self, other):
        if isinstance(other, Fixnum):
            return self.fixval < other.fixval
        elif isinstance(other, ExactNegativeInfinity):
            return False
        else:
            return True
    def add(self, other):
        if isinstance(other, Fixnum):
            try:
                res = rarithmetic.ovfcheck(other.fixval + self.fixval)
                return Fixnum(res)
            except OverflowError:
                return Bignum(rbigint.fromint(self.fixval).add(rbigint.fromint(other.fixval)))
        else:
            assert isinstance(other, Number)
            return other.add(self)
    def neg(self):
        try:
            return Fixnum(-self.fixval)
        except OverflowError:
            return Bignum(rbigint.fromint(self.fixval).neg())

class Bignum(Number):
    _immutable_fields_ = ['bigval']
    def __init__(self, bigval, source_pos=None):
        assert isinstance(bigval, rbigint)
        self.bigval = bigval
        self.source_pos = source_pos
    def tostring(self):
        return str(self.bigval)
    def equal(self, other):
        return isinstance(other, Bignum) and other.bigval.eq(self.bigval)
    def add(self, other):
        if isinstance(other, Bignum):
            otherval = other.bigval
        elif isinstance(other, Fixnum):
            otherval = rbigint.fromint(other.fixval)
        else:
            assert isinstance(other, Number)
            return other.add(self)
        return try_and_make_fixnum(self.bigval.add(otherval))
    def neg(self):
        return try_and_make_fixnum(self.bigval.neg())

def try_and_make_fixnum(bi):
    try:
        num = bi.toint()
        return Fixnum(num)
    except OverflowError:
        return Bignum(bi)

#XXX: Unicode
class Symbol(KernelValue):

    type_name = 'symbol'
    _immutable_fields_ = ['symval']

    def __init__(self, value, source_pos=None):
        assert isinstance(value, str), "wrong value for Symbol: %s" % value
        self.symval = value
        self.source_pos = source_pos

    def tostring(self):
        return self.symval

    def interpret_simple(self, env):
        return env.lookup(self)

    def equal(self, other):
        return isinstance(other, Symbol) and other.symval == self.symval

_symbol_table = {}

def get_interned(name):
    try:
        return _symbol_table[name]
    except KeyError:
        ret = _symbol_table[name] = Symbol(name)
        return ret

class List(KernelValue):
    pass

class Null(List):
    type_name = 'null'
    def tostring(self):
        return "()"
    def equal(self, other):
        return isinstance(other, Null)

nil = Null()

def is_nil(kv):
    return isinstance(kv, Null)

class Ignore(KernelValue):
    type_name = 'ignore'
    def tostring(self):
        return '#ignore'
    def equal(self, other):
        return isinstance(other, Ignore)

ignore = Ignore()

def is_ignore(kv):
    return ignore.equal(kv)

class Inert(KernelValue):
    type_name = 'inert'
    def tostring(self):
        return '#inert'
    def equal(self, other):
        return isinstance(other, Inert)

inert = Inert()

def is_inert(kv):
    return inert.equal(kv)

class Boolean(KernelValue):
    type_name = 'boolean'
    _immutable_fields_ = ['value']
    def __init__(self, value, source_pos=None):
        assert isinstance(value, bool), "wrong value for Boolean: %s" % value
        self.bval = value
        self.source_pos = source_pos
    def tostring(self):
        return '#t' if self.bval else '#f'
    def equal(self, other):
        return isinstance(other, Boolean) and other.bval == self.bval

true = Boolean(True)
false = Boolean(False)

def is_true(kv):
    return true.equal(kv)

def is_false(kv):
    return false.equal(kv)

class Pair(List):
    type_name = 'pair'
    _immutable_fields_ = ['car', 'cdr']
    simple = False
    def __init__(self, car, cdr, source_pos=None):
        assert isinstance(car, KernelValue), "non-KernelValue car: %s" % car
        assert isinstance(cdr, KernelValue), "non-KernelValue cdr: %s" % cdr
        self.car = car
        self.cdr = cdr
        self.source_pos = source_pos
    def tostring(self):
        s = rstring.StringBuilder()
        s.append("(")
        pair = self
        while True:
            assert isinstance(pair, Pair), "not a pair: %s" % pair
            s.append(pair.car.tostring())
            if isinstance(pair.cdr, Pair):
                pair = pair.cdr
                s.append(" ")
            else:
                if not is_nil(pair.cdr):
                    s.append(" . ")
                    s.append(pair.cdr.tostring())
                break
        s.append(")")
        return s.build()
    def interpret(self, env, cont):
        if cont.source_pos is None:
            cont.source_pos = self.source_pos
        return self.car, env, CombineCont(self.cdr,
                                          env,
                                          cont,
                                          source_pos=self.car.source_pos)
    def equal(self, other):
        return (isinstance(other, Pair)
                and self.car.equal(other.car)
                and self.cdr.equal(other.cdr))

class Combiner(KernelValue):
    type_name = 'combiner'
    def combine(self, operands, env, cont):
        raise NotImplementedError

class Operative(Combiner):
    type_name = 'operative'
    name = None

class CompoundOperative(Operative):
    def __init__(self, formals, eformal, exprs, static_env, source_pos=None, name=None):
        self.formals = formals
        self.eformal = eformal
        self.exprs = exprs
        self.static_env = static_env
        self.source_pos = source_pos
        self.name = name
    def combine(self, operands, env, cont):
        eval_env = Environment([self.static_env])
        match_parameter_tree(self.formals, operands, eval_env)
        match_parameter_tree(self.eformal, env, eval_env)
        return sequence(self.exprs, eval_env, cont)
    def tostring(self):
        if self.name is None:
            return str(self)
        else:
            return "<operative '%s'>" % self.name

class Primitive(Operative):
    def __init__(self, code, name):
        self.code = code
        self.source_pos = None
        self.name = name
    def combine(self, operands, env, cont):
        return self.code(operands, env, cont)
    def tostring(self):
        return "<primitive '%s'>" % self.name

class SimplePrimitive(Operative):
    def __init__(self, code, name):
        self.code = code
        self.source_pos = None
        self.name = name
    def combine(self, operands, env, cont):
        return cont.plug_reduce(self.code(operands))
    def tostring(self):
        return "<primitive '%s'>" % self.name

class ContWrapper(Operative):
    def __init__(self, cont, source_pos=None):
        self.cont = cont
        self.source_pos = source_pos
        self.name = None
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
    debug.on_abnormal_pass(operands, src_cont, dst_cont, exiting, entering)
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
    type_name = 'applicative'
    def __init__(self, combiner, source_pos=None):
        assert isinstance(combiner, Combiner), "wrong type to wrap: %s" % combiner
        self.wrapped_combiner = combiner
        self.source_pos = source_pos
    def combine(self, operands, env, cont):
        return evaluate_arguments(operands,
                                  env,
                                  ApplyCont(self.wrapped_combiner, env, cont))
    def tostring(self):
        return "<applicative %s>" % self.wrapped_combiner.tostring()


class Environment(KernelValue):
    type_name = 'environment'
    def __init__(self, parents, bindings=None, source_pos=None):
        self.parents = parents
        self.bindings = bindings or {}
        self.source_pos = source_pos
    def set(self, symbol, value):
        assert isinstance(symbol, Symbol), "setting non-symbol: %s" % symbol
        self.bindings[symbol.symval] = value
    def lookup(self, symbol):
        assert isinstance(symbol, Symbol), "looking up non-symbol: %s" % symbol
        try:
            ret = self.bindings[symbol.symval]
            return ret
        except KeyError:
            for parent in self.parents:
                try:
                    ret = parent.lookup(symbol)
                    return ret
                except KernelException as e:
                    if e.val.dest_cont is not symbol_not_found_cont:
                        raise
            signal_symbol_not_found(symbol)

class EncapsulationType(KernelValue):
    def create_methods(self, source_pos=None):
        constructor = Applicative(EncapsulationConstructor(self, source_pos))
        predicate = Applicative(EncapsulationPredicate(self, source_pos))
        accessor = Applicative(EncapsulationAccessor(self, source_pos))
        return Pair(constructor, Pair(predicate, Pair(accessor, nil)))

class EncapsulatedObject(KernelValue):
    # Abusing terminology; this is actually a union of types.
    type_name = 'encapsulated-object'
    def __init__(self, val, encapsulation_type, source_pos=None):
        self.val = val
        self.encapsulation_type = encapsulation_type
        self.source_pos = source_pos

class EncapsulationMethod(Operative):
    def __init__(self, encapsulation_type, source_pos=None):
        self.encapsulation_type = encapsulation_type
        self.source_pos = source_pos
        self.name = None

class EncapsulationConstructor(EncapsulationMethod):
    def combine(self, operands, env, cont):
        to_wrap, = pythonify_list(operands, 1)
        return cont.plug_reduce(EncapsulatedObject(to_wrap,
                                                   self.encapsulation_type))

class EncapsulationPredicate(EncapsulationMethod):
    def combine(self, operands, env, cont):
        for val in iter_list(operands):
            if not isinstance(val, EncapsulatedObject):
                return cont.plug_reduce(false)
            if val.encapsulation_type is not self.encapsulation_type:
                return cont.plug_reduce(false)
        return cont.plug_reduce(true)

class EncapsulationAccessor(EncapsulationMethod):
    def combine(self, operands, env, cont):
        wrapped, = pythonify_list(operands, 1)
        check_type(wrapped, EncapsulatedObject)
        assert isinstance(wrapped, EncapsulatedObject)
        if wrapped.encapsulation_type is self.encapsulation_type:
            return cont.plug_reduce(wrapped.val)
        else:
            signal_encapsulation_type_error(self, wrapped)

# Copying a trick from the reference implementation in the R-1RK.
#
# This is a member of promises so it can be overwritten altogether when
# a promise results in another that must be resolved immediately.
#
# If env is None then val is the result of this promise, otherwise val is the
# expression that we need to evaluate in env.
class PromiseData(object):
    def __init__(self, val, env):
        self.val = val
        self.env = env

class Promise(KernelValue):
    type_name = 'promise'
    def __init__(self, val, env, source_pos=None):
        self.data = PromiseData(val, env)
        self.source_pos = source_pos
    def force(self, cont):
        if self.data.env is None:
            return cont.plug_reduce(self.data.val)
        else:
            return (self.data.val,
                    self.data.env,
                    HandlePromiseResultCont(self, cont))

class KeyedDynamicBinder(Operative):
    def combine(self, operands, env, cont):
        value, thunk = pythonify_list(operands, 2)
        return thunk.combine(nil,
                             Environment([]),
                             KeyedDynamicCont(self, value, cont))

class KeyedDynamicAccessor(Operative):
    def __init__(self, binder, source_pos=None):
        self.binder = binder
        self.source_pos = source_pos
    def combine(self, operands, env, cont):
        pythonify_list(operands, 0)
        prev = cont
        while prev is not None:
            if (isinstance(prev, KeyedDynamicCont)
                and prev.binder is self.binder):
                return cont.plug_reduce(prev.value)
            prev = prev.prev
        signal_unbound_dynamic_key(self)

class KeyedStaticBinder(Operative):
    def combine(self, operands, env, cont):
        value, env = pythonify_list(operands, 2)
        check_type(env, Environment)
        assert isinstance(env, Environment)
        return cont.plug_reduce(KeyedEnvironment(self, value, env))

class KeyedEnvironment(Environment):
    def __init__(self, binder, value, parent, source_pos=None):
        Environment.__init__(self, [parent], {}, source_pos)
        self.binder = binder
        self.value = value

class KeyedStaticAccessor(Operative):
    def __init__(self, binder, source_pos=None):
        self.binder = binder
        self.source_pos = source_pos
    def combine(self, operands, env, cont):
        pythonify_list(operands, 0)
        ret = self.find_binding(env)
        if ret is None:
            signal_unbound_static_key(self)
        else:
            return cont.plug_reduce(ret)
    def find_binding(self, env):
        if (isinstance(env, KeyedEnvironment)
            and env.binder is self.binder):
            return env.value
        for parent in env.parents:
            ret = self.find_binding(parent)
            if ret is not None:
                return ret
        return None

class Continuation(KernelValue):
    type_name = 'continuation'
    _immutable_args_ = ['prev']
    def __init__(self, prev, source_pos=None):
        self.prev = prev
        self.marked = False
        self.source_pos = source_pos
    def plug_reduce(self, val):
        debug.on_plug_reduce(val, self)
        return self._plug_reduce(val)
    def _plug_reduce(self, val):
        return self.prev.plug_reduce(val)
    def mark(self, boolean):
        self.marked = boolean
        if self.prev is not None:
            self.prev.mark(boolean)

class RootCont(Continuation):
    def __init__(self):
        Continuation.__init__(self, None)
        self.source_pos = None
    def _plug_reduce(self, val):
        raise KernelExit

class BaseErrorCont(Continuation):
    def _plug_reduce(self, val):
        if not isinstance(val, ErrorObject):
            print "*** ERROR ***:",
        print val.todisplay()
        return Continuation._plug_reduce(self, val)

def evaluate_arguments(vals, env, cont):
    if isinstance(vals, Pair):
        if is_nil(vals.cdr):
            return vals.car, env, NoMoreArgsCont(cont, vals.car.source_pos)
        else:
            return vals.car, env, EvalArgsCont(vals.cdr, env, cont, vals.car.source_pos)
    else:
        return vals, env, cont

# XXX: refactor to extract common pattern with evaluate_arguments.
#      this one happens to work on a Python list because we just
#      happen to build one for transposing the list arguments to
#      map.
def map_(combiner, transposed_lists, index, env, cont):
    if not transposed_lists:
        return cont.plug_reduce(nil)
    if index == len(transposed_lists) - 1:
        return combiner.combine(transposed_lists[index],
                                env, NoMoreArgsCont(cont))
    else:
        return combiner.combine(transposed_lists[index],
                                env,
                                MapCont(combiner,
                                        transposed_lists,
                                        index+1,
                                        env,
                                        cont))

class MapCont(Continuation):
    def __init__(self, combiner, lists, index, env, prev, source_pos=None):
        Continuation.__init__(self, prev, source_pos)
        self.combiner = combiner
        self.lists = lists
        self.index = index
        self.env = env
    def _plug_reduce(self, val):
        return map_(self.combiner,
                    self.lists,
                    self.index,
                    self.env,
                    GatherArgsCont(val, self.prev))

class EvalArgsCont(Continuation):
    def __init__(self, exprs, env, prev, source_pos=None):
        Continuation.__init__(self, prev, source_pos)
        self.exprs = exprs
        self.env = env
    def _plug_reduce(self, val):
        return evaluate_arguments(self.exprs,
                                  self.env,
                                  GatherArgsCont(val, self.prev))

class NoMoreArgsCont(Continuation):
    def _plug_reduce(self, val):
        return self.prev.plug_reduce(Pair(val, nil))

class GatherArgsCont(Continuation):
    def __init__(self, val, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.val = val
        self.source_pos = source_pos
    def _plug_reduce(self, val):
        return self.prev.plug_reduce(Pair(self.val, val))

class ApplyCont(Continuation):
    def __init__(self, combiner, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.combiner = combiner
        self.env = env
        self.source_pos = source_pos
    def _plug_reduce(self, args):
        return self.combiner.combine(args, self.env, self.prev)

class CombineCont(Continuation):
    def __init__(self, operands, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.operands = operands
        self.env = env
        self.source_pos = source_pos
    def _plug_reduce(self, val):
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
    def _plug_reduce(self, val):
        return sequence(self.exprs, self.env, self.prev)

def sequence(exprs, env, cont):
    if is_nil(exprs):
        return cont.plug_reduce(inert)
    assert isinstance(exprs, Pair), "non-pair sequence: %s" % exprs
    if is_nil(exprs.cdr):
        # The whole function can be made shorter and simpler if we don't treat
        # this as a special case, but then we'd be creating an extra
        # continuation for the last element of a list.  Avoiding that should be
        # a significant savings since every list has a last element.
        #
        # This optimization was taken from Queinnec's LiSP (see README).
        # I haven't actually measured, yet, how worthy is it when compiling
        # with JIT enabled.
        return exprs.car, env, cont
    else:
        return exprs.car, env, SequenceCont(exprs.cdr, env, cont)

class IfCont(Continuation):
    def __init__(self, consequent, alternative, env, prev):
        Continuation.__init__(self, prev)
        self.consequent = consequent
        self.alternative = alternative
        self.env = env
    def _plug_reduce(self, val):
        if is_true(val):
            return self.consequent, self.env, self.prev
        elif is_false(val):
            return self.alternative, self.env, self.prev
        else:
            assert False, "not #t nor #f: %s" % val

class CondCont(Continuation):
    def __init__(self, clauses, env, prev, source_pos=None):
        Continuation.__init__(self, prev)
        self.clauses = clauses
        self.env = env
        self.prev = prev
        self.source_pos = source_pos
    def _plug_reduce(self, val):
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
    def _plug_reduce(self, val):
        match_parameter_tree(self.definiend, val, self.env)
        return self.prev.plug_reduce(inert)

def match_parameter_tree(param_tree, operand_tree, env):
    if isinstance(param_tree, Symbol):
        op = operand_tree
        while isinstance(op, Applicative):
            op = op.wrapped_combiner
        if isinstance(op, Operative) and op.name is None:
            op.name = param_tree.symval
        env.set(param_tree, operand_tree)
    elif is_ignore(param_tree):
        pass
    elif is_nil(param_tree):
        if not is_nil(operand_tree):
            # XXX: this only shows the tail of the mismatch
            signal_operand_mismatch(param_tree, operand_tree)
    elif isinstance(param_tree, Pair):
        if not isinstance(operand_tree, Pair):
            # XXX: this only shows the tail of the mismatch
            signal_operand_mismatch(param_tree, operand_tree)
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
        assert isinstance(interceptor, Applicative), "non-applicative interceptor: %s" % interceptor
        self.interceptor = interceptor.wrapped_combiner
        self.source_pos = source_pos

    def _plug_reduce(self, val):
        outer_cont = self.prev
        return self.interceptor.combine(
                Pair(val, Pair(Applicative(ContWrapper(outer_cont)), nil)),
                outer_cont.env,
                self.next_cont)

class ExtendCont(Continuation):
    def __init__(self, receiver, env, cont_to_extend, source_pos=None):
        Continuation.__init__(self, cont_to_extend)
        assert isinstance(receiver, Applicative), "non-applicative receiver: %s" % receiver
        self.receiver = receiver.wrapped_combiner
        self.env = env
        self.source_pos = source_pos
    def _plug_reduce(self, val):
        return self.receiver.combine(val, self.env, self.prev)

class HandlePromiseResultCont(Continuation):
    def __init__(self, promise, prev, source_pos=None):
        Continuation.__init__(self, prev, source_pos)
        self.promise = promise
    def plug_reduce(self, val):
        if self.promise.data.env is None:
            return self.prev.plug_reduce(self.promise.data.val)
        if isinstance(val, Promise):
            self.promise.data = val.data
            return self.promise.force(self.prev)
        else:
            self.promise.data.val = val
            self.promise.data.env = None
            return self.prev.plug_reduce(val)

class KeyedDynamicCont(Continuation):
    def __init__(self, binder, value, prev, source_pos=None):
        Continuation.__init__(self, prev, source_pos)
        self.binder = binder
        self.value = value

class DebugErrorCont(Continuation):
    def plug_reduce(self, val):
        return debug.on_error(val)

class ConstantCont(Continuation):
    """Ignore the value passed to me; just pass on the one provided in the
    constructor."""
    def __init__(self, val, prev):
        Continuation.__init__(self, prev)
        self.val = val
    def _plug_reduce(self, val):
        return self.prev.plug_reduce(self.val)

def car(val):
    assert isinstance(val, Pair), "car on non-pair: %s" % val
    return val.car
def cdr(val):
    assert isinstance(val, Pair), "cdr on non-pair: %s" % val
    return val.cdr

# caar, cadr, ..., caadr, ..., cdddddr.
for length in range(2, 6):
    for adsoup in product('ad', repeat=length):
        exec("def c%sr(val): return %sval%s"
             % (''.join(adsoup),
                ''.join('c%sr(' % each for each in adsoup),
                ''.join(')' for each in adsoup)))

# XXX: these don't feel like they belong in a kernel type module, but placing
# them in primitive.py would create a cyclic dependency.
root_cont = RootCont()
debug_error_cont = DebugErrorCont(root_cont)
error_cont = BaseErrorCont(debug_error_cont)
system_error_cont = Continuation(error_cont)
user_error_cont = Continuation(error_cont)
file_not_found_cont = Continuation(user_error_cont)
parse_error_cont = Continuation(user_error_cont)
type_error_cont = Continuation(user_error_cont)
value_error_cont = Continuation(user_error_cont)
encapsulation_type_error_cont = Continuation(type_error_cont)
operand_mismatch_cont = Continuation(type_error_cont)
arity_mismatch_cont = Continuation(operand_mismatch_cont)
symbol_not_found_cont = Continuation(user_error_cont)
unbound_dynamic_key_cont = Continuation(user_error_cont)
unbound_static_key_cont = Continuation(user_error_cont)
add_positive_to_negative_infinity_cont = Continuation(user_error_cont)

class ErrorObject(KernelValue):
    type_name = 'error-object'
    def __init__(self, dest_cont, message, irritants):
        self.dest_cont = dest_cont
        assert isinstance(message, str)
        if not is_nil(irritants):
            check_type(irritants, Pair)
        self.message = String(message)
        self.irritants = irritants
        # Filled in by the evaluator.
        self.val = None
        self.env = None
        self.src_cont = None
    def todisplay(self):
        return "*** ERROR ***: %s" % self.message.todisplay()

def raise_(*args):
    raise KernelException(ErrorObject(*args))

def signal_file_not_found(filename):
    raise_(file_not_found_cont,
           ("file '%s' not found" % filename),
           Pair(String(filename), nil))

def signal_parse_error(error_string, source_filename):
    raise_(parse_error_cont,
           error_string,
           Pair(String(source_filename), nil))

def signal_symbol_not_found(symbol):
    raise_(symbol_not_found_cont,
           "Symbol '%s' not found" % symbol.todisplay(),
           Pair(symbol, nil))

def signal_unbound_dynamic_key(accessor):
    raise_(unbound_dynamic_key_cont,
           "Binder '%s' not in dynamic extent" % accessor.binder.todisplay(),
            Pair(accessor, nil))

def signal_unbound_static_key(accessor):
    raise_(unbound_static_key_cont,
           "Binder '%s' not in scope" % accessor.binder.todisplay(),
            Pair(accessor, nil))

def signal_type_error(expected_type, actual_value):
    raise_(type_error_cont,
           "Expected object of type %s, but got %s instead"
               % (expected_type.type_name,
                  actual_value.tostring()),
           Pair(String(expected_type.type_name),
                              Pair(actual_value, nil)))

def signal_value_error(msg, irritants):
    raise_(value_error_cont, msg, irritants)

def signal_encapsulation_type_error(expected_type, actual_value):
    raise_(encapsulation_type_error_cont,
           "Expected encapsulated object of type %s, but got %s instead"
               % (expected_type.tostring(),
                  actual_value.tostring()),
           Pair(expected_type, Pair(actual_value, nil)))

def check_type(val, type_):
    if not isinstance(val, type_):
        signal_type_error(type_, val)

def signal_operand_mismatch(expected_params, actual_operands):
    raise_(operand_mismatch_cont,
           "%s doesn't match expected param tree %s"
               % (actual_operands.tostring(),
                  expected_params.tostring()),
           Pair(expected_params, Pair(actual_operands, nil)))

def signal_arity_mismatch(expected_arity, actual_arguments):
    raise_(arity_mismatch_cont,
           "expected %s arguments but got %s"
               % (expected_arity,
                  actual_arguments.tostring()),
           Pair(String(expected_arity), Pair(actual_arguments, nil)))

def signal_add_positive_to_negative_infinity_error(pos, neg):
    raise_(add_positive_to_negative_infinity_cont,
           "Tried to add positive to negative infinity",
           Pair(pos, Pair(neg, nil)))

# Not actual kernel type.
class KernelExit(Exception):
    pass

# We need to wrap ErrorObjects in these because we want them to be KernelValues
# and rpython doesn't allow raising non-Exceptions nor multiple inheritance.
class KernelException(Exception):
    def __init__(self, val):
        assert isinstance(val, ErrorObject)
        self.val = val
    def __str__(self):
        return self.val.todisplay()

class NonNullListTail(Exception):
    def __init__(self, val):
        self.val = val

def iter_list(vals):
    while isinstance(vals, Pair):
        yield vals.car
        vals = vals.cdr
    if not is_nil(vals):
        raise NonNullListTail(vals)

def pythonify_list(vals, check_arity=-1):
    ret = []
    for item in iter_list(vals):
        ret.append(item)
    if check_arity != -1 and len(ret) != check_arity:
        signal_arity_mismatch(str(check_arity), vals)
    return ret

def kernelify_list(ls):
    ret = nil
    for x in reversed(ls):
        ret = Pair(x, ret)
    return ret
