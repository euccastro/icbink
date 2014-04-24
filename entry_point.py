from rpython.rlib import jit

import interpret
import parse
import kernel_type as kt

def entry_point(argv):
    jit.set_param(None, "trace_limit", 20000)
    interpret.run(argv)
    return 0

def target(driver, args):
    return entry_point, None
