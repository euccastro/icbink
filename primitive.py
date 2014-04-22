def string_append(ss):
    #XXX: if RPython complains, make a StringBuilder.
    return ''.join([s.value for s in ss])
