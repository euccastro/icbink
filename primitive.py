from itertools import product

import os
from rpython.rlib import jit, rpath, rstring, unroll
from rpython.rlib.parsing.parsing import ParseError

import debug
import kernel_type as kt
import parse

search_paths = ['.'] + os.environ.get('KERNELPATH', '').split(':')

_exports = {}

def export(name, argtypes=None, simple=True):
    operative = name.startswith("$")
    if operative:
        simple = False
    def wrapper(fn):
        if argtypes is None:
            wrapped = fn
        else:
            unroll_argtypes = unroll.unrolling_iterable(argtypes)
            def wrapped(otree, *etc):
                args_tuple = ()
                rest = otree
                for type_ in unroll_argtypes:
                    assert isinstance(rest, kt.Pair)
                    arg = rest.car
                    rest = rest.cdr
                    kt.check_type(arg, type_)
                    assert isinstance(arg, type_)
                    args_tuple += (arg,)
                assert kt.is_nil(rest)
                args_tuple += etc
                return fn(*args_tuple)
        if simple:
            comb = kt.SimplePrimitive(wrapped, name)
        else:
            comb = kt.Primitive(wrapped, name)
        if not operative:
            comb = kt.Applicative(comb)
        _exports[name] = comb
        return wrapped
    return wrapper

@export('string-append')
def string_append(vals):
    s = rstring.StringBuilder()
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.String)
        assert isinstance(v, kt.String)
        s.append(v.strval)
    return kt.String(s.build())

@export('continuation->applicative', argtypes=[kt.Continuation])
def continuation2applicative(cont):
    return kt.Applicative(kt.ContWrapper(cont))

@export('guard-continuation',
        [kt.List, kt.Continuation, kt.List],
        simple=False)
def guard_continuation(entry_guards, cont_to_guard, exit_guards, env, cont):
    check_guards(entry_guards)
    check_guards(exit_guards)
    outer_cont = kt.OuterGuardCont(entry_guards, env, cont_to_guard)
    inner_cont = kt.InnerGuardCont(exit_guards, env, outer_cont)
    return inner_cont, env, cont

@export('extend-continuation', simple=False)
def extend_continuation(vals, env, cont):
    args = kt.pythonify_list(vals)
    if len(args) == 2:
        cont_to_extend, receiver = args
        recv_env = kt.Environment([])
    else:
        cont_to_extend, receiver, recv_env = args
    kt.check_type(cont_to_extend, kt.Continuation)
    kt.check_type(receiver, kt.Applicative)
    kt.check_type(recv_env, kt.Environment)
    return kt.ExtendCont(receiver, recv_env, cont_to_extend), env, cont

@export('$sequence')
def sequence(exprs, env, cont):
    return kt.sequence(exprs, env, cont)

@export('$vau')
def vau(operands, env, cont):
    #XXX: check arity flexibly
    assert isinstance(operands, kt.Pair)
    formals = operands.car
    cdr = operands.cdr
    assert isinstance(cdr, kt.Pair)
    eformals = cdr.car
    exprs = cdr.cdr
    return cont.plug_reduce(kt.CompoundOperative(formals, eformals, exprs, env))

@export('$if', [kt.KernelValue, kt.KernelValue, kt.KernelValue])
def if_(test, consequent, alternative, env, cont):
    return test, env, kt.IfCont(consequent, alternative, env, cont)

@export('equal?', [kt.KernelValue, kt.KernelValue])
def equalp(o1, o2):
    return kt.true if o1.equal(o2) else kt.false

@export('cons', [kt.KernelValue, kt.KernelValue])
def cons(car, cdr):
    return kt.Pair(car, cdr)

@export('eval', [kt.KernelValue, kt.Environment], simple=False)
def eval_(expr, env, _, cont):
    return expr, env, cont

@export('make-environment')
def make_environment(vals):
    return kt.Environment(kt.pythonify_list(vals))

@export('$define!', [kt.KernelValue, kt.KernelValue])
def define(definiend, expression, env, cont):
    return expression, env, kt.DefineCont(definiend,
                                          env,
                                          cont,
                                          expression.source_pos)

@export('wrap', [kt.Combiner])
def wrap(combiner):
    return kt.Applicative(combiner)

@export('unwrap', [kt.Applicative])
def unwrap(applicative):
    return applicative.wrapped_combiner

@export('list')
def list_(vals):
    return vals

@export('list*')
def list_star(vals):
    assert isinstance(vals, kt.Pair)
    if isinstance(vals.cdr, kt.Pair):
        return kt.Pair(vals.car, list_star(vals.cdr))
    elif kt.is_nil(vals.cdr):
        return vals.car
    else:
        return vals

@export('$lambda')
def lambda_(vals, env, cont):
    assert isinstance(vals, kt.Pair)
    formals = vals.car
    exprs = vals.cdr
    return cont.plug_reduce(
            kt.Applicative(
                kt.CompoundOperative(formals, kt.ignore, exprs, env)))

# car, cdr, caar, cadr, ..., caadr, ..., cdddddr.
for length in range(1, 6):
    for adsoup in product('ad', repeat=length):
        name = 'c%sr' % ''.join(adsoup)
        exec("""
@export('%s')
def %s(val):
    assert isinstance(val, kt.Pair)
    assert kt.is_nil(val.cdr)
    return kt.%s(val.car)
""" % (name, name, name))

@export('apply', simple=False)
def apply_(vals, env_ignore, cont):
    ls = kt.pythonify_list(vals)
    if len(ls) == 2:
        applicative, args = ls
        env = kt.Environment([])
    else:
        applicative, args, env = ls
    kt.check_type(applicative, kt.Applicative)
    return kt.Pair(applicative.wrapped_combiner, args), env, cont

@export('$cond')
def cond(vals, env, cont):
    return kt.cond(vals, env, cont)

@export('call/cc', [kt.Applicative], simple=False)
def call_with_cc(applicative, env, cont):
    return kt.Pair(applicative, kt.Pair(cont, kt.nil)), env, cont

@export('symbol->string', [kt.Symbol])
def symbol2string(symbol):
    return kt.String(symbol.symval)

@export('make-encapsulation-type', [])
def make_encapsulation_type():
    return kt.EncapsulationType().create_methods()

@export('$lazy', [kt.KernelValue], simple=False)
def lazy(expr, env, cont):
    return cont.plug_reduce(kt.Promise(expr, env))

@export('memoize', [kt.KernelValue])
def memoize(val):
    return kt.Promise(val, None)

@export('force', [kt.KernelValue], simple=False)
def force(val, env, cont):
    if isinstance(val, kt.Promise):
        return val.force(cont)
    else:
        return cont.plug_reduce(val)

@export('make-keyed-dynamic-variable', [])
def make_keyed_dynamic_variable():
    return make_keyed_variable(kt.KeyedDynamicBinder,
                               kt.KeyedDynamicAccessor)

@export('make-keyed-static-variable', [])
def make_keyed_static_variable():
    return make_keyed_variable(kt.KeyedStaticBinder,
                               kt.KeyedStaticAccessor)

def make_keyed_variable(binder_class, accessor_class):
    binder = binder_class()
    accessor = accessor_class(binder)
    return kt.Pair(kt.Applicative(binder),
                   kt.Pair(kt.Applicative(accessor), kt.nil))

@export('+')
def add(vals):
    accum = kt.Fixnum(0)
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        accum = accum.add(v)
    return accum

@export('-')
def sub(vals):
    ls = kt.pythonify_list(vals)
    if len(ls) < 2:
        kt.signal_arity_mismatch('>=2', vals)
    accum = ls[0]
    for v in ls[1:]:
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        accum = accum.sub(v)
    return accum

@export('=?')
def lteq(vals):
    ls = kt.pythonify_list(vals)
    if len(ls) < 2:
        return kt.true
    latest = ls[0]
    for v in ls[1:]:
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        if not latest.equal(v):
            return kt.false
        latest = v
    return kt.true

#XXX: refactor
@export('<=?')
def lteq(vals):
    latest = kt.e_neg_inf
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        if not latest.lteq(v):
            return kt.false
        latest = v
    return kt.true

#XXX: refactor
@export('<?')
def lteq(vals):
    latest = kt.e_neg_inf
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        if not latest.lt(v):
            return kt.false
        latest = v
    return kt.true

# Not standard Kernel functions; for debugging only.

@export('print')
def print_(val):
    if isinstance(val, kt.Pair):
        for v in kt.iter_list(val):
            print v.todisplay(),
    else:
        assert kt.is_nil(val)
    return kt.inert

@export('println')
def println(val):
    print_(val)
    print
    return kt.inert

class TestError(Exception):
    def __init__(self, val):
        assert isinstance(val, kt.KernelValue)
        self.val = val

# XXX: integrate into error handling system?  start debug REPL?
@export('test-error')
def test_error(val):
    print "ERROR: ",
    println(val)
    raise TestError(val)
    return kt.inert

@export('debug-on')
def _debug_on(val):
    assert kt.is_nil(val)
    debug.start_stepping()
    return kt.inert

@export('debug-off')
def _debug_off(val):
    assert kt.is_nil(val)
    debug.stop_stepping()
    return kt.inert

class AdHocException(Exception):
    def __init__(self, val):
        self.val = val

class AdHocCont(kt.Continuation):
    def _plug_reduce(self, val):
        raise AdHocException(val)

def kernel_eval(val, env, cont=None):
    if cont is None:
        cont = AdHocCont(kt.root_cont)
    try:
        while True:
            driver.jit_merge_point(val=val, env=env, cont=cont)
            val_, env_, cont_ = debug.on_eval(val, env, cont)
            if val_ is not None:
                val, env, cont = val_, env_, cont_
            try:
                val, env, cont = val.interpret(env, cont)
            except kt.KernelException as e:
                error = e.val
                error.val = val
                error.env = env
                error.src_cont = cont
                val, env, cont = kt.abnormally_pass(error, cont, e.val.dest_cont)
    except AdHocException as e:
        return e.val

def get_printable_location(green_val):
    if green_val is None:
        return "No green val"
    else:
        return green_val.tostring()

driver = jit.JitDriver(reds=['env', 'cont'],
                       greens=['val'],
                       get_printable_location=get_printable_location)


@export('load', [kt.String], simple=False)
def load_(path, env, cont):
    # XXX: have some programmatically editable search path?
    filename = path.strval
    for dir_path in search_paths:
        whole_path = rpath.join(dir_path, [filename])
        if rpath.exists(whole_path):
            try:
                program = parse_file(whole_path)
            except ParseError as e:
                return kt.signal_parse_error(e.nice_error_message(),
                                             whole_path)
            return program, env, kt.ConstantCont(kt.inert, cont)
    else:
        return kt.signal_file_not_found(filename)

def parse_file(path):
    src = open(path).read()  # XXX: RPython?
    return kt.Pair(_ground_env.bindings['$sequence'],
                   parse.parse(src, path))

def check_guards(guards):
    for guard in kt.iter_list(guards):
        selector, interceptor = kt.pythonify_list(guard)
        kt.check_type(selector, kt.Continuation)
        kt.check_type(interceptor, kt.Applicative)
        kt.check_type(interceptor.wrapped_combiner, kt.Operative)

def make_pred(cls, name):
    def pred(vals):
        for val in kt.iter_list(vals):
            if not isinstance(val, cls):
                return kt.false
        return kt.true
    return kt.Applicative(kt.SimplePrimitive(pred, name))

for cls in [kt.Boolean,
            kt.Symbol,
            kt.Inert,
            kt.Pair,
            kt.Null,
            kt.Environment,
            kt.Ignore,
            kt.Operative,
            kt.Applicative,
            kt.Combiner,
            kt.String,
            kt.Number,
            kt.Promise,
            kt.ErrorObject]:
    pred_name = cls.type_name + "?"
    _exports[pred_name] = make_pred(cls, pred_name)
del pred_name, cls

# Not standard Kernel and not real type predicates.
_exports['fixnum?'] = make_pred(kt.Fixnum, 'fixnum?')
_exports['bignum?'] = make_pred(kt.Bignum, 'bignum?')

def empty_environment():
    return kt.Environment([], {})

def standard_environment():
    return kt.Environment([_ground_env], {})

def extended_environment():
    return kt.Environment([_extended_env], {})

_exports['root-continuation'] = kt.root_cont
_exports['error-continuation'] = kt.error_cont
_exports['system-error-continuation'] = kt.system_error_cont
_exports['user-error-continuation'] = kt.user_error_cont
_exports['file-not-found-continuation'] = kt.file_not_found_cont
_exports['parse-error-continuation'] = kt.parse_error_cont
_exports['unbound-dynamic-key-continuation'] = kt.unbound_dynamic_key_cont
_exports['unbound-static-key-continuation'] = kt.unbound_static_key_cont
_exports['type-error-continuation'] = kt.type_error_cont
_exports['encapsulation-type-error-continuation'] = kt.encapsulation_type_error_cont
_exports['operand-mismatch-continuation'] = kt.operand_mismatch_cont
_exports['arity-mismatch-continuation'] = kt.arity_mismatch_cont
_exports['symbol-not-found-continuation'] = kt.symbol_not_found_cont
_exports['add-positive-to-negative-infinity-continuation'] = kt.add_positive_to_negative_infinity_cont

_ground_env = kt.Environment([], _exports)

here = rpath.dirname(__file__)

kernel_eval(parse_file(rpath.join(here, ["kernel.k"])), _ground_env)
_extended_env = kt.Environment([_ground_env], {})
kernel_eval(parse_file(rpath.join(here, ["extension.k"])), _extended_env)

def standard_value(name):
    return _ground_env.bindings[name]

del _exports
