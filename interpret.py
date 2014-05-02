#!/usr/bin/env python

import os
import sys

from rpython.rlib import jit

import kernel_type as kt
import parse
import primitive


def empty_environment():
    return kt.Environment([], {})

_ground_env = kt.Environment([], primitive.exports)

def standard_environment():
    return kt.Environment([_ground_env], {})

def run_one_expr(val, env, ignore_debug=False):
    cont = kt.TerminalCont()
    try:
        while True:
            if (not ignore_debug
                and primitive.debug_mode()
                and val.source_pos is not None):
                print "line", val.source_pos.lineno,
                print ", col", val.source_pos.columnno
                # XXX: optionally take source filename so we can show the line
                # instead
                print val.tostring()
                try:
                    while True:
                        os.write(1, "> ")
                        cmd = readline()
                        if cmd == "":
                            continue
                        elif cmd == ",c":
                            primitive.debug_off()
                            break
                        elif cmd == ",s":
                            break
                        else:
                            dbgexprs = parse.parse(cmd)
                            for dbgexpr in dbgexprs.data:
                                dbg_val = run_one_expr(dbgexpr,
                                                       env,
                                                       ignore_debug=True)
                                print dbg_val.tostring()
                except EOFError:
                    primitive.debug_off()
                    break
            driver.jit_merge_point(val=val, env=env, cont=cont)
            primitive.trace(":: interpreting ", val.tostring())
            val, env, cont = val.interpret(env, cont)
    except kt.Done as e:
        return e.value

#XXX adapted from Mariano Guerra's plang; research whether there's equivalent functionality in rlib.
def readline():
    result = []
    while True:
        s = os.read(0, 1)
        if s == '\n':
            break
        if s == '':
            if len(result) > 0:
                break
            else:
                raise EOFError
        result.append(s)
    return "".join(result)

def get_printable_location(green_val):
    if green_val is None:
        return "No green val"
    else:
        return green_val.tostring()
driver = jit.JitDriver(reds=['env', 'cont'],
                       greens=['val'],
                       get_printable_location=get_printable_location)


def keval(expr_str, env):
    expr, = parse.parse(expr_str).data
    return run_one_expr(expr, env)

def test():
    env = standard_environment()
    env.set(kt.get_interned('x'), kt.String('the-value-bound-by-x'))
    for expr_str, typ, value in [('"one"', kt.String, 'one'),
                                 ('x', kt.String, 'the-value-bound-by-x'),
                                 ('(string-append)', kt.String, ''),
                                 ('(string-append "one")', kt.String, 'one'),
                                 ('(string-append "one" "two")', kt.String, 'onetwo'),
                                 ]:
        result = keval(expr_str, env)
        assert isinstance(result, typ)
        assert result.value == value
    assert isinstance(keval('string-append', env), kt.Applicative)
    print "All OK."

def load(filename, env):
    src = open(filename).read()
    program = parse.parse(src)
    for expr in program.data:
        run_one_expr(expr, env)

def run(args):
    env = standard_environment()
    _, filename = args
    load("kernel.k", env)
    load("extension.k", env)
    load(filename, env)
    return 0

def test():
    run(["_", "test.k"])

if __name__ == '__main__':
    run(sys.argv)


