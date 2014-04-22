class KernelObject(object):
    def equal(self, other):
        return other is self
    def eq(self, other):
        return other is self

class String(KernelObject):
    pass

#XXX: Just using Python ints for now; let's break down into exact/inexact etc.
class Number(KernelObject):
    pass

class Symbol(KernelObject):
    pass

class Nil(KernelObject):
    pass

nil = Nil()

class Boolean(KernelObject):
    pass

true = Boolean()
false = Boolean()
