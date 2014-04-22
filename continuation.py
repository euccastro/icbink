class Done(Exception):
    def __init__(self, value):
        self.value = value

class Continuation(object):
    pass

class TerminalContinuation(Continuation):
    def plug_reduce(self, val):
        raise Done(val)

