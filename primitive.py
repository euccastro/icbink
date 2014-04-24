from rpython.rlib import rstring

import kernel_type as kt


exports = {}

def export(name, simple=True, applicative=True):
    def wrapper(fn):
        if simple:
            comb = kt.SimplePrimitive(fn)
        else:
            comb = kt.Primitive(fn)
        if applicative:
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
    return kt.ContWrapper(cont)

@export('guard-continuation', simple=False, applicative=False)
def guard_continuation(vals, env, cont):
    return kt.evaluate_arguments(
            vals,
            env,
            kt.ApplyCont(kt.Primitive(_guard_continuation),
                         env,
                         cont))

@export('$sequence', simple=False, applicative=False)
def sequence(exprs, env, cont):
    return kt.sequence(exprs, env, cont)

@export('$vau', simple=False, applicative=False)
def vau(operands, env, cont):
    assert isinstance(operands, kt.Pair)
    formals = operands.car
    cdr = operands.cdr
    assert isinstance(cdr, kt.Pair)
    eformals = cdr.car
    exprs = cdr.cdr
    return cont.plug_reduce(kt.CompoundOperative(formals, eformals, exprs, env))

@export('$if', simple=False, applicative=False)
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

@export('$define!', simple=False, applicative=False)
def define(vals, env, cont):
    definiend, expression = kt.pythonify_list(vals)
    return expression, env, kt.DefineCont(definiend, env, cont)

@export('wrap')
def wrap(vals):
    combiner, = kt.pythonify_list(vals)
    return kt.Applicative(combiner)

# Not a standard Kernel function; for debugging only.
@export('print')
def dbg(val):
    assert isinstance(val, kt.Pair)
    assert val.cdr is kt.nil
    print val.car.tostring()
    return kt.inert

def _guard_continuation(vals, env, cont):
    entry_guards, cont_to_guard, exit_guards = kt.pythonify_list(vals)
    check_guards(entry_guards)
    check_guards(exit_guards)
    assert isinstance(cont_to_guard, kt.Continuation)
    outer_cont = kt.OuterGuardCont(entry_guards, env, cont_to_guard)
    inner_cont = kt.InnerGuardCont(exit_guards, env, outer_cont)
    return cont.plug_reduce(inner_cont)

def check_guards(guards):
    for guard in kt.iter_list(guards):
        interceptor, selector = kt.pythonify_list(guard)
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
             'string']:
    cls = getattr(kt, name.capitalize())
    exports[kt.get_interned(name+"?")] = make_pred(cls)

