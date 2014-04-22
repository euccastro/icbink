import continuation
import environment
import parse
import kernel_type as kt

def run_one_expr(val, env):
    cont = continuation.TerminalContinuation()
    try:
        while True:
            val, env, cont = val.interpret(env, cont)
    except continuation.Done as e:
        return e.value


if __name__ == '__main__':
    expr, = parse.parse('"test"').exprs
    result = run_one_expr(expr, environment.empty_environment())
    assert isinstance(result, kt.String)
    assert result.value == 'test'
    print "All OK."
