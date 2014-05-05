#!/usr/bin/env python

import sys

import primitive


def run(args):
    env = primitive.extended_environment()
    _, filename = args
    primitive.load(filename, env)
    return 0


if __name__ == '__main__':
    run(sys.argv)


