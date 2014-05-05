#!/usr/bin/env python

import sys

from rpython.rlib import jit

import debug
import kernel_type as kt
import parse
import primitive


def empty_environment():
    return kt.Environment([], {})

def standard_environment():
    return kt.Environment([_ground_env], {})

def extended_environment():
    return kt.Environment([_extended_env], {})


def run_one_expr(val,
                 env):
    cont = kt.TerminalCont()
    try:
        while True:
            driver.jit_merge_point(val=val, env=env, cont=cont)
            debug.on_eval(val, env, cont)
            try:
                val, env, cont = val.interpret(env, cont)
            except kt.KernelError as e:
                debug.on_error(e, val, env, cont)
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
    expr, = parse.parse(expr_str).data
    return run_one_expr(expr, env)

def load(path, env):
    src = open(path).read()
    src_lines = src.split("\n")
    program = parse.parse(src, path)
    for expr in program.data:
        run_one_expr(expr, env)

def run(args):
    env = extended_environment()
    _, filename = args
    load(filename, env)
    return 0

def test():
    run(["_", "test.k"])

_ground_env = kt.Environment([], primitive.exports)
load("kernel.k", _ground_env)
_extended_env = kt.Environment([_ground_env], {})
load("extension.k", _extended_env)


if __name__ == '__main__':
    run(sys.argv)


