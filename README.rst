==============
 Icbink 0.0.0
==============

This aims to be a practical and robust (but not necessarily complete) implementation of `The Kernel Programming Language`_ in RPython_.  This should give us an optimizing JIT compiler almost for free (see `Laurence Tratt's excellent article`_ for more details.)

At the moment guarded continuations look like they're working.  We also have the beginnings of a rudimentary command-line debugger.

Sources of inspiration/pilfering:

* Sam Tobin-Hochstad et al., pycket_: Racket implementation in RPython

* Mariano Guerra's plang_: another shot at Kernel in RPython

* John Shutt's SINK_: scheme-based Kernel implementation

* Queinnec's `Lisp in Small Pieces`_

* Andrés Navarro's Klisp_: to my knowledge, the most mature and complete implementation to date.

.. _The Kernel Programming Language: http://web.cs.wpi.edu/~jshutt/kernel.html
.. _Rpython: http://doc.pypy.org/en/latest/getting-started-dev.html
.. _Laurence Tratt's excellent article: http://tratt.net/laurie/blog/entries/fast_enough_vms_in_fast_enough_time
.. _pycket: https://github.com/samth/pycket
.. _plang: https://github.com/marianoguerra/plang
.. _SINK: http://web.cs.wpi.edu/~jshutt/sink-01m10.tar.gz
.. _Lisp in Small Pieces: http://en.wikipedia.org/wiki/Lisp_in_Small_Pieces
.. _Klisp: http://klisp.org
