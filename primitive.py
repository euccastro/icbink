from itertools import product

from rpython.rlib import jit, rstring

import debug
import kernel_type as kt
import parse


_exports = {}

def export(name, simple=True):
    operative = name.startswith("$")
    if operative:
        simple = False
    def wrapper(fn):
        if simple:
            comb = kt.SimplePrimitive(fn, name)
        else:
            comb = kt.Primitive(fn, name)
        if not operative:
            comb = kt.Applicative(comb)
        _exports[name] = comb
        return fn
    return wrapper

@export('string-append')
def string_append(vals):
    s = rstring.StringBuilder()
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.String)
        s.append(v.sval)
    return kt.String(s.build())

@export('continuation->applicative')
def continuation2applicative(vals):
    cont, = kt.pythonify_list(vals, 1)
    assert isinstance(cont, kt.Continuation)
    return kt.Applicative(kt.ContWrapper(cont))

@export('guard-continuation', simple=False)
def guard_continuation(vals, env, cont):
    entry_guards, cont_to_guard, exit_guards = kt.pythonify_list(vals)
    check_guards(entry_guards)
    check_guards(exit_guards)
    assert isinstance(cont_to_guard, kt.Continuation)
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
    assert isinstance(cont_to_extend, kt.Continuation)
    assert isinstance(receiver, kt.Applicative)
    assert isinstance(recv_env, kt.Environment)
    return kt.ExtendCont(receiver, recv_env, cont_to_extend), env, cont

@export('$sequence')
def sequence(exprs, env, cont):
    return kt.sequence(exprs, env, cont)

@export('$vau')
def vau(operands, env, cont):
    assert isinstance(operands, kt.Pair)
    formals = operands.car
    cdr = operands.cdr
    assert isinstance(cdr, kt.Pair)
    eformals = cdr.car
    exprs = cdr.cdr
    return cont.plug_reduce(kt.CompoundOperative(formals, eformals, exprs, env))

@export('$if')
def if_(operands, env, cont):
    test, consequent, alternative = kt.pythonify_list(operands)
    return test, env, kt.IfCont(consequent, alternative, env, cont)

@export('equal?')
def equalp(vals):
    o1, o2 = kt.pythonify_list(vals)
    return kt.true if o1.equal(o2) else kt.false

@export('cons')
def cons(vals):
    car, cdr = kt.pythonify_list(vals)
    return kt.Pair(car, cdr)

@export('eval', simple=False)
def eval_(vals, env_ignore, cont):
    expr, env = kt.pythonify_list(vals)
    return expr, env, cont

@export('make-environment')
def make_environment(vals):
    return kt.Environment(kt.pythonify_list(vals))

@export('$define!')
def define(vals, env, cont):
    definiend, expression = kt.pythonify_list(vals)
    return expression, env, kt.DefineCont(definiend, env, cont)

@export('wrap')
def wrap(vals):
    combiner, = kt.pythonify_list(vals)
    return kt.Applicative(combiner)

@export('unwrap')
def unwrap(vals):
    applicative, = kt.pythonify_list(vals)
    assert isinstance(applicative, kt.Applicative)
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
    for absoup in product('ad', repeat=length):
        name = 'c%sr' % ''.join(absoup)
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
    assert isinstance(applicative, kt.Applicative)
    return kt.Pair(applicative.wrapped_combiner, args), env, cont

@export('$cond')
def cond(vals, env, cont):
    return kt.cond(vals, env, cont)

@export('call/cc', simple=False)
def call_with_cc(vals, env, cont):
    applicative, = kt.pythonify_list(vals)
    assert isinstance(applicative, kt.Applicative)
    return kt.Pair(applicative, kt.Pair(cont, kt.nil)), env, cont

@export('symbol->string')
def symbol2string(vals):
    symbol, = kt.pythonify_list(vals)
    assert isinstance(symbol, kt.Symbol)
    return kt.String(symbol.sval)

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

def kernel_eval(val, env, cont):
    if cont is None:
        cont = AdHocCont(kt.root_cont)
    try:
        while True:
            driver.jit_merge_point(val=val, env=env, cont=cont)
            debug.on_eval(val, env, cont)
            try:
                val, env, cont = val.interpret(env, cont)
            except kt.KernelException as e:
                val, env, cont = kt.abnormally_pass(e.val, cont, e.val.dest_cont)
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


def load(path, env, cont=None):
    src = open(path).read()
    src_lines = src.split("\n")
    program = kt.Pair(_ground_env.bindings['$sequence'],
                      parse.parse(src, path))
    return kernel_eval(program, env, cont)

def check_guards(guards):
    for guard in kt.iter_list(guards):
        selector, interceptor = kt.pythonify_list(guard)
        #XXX: kernelized error handling
        assert isinstance(selector, kt.Continuation)
        assert isinstance(interceptor, kt.Applicative)
        assert isinstance(interceptor.wrapped_combiner, kt.Operative)

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
            kt.ErrorObject]:
    pred_name = cls.type_name + "?"
    _exports[pred_name] = make_pred(cls, pred_name)
del pred_name, cls

def empty_environment():
    return kt.Environment([], {})

def standard_environment():
    return kt.Environment([_ground_env], {})

def extended_environment():
    return kt.Environment([_extended_env], {})

_exports['root-continuation'] = kt.root_cont
_exports['error-continuanion'] = kt.error_cont
_exports['system-error-continuation'] = kt.system_error_cont
_exports['user-error-continuation'] = kt.user_error_cont
_exports['type-error-continuation'] = kt.type_error_cont
_exports['operand-mismatch-continuation'] = kt.operand_mismatch_cont
_exports['arity-mismatch-continuation'] = kt.arity_mismatch_cont
_exports['symbol-not-found-continuation'] = kt.symbol_not_found_cont

_ground_env = kt.Environment([], _exports)
load("kernel.k", _ground_env)
_extended_env = kt.Environment([_ground_env], {})
load("extension.k", _extended_env)

del _exports
