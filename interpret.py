from rpython.rlib import jit

import kernel_type as kt
import parse
import primitive


def empty_environment():
    return kt.Environment([], {})

def _simple_applicative(fn):
    return kt.Applicative(kt.SimplePrimitive(fn))

class _GroundEnvironmentContainer:
    env = None

def pythonify(s):
    return s.replace('-', '_')

def init_ground_environment():
    d = dict([(kt.get_interned(name),
               _simple_applicative(getattr(primitive, pythonify(name))))
              for name in ['string-append']])
    _GroundEnvironmentContainer.env = kt.Environment([], d)

def standard_environment():
    return kt.Environment([_GroundEnvironmentContainer.env], {})

def run_one_expr(val, env):
    cont = kt.TerminalCont()
    try:
        while True:
            driver.jit_merge_point(val=val, env=env, cont=cont)
            val, env, cont = val.interpret(env, cont)
    except kt.Done as e:
        return e.value

def get_printable_location(green_val):
    if green_val is None:
        return "No green val"
    else:
        return green_val.tostring()
driver = jit.JitDriver(reds=['env', 'cont'],
                       greens=['val'],
                       get_printable_location=get_printable_location)


def keval(expr_str, env):
    expr, = parse.parse(expr_str).exprs
    return run_one_expr(expr, env)

def test():
    init_ground_environment()
    env = standard_environment()
    env.set(kt.get_interned('x'), kt.String('the-value-bound-by-x'))
    for expr_str, typ, value in [('"one"', kt.String, 'one'),
                                 ('x', kt.String, 'the-value-bound-by-x')]:
        result = keval(expr_str, env)
        assert isinstance(result, typ)
        assert result.value == value
    assert isinstance(keval('string-append', env), kt.Applicative)
    print "All OK."

if __name__ == '__main__':
    test()

