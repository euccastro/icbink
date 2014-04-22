from rpython.rlib import jit

import environment
import interpret
import parse
import kernel_type as kt

def entry_point(argv):
    jit.set_param(None, "trace_limit", 20000)
    expr, = parse.parse('"test"').exprs
    result = interpret.run_one_expr(expr, environment.empty_environment())
    assert isinstance(result, kt.String)
    assert result.value == 'test'
    print "All OK."
    return 0

def target(driver, args):
    return entry_point, None
