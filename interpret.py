#!/usr/bin/env python

import os
import sys

from rpython.rlib import jit

import kernel_type as kt
import parse
import primitive


def empty_environment():
    return kt.Environment([], {})

def standard_environment():
    return kt.Environment([_ground_env], {})

def extended_environment():
    return kt.Environment([_extended_env], {})

def print_bindings(env, recursive=False, indent=0):
    for k, v in env.bindings.iteritems():
        print "    " * indent, k, ":", v.tostring()
    if recursive:
        for parent in env.parents:
            print " ---"
            print_bindings(parent, True, indent+1)

def run_one_expr(val,
                 env,
                 debug_data=None,
                 ignore_debug=False):
    if debug_data is None:
        debug_data = DebugData()
    cont = kt.TerminalCont()
    try:
        while True:
            if val.source_pos is not None:
                debug_data.source_pos = val.source_pos
            if (not ignore_debug
                and primitive.debug_mode()
                and val.source_pos is not None):
                print
                debug_interaction(debug_data, env, cont)
            driver.jit_merge_point(val=val, env=env, cont=cont)
            primitive.trace(":: interpreting ", val.tostring())
            try:
                val, env, cont = val.interpret(env, cont)
            except (kt.KernelError, AssertionError) as e:
                print
                #XXX: find out how to print (something like a) Python traceback
                #     in RPython
                print "*** ERROR *** :", repr(e), e.message
                debug_interaction(debug_data, env, cont)
    except kt.Done as e:
        return e.value

class DebugData:
    def __init__(self, source_pos=None, command=None, skip=False):
        self.source_pos = source_pos
        self.command = command
        self.skip = skip

class DebugHook(object):
    def trigger(self, val, cont):
        raise NotImplementedError

cont_hooks = {}

class ReturnDebugHook(DebugHook):
    def trigger(self, cont, val):
        try:
            source_pos, debug_data, env = cont_hooks[cont]
        except KeyError:
            return
        print
        print "<< returns", val.tostring()
        if debug_data.skip:
            return
        debug_interaction(DebugData(source_pos,
                                    debug_data.command,
                                    debug_data.skip),
                          env,
                          cont)

class ResumeDebugHook(DebugHook):
    def __init__(self, cont, debug_data):
        self.cont = cont
        self.debug_data = debug_data
    def trigger(self, cont, val):
        if cont is self.cont:
            print "matched cont!", cont
            self.debug_data.skip = False

class ResumeOnContainingCombineDebugHook(DebugHook):
    def __init__(self, cont, debug_data):
        self.cont = cont
        self.debug_data = debug_data
    def trigger(self, cont, val):
        if isinstance(cont, kt.CombineCont):
            c = cont
            while True:
                if c is None:
                    print "found combinecont!", cont, cont.prev
                    debug_hooks[debug_hooks.index(self)] = ResumeDebugHook(
                            cont.prev, self.debug_data)
                    return
                elif c is self.cont:
                    return
                c = c.prev

debug_hooks = []

return_debug_hook = ReturnDebugHook()

def return_hook_callback(val, cont):
    if primitive.debug_mode():
        for hook in debug_hooks:
            hook.trigger(val, cont)
        return_debug_hook.trigger(val, cont)

kt.return_hook.callback = return_hook_callback

def debug_interaction(debug_data, env, cont):
    if debug_data.skip:
        return
    debug_data.source_pos.print_()
    try:
        while True:
            os.write(1, "> ")
            cont_hooks[cont] = debug_data.source_pos, debug_data, env
            cmd = readline()
            if cmd == "":
                if debug_data.command is not None:
                    cmd = debug_data.command
                else:
                    continue
            debug_data.command = cmd
            if cmd == ",c":
                cont_hooks.clear()
                del debug_hooks[:]
                primitive.debug(False)
                break
            elif cmd == ",s":
                break
            elif cmd == ",n":
                debug_data.skip = True
                debug_hooks.append(ResumeDebugHook(cont, debug_data))
                break
            elif cmd == ",r":
                debug_data.skip = True
                debug_hooks.append(ResumeOnContainingCombineDebugHook(cont, debug_data))
                break
            elif cmd == ",e":
                print_bindings(env, recursive=False)
            elif cmd == ",E":
                print_bindings(env, recursive=True)
            elif cmd == ",q":
                raise SystemExit
            else:
                dbgexprs = parse.parse(cmd)
                for dbgexpr in dbgexprs.data:
                    dbg_val = run_one_expr(dbgexpr,
                                           env,
                                           debug_data,
                                           ignore_debug=True)
                    print dbg_val.tostring()
    except EOFError:
        primitive.debug(False)

#XXX adapted from Mariano Guerra's plang; research whether there's equivalent
#    functionality in rlib.
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


