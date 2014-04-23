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

