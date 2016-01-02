from itertools import product
import os
import stat

from rpython.rlib import jit, rpath, rstring, unroll
from rpython.rlib.parsing.parsing import ParseError
from rpython.rlib.parsing.deterministic import LexerError
from rpython.rlib.rbigint import rbigint

import debug
import kernel_type as kt
import parse

search_paths = ['.'] + os.environ.get('KERNELPATH', '').split(':')

_exports = {}

def export(name, argtypes=None, simple=True):
    operative = name.startswith("$")
    if operative:
        simple = False
    def wrapper(fn):
        if argtypes is None:
            wrapped = fn
        else:
            unroll_argtypes = unroll.unrolling_iterable(argtypes)
            def wrapped(otree, *etc):
                args_tuple = ()
                rest = otree
                for type_ in unroll_argtypes:
                    if isinstance(rest, kt.Pair):
                        arg = rest.car
                        rest = rest.cdr
                        kt.check_type(arg, type_)
                        if isinstance(arg, type_):
                            args_tuple += (arg,)
                        else:
                            kt.signal_type_error(type_, arg)
                    else:
                        kt.signal_arity_mismatch(str(len(argtypes)),
                                                 otree)
                if kt.is_nil(rest):
                    args_tuple += etc
                    return fn(*args_tuple)
                else:
                    kt.signal_arity_mismatch(str(len(argtypes)),
                                             otree)
        if simple:
            comb = kt.SimplePrimitive(wrapped, name)
        else:
            comb = kt.Primitive(wrapped, name)
        if not operative:
            comb = kt.Applicative(comb)
        _exports[name] = comb
        return wrapped
    return wrapper

@export('string-append')
def string_append(vals):
    s = rstring.StringBuilder()
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.String)
        assert isinstance(v, kt.String)
        s.append(v.strval)
    return kt.String(s.build())

@export('continuation->applicative', argtypes=[kt.Continuation])
def continuation2applicative(cont):
    return kt.Applicative(kt.ContWrapper(cont))

@export('guard-continuation',
        [kt.List, kt.Continuation, kt.List],
        simple=False)
def guard_continuation(entry_guards, cont_to_guard, exit_guards, env, cont):
    check_guards(entry_guards)
    check_guards(exit_guards)
    outer_cont = kt.OuterGuardCont(entry_guards, env, cont_to_guard)
    inner_cont = kt.InnerGuardCont(exit_guards, env, outer_cont)
    return inner_cont, env, cont

@export('extend-continuation', simple=False)
def extend_continuation(vals, env, cont):
    args = kt.pythonify_list(vals)
    if len(args) == 2:
        cont_to_extend, receiver = args
        recv_env = kt.Environment([])
    else:
        cont_to_extend, receiver, recv_env = args
    kt.check_type(cont_to_extend, kt.Continuation)
    kt.check_type(receiver, kt.Applicative)
    kt.check_type(recv_env, kt.Environment)
    return kt.ExtendCont(receiver, recv_env, cont_to_extend), env, cont

@export('$sequence')
def sequence(exprs, env, cont):
    return kt.sequence(exprs, env, cont)

@export('$vau')
def vau(operands, env, cont):
    #XXX: check arity flexibly
    assert isinstance(operands, kt.Pair)
    formals = operands.car
    cdr = operands.cdr
    assert isinstance(cdr, kt.Pair)
    eformals = cdr.car
    exprs = cdr.cdr
    return cont.plug_reduce(kt.CompoundOperative(formals, eformals, exprs, env))

@export('$if', [kt.KernelValue, kt.KernelValue, kt.KernelValue])
def if_(test, consequent, alternative, env, cont):
    return test, env, kt.IfCont(consequent, alternative, env, cont)

@export('equal?', [kt.KernelValue, kt.KernelValue])
def equalp(o1, o2):
    return kt.true if o1.equal(o2) else kt.false

@export('cons', [kt.KernelValue, kt.KernelValue])
def cons(car, cdr):
    return kt.Pair(car, cdr)

@export('eval', [kt.KernelValue, kt.Environment], simple=False)
def eval_(expr, env, _, cont):
    return expr, env, cont

@export('make-environment')
def make_environment(vals):
    return kt.Environment(kt.pythonify_list(vals))

@export('$binds?')
def binds(vals, env, cont):
    pyvals = kt.pythonify_list(vals)
    if len(pyvals) < 1:
        kt.signal_arity_mismatch(">=1", vals)
    for symbol in pyvals[1:]:
        kt.check_type(symbol, kt.Symbol)
    env_expr = pyvals[0]
    return env_expr, env, kt.BindsCont(pyvals, cont)

@export('length', [kt.KernelValue])
def length(lst):
    ret = 0
    while isinstance(lst, kt.Pair):
        try:
            ret += 1
        except OverflowError:
            return big_length(ret, lst)
        lst = lst.cdr
    return kt.Fixnum(ret)

@export('list?', [kt.KernelValue])
def listp(val):
    while isinstance(val, kt.Pair):
        val = val.cdr
    return kt.kernel_boolean(kt.is_nil(val))

def big_length(i, lst):
    ret = rbigint.from_int(i)
    while isinstance(lst, kt.Pair):
        ret = ret.add(1)
        lst = lst.cdr
    return kt.Bignum(ret)

@export('$define!', [kt.KernelValue, kt.KernelValue])
def define(definiend, expression, env, cont):
    return expression, env, kt.DefineCont(definiend,
                                          env,
                                          cont,
                                          expression.source_pos)

@export('wrap', [kt.Combiner])
def wrap(combiner):
    return kt.Applicative(combiner)

@export('unwrap', [kt.Applicative])
def unwrap(applicative):
    return applicative.wrapped_combiner

@export('list')
def list_(vals):
    return vals

@export('list*')
def list_star(vals):
    if kt.is_nil(vals):
        kt.signal_arity_mismatch(">=1", vals)
    if not isinstance(vals, kt.Pair):
        kt.signal_value_error("Called list* with non-list", vals)
    if isinstance(vals.cdr, kt.Pair):
        return kt.Pair(vals.car, list_star(vals.cdr))
    elif kt.is_nil(vals.cdr):
        return vals.car
    else:
        return vals

@export('$lambda')
def lambda_(vals, env, cont):
    assert isinstance(vals, kt.Pair)
    formals = vals.car
    exprs = vals.cdr
    return cont.plug_reduce(
            kt.Applicative(
                kt.CompoundOperative(formals, kt.ignore, exprs, env)))

# car, cdr, caar, cadr, ..., caadr, ..., cdddddr.
for length in range(1, 6):
    for adsoup in product('ad', repeat=length):
        name = 'c%sr' % ''.join(adsoup)
        exec("""
@export('%s')
def %s(val):
    assert isinstance(val, kt.Pair)
    assert kt.is_nil(val.cdr)
    return kt.%s(val.car)
""" % (name, name, name))

@export('apply', simple=False)
def apply_(vals, env_ignore, cont):
    ls = kt.pythonify_list(vals)
    if len(ls) == 2:
        applicative, args = ls
        env = kt.Environment([])
    else:
        applicative, args, env = ls
    kt.check_type(applicative, kt.Applicative)
    return kt.Pair(applicative.wrapped_combiner, args), env, cont

@export('map', simple=False)
def map_(vals, env, cont):
    try:
        args = kt.pythonify_list(vals)
    except kt.NonNullListTail:
        kt.signal_value_error("Argument tree to map is not a list", vals)
    else:
        if len(args) < 2:
            kt.signal_arity_mismatch(">=2", vals)
        app = args[0]
        kt.check_type(app, kt.Applicative)
        assert isinstance(app, kt.Applicative)
        lists = args[1:]
        return kt.map_(app.wrapped_combiner,
                       transpose(lists),
                       0,
                       env,
                       cont)

def transpose(pyklists):
    """
    Convert a python list of kernel lists of the form:
        [(a11 ... a1n),
         (... ... ...),
         (am1 ... amn)]
    to a python list of kernel lists of the form:
        [(a11 ... am1),
         (... ... ...),
         (a1n ... amn)]
    """
    try:
        pypylists = [kt.pythonify_list(l) for l in pyklists]
    except kt.NonNullListTail as e:
        kt.signal_value_error("Non-list passed to map", e.val)
    else:
        ln = len(pypylists[0])
        for ls in pypylists[1:]:
            if len(ls) != ln:
                kt.signal_value_error("Different-sized lists passed to map",
                                      kt.kernelify_list(pyklists))
        t = [[l[i] for l in pypylists]
             for i in range(ln)]
        return [kt.kernelify_list([l[i] for l in pypylists])
                for i in range(ln)]

@export('$cond')
def cond(vals, env, cont):
    return kt.cond(vals, env, cont)

@export('call/cc', [kt.Applicative], simple=False)
def call_with_cc(applicative, env, cont):
    return kt.Pair(applicative, kt.Pair(cont, kt.nil)), env, cont

@export('symbol->string', [kt.Symbol])
def symbol2string(symbol):
    return kt.String(symbol.symval)

@export('make-encapsulation-type', [])
def make_encapsulation_type():
    return kt.EncapsulationType().create_methods()

@export('$lazy', [kt.KernelValue], simple=False)
def lazy(expr, env, cont):
    return cont.plug_reduce(kt.Promise(expr, env))

@export('memoize', [kt.KernelValue])
def memoize(val):
    return kt.Promise(val, None)

@export('force', [kt.KernelValue], simple=False)
def force(val, env, cont):
    if isinstance(val, kt.Promise):
        return val.force(cont)
    else:
        return cont.plug_reduce(val)

@export('make-keyed-dynamic-variable', [])
def make_keyed_dynamic_variable():
    return make_keyed_variable(kt.KeyedDynamicBinder,
                               kt.KeyedDynamicAccessor)

@export('make-keyed-static-variable', [])
def make_keyed_static_variable():
    return make_keyed_variable(kt.KeyedStaticBinder,
                               kt.KeyedStaticAccessor)

def make_keyed_variable(binder_class, accessor_class):
    binder = binder_class()
    accessor = accessor_class(binder)
    return kt.Pair(kt.Applicative(binder),
                   kt.Pair(kt.Applicative(accessor), kt.nil))

@export('+')
def add(vals):
    accum = kt.zero
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        accum = accum.add(v)
    return accum

@export('*')
def mul(vals):
    accum = kt.one
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        accum = accum.mul(v)
    return accum

@export('zero?')
def zerop(vals):
    for v in kt.iter_list(vals):
        # Robustness: we need to check the type of all elements, even those
        # after the first non-zero.
        kt.check_type(v, kt.Number)
    for v in kt.iter_list(vals):
        if not kt.zero.equal(v):
            return kt.false
    return kt.true

@export('div', [kt.Number, kt.Number])
def div(a, d):
    if isinstance(a, kt.Infinity):
        kt.signal_divide_infinity(a, d)
    elif d.equal(kt.zero):
        kt.signal_divide_by_zero(a, d)
    else:
        return a.divide_by(d)

@export('mod', [kt.Number, kt.Number])
def mod(a, d):
    if isinstance(a, kt.Infinity):
        kt.signal_divide_infinity(a, d)
    elif d.equal(kt.zero):
        kt.signal_divide_by_zero(a, d)
    else:
        return a.mod_by(d)

@export('div-and-mod', [kt.Number, kt.Number])
def div_and_mod(a, d):
    if isinstance(a, kt.Infinity):
        kt.signal_divide_infinity(a, d)
    elif d.equal(kt.zero):
        kt.signal_divide_by_zero(a, d)
    else:
        return a.divmod_by(d)

@export('-')
def sub(vals):
    ls = kt.pythonify_list(vals)
    if len(ls) < 2:
        kt.signal_arity_mismatch('>=2', vals)
    accum = ls[0]
    for v in ls[1:]:
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        accum = accum.sub(v)
    return accum

@export('=?')
def eq(vals):
    ls = kt.pythonify_list(vals)
    if len(ls) < 2:
        return kt.true
    latest = ls[0]
    for v in ls[1:]:
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        if not latest.equal(v):
            return kt.false
        latest = v
    return kt.true

#XXX: refactor
@export('<=?')
def lteq(vals):
    latest = kt.e_neg_inf
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        if not latest.lteq(v):
            return kt.false
        latest = v
    return kt.true

#XXX: refactor
@export('<?')
def lt(vals):
    latest = kt.e_neg_inf
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        if not latest.lt(v):
            return kt.false
        latest = v
    return kt.true

@export('>?')
def gt(vals):
    latest = kt.e_pos_inf
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        if not v.lt(latest):
            return kt.false
        latest = v
    return kt.true

@export('positive?')
def positive(vals):
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        if not kt.zero.lt(v):
            return kt.false
    return kt.true

@export('negative?')
def negative(vals):
    for v in kt.iter_list(vals):
        kt.check_type(v, kt.Number)
        assert isinstance(v, kt.Number)
        if not v.lt(kt.zero):
            return kt.false
    return kt.true

@export('append')
def append(vals):
    lists = kt.pythonify_list(vals)
    if not lists:
        return kt.nil
    ret = lists.pop()
    for ls in reversed(lists):
        for el in reversed(kt.pythonify_list(ls)):
            ret = kt.Pair(el, ret)
    return ret

@export('and?')
def andp(vals):
    rest = vals
    ret = kt.true
    while isinstance(rest, kt.Pair):
        v = rest.car
        kt.check_type(v, kt.Boolean)
        if kt.false.equal(v):
            ret = kt.false
        rest = rest.cdr
    if kt.is_nil(rest):
        return ret
    else:
        kt.signal_value_error("Called 'and?' with non-list",
                              kt.Pair(vals, kt.nil))

@export('or?')
def orp(vals):
    rest = vals
    ret = kt.false
    while isinstance(rest, kt.Pair):
        v = rest.car
        kt.check_type(v, kt.Boolean)
        if kt.true.equal(v):
            ret = kt.true
        rest = rest.cdr
    if kt.is_nil(rest):
        return ret
    else:
        kt.signal_value_error("Called 'or?' with non-list",
                              kt.Pair(vals, kt.nil))

@export('$and?')
def s_andp(vals, env, cont):
    return kt.s_andp(vals, env, cont)

@export('$or?')
def s_andp(vals, env, cont):
    return kt.s_orp(vals, env, cont)

# Not standard Kernel functions; for debugging only.

@export('print')
def print_(val):
    if isinstance(val, kt.Pair):
        for v in kt.iter_list(val):
            print v.todisplay(),
    else:
        assert kt.is_nil(val)
    return kt.inert

@export('println')
def println(val):
    print_(val)
    print
    return kt.inert

@export('print-tb', simple=False)
def print_tb(val, env, cont):
    c = cont
    while c is not None:
        assert isinstance(c, kt.Continuation)
        if c.source_pos is not None:
            c.source_pos.print_()
        c = c.prev
    return cont.plug_reduce(kt.inert)

class TestError(Exception):
    def __init__(self, val):
        assert isinstance(val, kt.KernelValue)
        self.val = val

# XXX: integrate into error handling system?  start debug REPL?
@export('test-error')
def test_error(val):
    print "ERROR: ",
    println(val)
    raise TestError(val)
    return kt.inert

@export('debug-on')
def _debug_on(val):
    assert kt.is_nil(val)
    debug.start_stepping()
    return kt.inert

@export('debug-off')
def _debug_off(val):
    assert kt.is_nil(val)
    debug.stop_stepping()
    return kt.inert

class AdHocException(Exception):
    def __init__(self, val):
        self.val = val

class AdHocCont(kt.Continuation):
    def _plug_reduce(self, val):
        raise AdHocException(val)

def kernel_eval(val, env, cont=None):
    if cont is None:
        cont = AdHocCont(kt.root_cont)
    try:
        while True:
            driver.jit_merge_point(val=val, env=env, cont=cont)
            val_, env_, cont_ = debug.on_eval(val, env, cont)
            if val_ is not None:
                val, env, cont = val_, env_, cont_
            try:
                val, env, cont = val.interpret(env, cont)
            except kt.KernelException as e:
                error = e.val
                error.val = val
                error.env = env
                error.src_cont = cont
                val, env, cont = kt.abnormally_pass(error, cont, e.val.dest_cont)
    except AdHocException as e:
        return e.val

def get_printable_location(green_val):
    if green_val is None:
        return "No green val"
    else:
        return green_val.tostring()

driver = jit.JitDriver(reds=['env', 'cont'],
                       greens=['val'],
                       get_printable_location=get_printable_location)


def file_exists(path):
    try:
        st = os.stat(path)
    except OSError:
        return False
    return not stat.S_ISDIR(st.st_mode)

@export('load', [kt.String], simple=False)
def load_(path, env, cont):
    # XXX: have some programmatically editable search path?
    filename = path.strval
    for dir_path in search_paths:
        whole_path = rpath.rjoin(dir_path, filename)
        if file_exists(whole_path):
            try:
                program = parse_file(whole_path)
            except ParseError as e:
                return kt.signal_parse_error(e.nice_error_message(),
                                             whole_path)
            except LexerError as e:
                return kt.signal_parse_error(e.nice_error_message(),
                                             whole_path)
            return program, env, kt.ConstantCont(kt.inert, cont)
    else:
        return kt.signal_file_not_found(filename)

def parse_file(path):
    src = open(path).read()  # XXX: RPython?
    return kt.Pair(_ground_env.bindings['$sequence'],
                   parse.parse(src, path))

def check_guards(guards):
    for guard in kt.iter_list(guards):
        selector, interceptor = kt.pythonify_list(guard)
        kt.check_type(selector, kt.Continuation)
        kt.check_type(interceptor, kt.Applicative)
        kt.check_type(interceptor.wrapped_combiner, kt.Operative)

def make_pred(cls, name):
    def pred(vals):
        result = kt.true
        rest = vals
        while isinstance(rest, kt.Pair):
            val = rest.car
            if not isinstance(val, cls):
                result = kt.false
            rest = rest.cdr
        if kt.is_nil(rest):
            return result
        else:
            kt.signal_value_error(("Called predicate '%s' with non-list" % name),
                                  kt.Pair(vals, kt.nil))
    return kt.Applicative(kt.SimplePrimitive(pred, name))

for cls in [kt.Boolean,
            kt.Symbol,
            kt.Inert,
            kt.Pair,
            kt.Null,
            kt.Environment,
            kt.Continuation,
            kt.Ignore,
            kt.Operative,
            kt.Applicative,
            kt.Combiner,
            kt.String,
            kt.Number,
            kt.Promise,
            kt.ErrorObject]:
    pred_name = cls.type_name + "?"
    _exports[pred_name] = make_pred(cls, pred_name)
del pred_name, cls

# Not standard Kernel and not real type predicates.
_exports['fixnum?'] = make_pred(kt.Fixnum, 'fixnum?')
_exports['bignum?'] = make_pred(kt.Bignum, 'bignum?')

def empty_environment():
    return kt.Environment([], {})

def standard_environment():
    return kt.Environment([_ground_env], {})

def extended_environment():
    return kt.Environment([_extended_env], {})

_exports['root-continuation'] = kt.root_cont
_exports['error-continuation'] = kt.error_cont
_exports['system-error-continuation'] = kt.system_error_cont
_exports['user-error-continuation'] = kt.user_error_cont
_exports['file-not-found-continuation'] = kt.file_not_found_cont
_exports['parse-error-continuation'] = kt.parse_error_cont
_exports['unbound-dynamic-key-continuation'] = kt.unbound_dynamic_key_cont
_exports['unbound-static-key-continuation'] = kt.unbound_static_key_cont
_exports['type-error-continuation'] = kt.type_error_cont
_exports['value-error-continuation'] = kt.value_error_cont
_exports['combine-with-non-list-operands-continuation'] = kt.combine_with_non_list_operands_cont
_exports['encapsulation-type-error-continuation'] = kt.encapsulation_type_error_cont
_exports['operand-mismatch-continuation'] = kt.operand_mismatch_cont
_exports['arity-mismatch-continuation'] = kt.arity_mismatch_cont
_exports['symbol-not-found-continuation'] = kt.symbol_not_found_cont
_exports['add-positive-to-negative-infinity-continuation'] = kt.add_positive_to_negative_infinity_cont
_exports['multiply-infinity-by-zero-continuation'] = kt.multiply_infinity_by_zero_cont
_exports['divide-infinity-continuation'] = kt.divide_infinity_cont
_exports['divide-by-zero-continuation'] = kt.divide_by_zero_cont

_ground_env = kt.Environment([], _exports)

def dirname(path):
    norm = rpath.rnormpath(path)
    if not rpath.risabs(norm):
        norm = rpath.rjoin(".", norm)
    return norm.rsplit(rpath.sep, 1)[0]

print "file si", __file__

here = dirname(__file__)

kernel_eval(parse_file(rpath.rjoin(here, "kernel.k")), _ground_env)
_extended_env = kt.Environment([_ground_env], {})
kernel_eval(parse_file(rpath.rjoin(here, "extension.k")), _extended_env)

def standard_value(name):
    return _ground_env.bindings[name]

del _exports
