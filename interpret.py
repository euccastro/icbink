from rpython.rlib import jit

import continuation
import environment
import parse
import kernel_type as kt

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

if __name__ == '__main__':
    expr, = parse.parse('"test"').exprs
    result = run_one_expr(expr, environment.empty_environment())
    assert isinstance(result, kt.String)
    assert result.value == 'test'
    print "All OK."
