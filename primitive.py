from rpython.rlib import rstring

import kernel_type as kt


exports = {}

def export(name, simple=True, applicative=True):
    def wrapper(fn):
        if simple:
            comb = kt.SimplePrimitive(fn)
        else:
            comb = kt.Primitive(fn)
        if applicative:
            comb = kt.Applicative(comb)
        exports[kt.get_interned(name)] = comb
        return fn
    return wrapper

@export('string-append')
def string_append(vals):
    s = rstring.StringBuilder()
    for v in _parse_vals(vals):
        assert isinstance(v, kt.String)
        s.append(v.value)
    return kt.String(s.build())

def _parse_vals(vals):
    if vals is kt.nil:
        return
    while isinstance(vals, kt.Pair):
        yield vals.car
        vals = vals.cdr

