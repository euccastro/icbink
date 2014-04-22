from rpython.rlib import rstring

import kernel_type as kt


def string_append(vals):
    s = rstring.StringBuilder()
    while vals is not kt.nil:
        assert isinstance(car, kt.Pair)
        car = vals.car
        assert isinstance(car, kt.String)
        s.append(car.value)
        vals = vals.cdr
    return kt.String(s.build)
