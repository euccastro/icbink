from itertools import product

from rpython.rlib import rstring

import kernel_type as kt


exports = {}

def export(name, simple=True):
    operative = name.startswith("$")
    if operative:
        simple = False
    def wrapper(fn):
        if simple:
            comb = kt.SimplePrimitive(fn)
        else:
            comb = kt.Primitive(fn)
        if not operative:
            comb = kt.Applicative(comb)
        exports[kt.get_interned(name)] = comb
        return fn
    return wrapper

@export('string-append')
def string_append(vals):
    s = rstring.StringBuilder()
    for v in kt.iter_list(vals):
        assert isinstance(v, kt.String)
        s.append(v.value)
    return kt.String(s.build())

@export('continuation->applicative')
def continuation2applicative(vals):
    cont, = kt.pythonify_list(vals)
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
    return cont.plug_reduce(inner_cont)

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
    return cont.plug_reduce(
            kt.ExtendCont(receiver, recv_env, cont_to_extend))

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

class TraceStatus(object):
    def __init__(self):
        self.trace = False

_trace = TraceStatus()

def trace(*args):
    if _trace.trace:
        print " ".join(args)

@export('trace-on')
def trace_on(val):
    _trace.trace = True
    return kt.inert

@export('trace-off')
def trace_off(val):
    _trace.trace = False
    return kt.inert

def check_guards(guards):
    for guard in kt.iter_list(guards):
        selector, interceptor = kt.pythonify_list(guard)
        #XXX: kernelized error handling
        assert isinstance(selector, kt.Continuation)
        assert isinstance(interceptor, kt.Applicative)
        assert isinstance(interceptor.wrapped_combiner, kt.Operative)

def make_pred(cls):
    def pred(vals):
        for val in kt.iter_list(vals):
            if not isinstance(val, cls):
                return kt.false
        return kt.true
    return kt.Applicative(kt.SimplePrimitive(pred))

for name in ['boolean',
             'symbol',
             'inert',
             'pair',
             'null',
             'environment',
             'ignore',
             'operative',
             'applicative',
             'combiner',
             'string']:
    cls = getattr(kt, name.capitalize())
    exports[kt.get_interned(name+"?")] = make_pred(cls)

