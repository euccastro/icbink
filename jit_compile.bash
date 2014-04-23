#!/usr/bin/env bash

pypy ../pypy/rpython/translator/goal/translate.py --opt=jit entry_point.py

