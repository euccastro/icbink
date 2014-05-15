The debugger
============

icbink features a simple command-line debugger.  It allows you to step into user code, see the values to which expressions evaluate, enter expressions to be evaluated in the command line, and display the local environment and its parents.

Breakpoints are currently not implemented.  They shouldn't be hard to add; add an issue to the github tracker if you want them.

Usage
-----

Insert ``(debug-on)`` in the spot where you want to start stepping into the code.  Then run your program normally (using something like rlwrap_ is *highly* recommended; readline functionality is not implemented natively ATM).  Interpretation will pause when the call to ``debug-on`` is hit, and a prompt will appear on your screen.  There you can enter the following commands:

- ``,s``: step into next expression.
- ``,n``: step over next expression.
- ``,r``: continue until current form is evaluated (roughly, get out of enclosing parens).
- ``,c``: continue (stop stepping).
- ``,c <expr>``: evaluate ``<expr>`` in the current environment, return its value instead of that of the expression we were about to evaluate.
- ``,E``: print local environment and all its parents (indented, separated by ``---``).
- ``,e``: print local environment only.
- (any kernel expression): evaluate the expression in the local environment.

If you just hit the <enter> key without inputting any text, the latest command --if any-- will be repeated.

How does it work
----------------

When we parse the source code and generate the pairs, symbols and literals that comprise the program or module, we assign each such kernel object a "source info" object (see ``parse.py``).  In addition, we propagate this source info to the continuations that will receive the results of evaluating these expressions, so we can print the source location along with such results.

The debugger (see ``debug.py``) exposes some RPython functions that the interpreter logic calls to notify that

- an expression is about to be evaluated,
- a value is about to be plugged back to a continuation, or that
- an abnormal pass is about to be initiated.

By default, the debugger just ignores these calls.  When we enter stepping mode (through ``debug-on``), the debugger prompts the user for commands whenever the interpreter is about to evaluate any expression that has a source info (skipping the library functions in ``kernel.k`` and ``extension.k``, since I found stepping through the bodies of these is seldom helpful -).  ``debug.debug_interaction`` implements the debug REPL, and ``debug.StepHook`` contains the logic for triggering it.  For ``,n`` and ``,r``, ``debug.ResumeContHook`` is used, which skips evaluations until the continuation of interest 'returns' (receives a value) and then resumes stepping mode.

If any of this is unclear or if you can think of a better explanation, please ask_ any questions or sumbit a PR for docs improvements.

.. _rlwrap: http://freecode.com/projects/rlwrap
.. _ask: mailto:euccastro@gmail.com
