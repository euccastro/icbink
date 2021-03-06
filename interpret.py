#!/usr/bin/env python

import sys

import kernel_type as kt
import primitive


def run(args):
    env = primitive.extended_environment()
    _, filename = args
    try:
        program = primitive.parse_file(filename)
        primitive.kernel_eval(program, env, kt.root_cont)
    except kt.KernelExit:
        pass
    return 0


if __name__ == '__main__':
    run(sys.argv)


