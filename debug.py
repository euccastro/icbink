import os

import parse


class DebugHook(object):
    def on_eval(self, val, env, cont):
        pass
    def on_plug_reduce(self, val, cont):
        pass
    def on_abnormal_pass(self,
                         val_tree,
                         src_cont,
                         dst_cont,
                         exiting,
                         entering):
        pass

class StepHook(DebugHook):
    def on_eval(self, val, env, cont):
        if val.source_pos is not None:
            val.source_pos.print_()
            debug_interaction(env, cont)
    def on_plug_reduce(self, val, cont):
        if cont.source_pos is not None:
            cont.source_pos.print_()
            print "<<< RETURN", val.tostring()
    def on_abnormal_pass(self,
                         val_tree,
                         src_cont,
                         dst_cont,
                         exiting,
                         entering):
        print "*** ABNORMAL PASS of %s from %s to %s" % (
                val_tree.tostring(),
                src_cont.tostring(),
                dst_cont.tostring())

class ResumeContHook(DebugHook):
    def __init__(self, env, cont):
        self.env = env
        self.cont = cont
    def on_plug_reduce(self, val, cont):
        if cont is self.cont:
            if cont.source_pos is not None:
                cont.source_pos.print_()
            print "<<< RETURN", val.tostring()
            debug_interaction(self.env, cont)
    def on_abnormal_pass(self,
                         val_tree,
                         src_cont,
                         dst_cont,
                         exiting,
                         entering):
        #XXX: interact?
        for cont, interceptor in exiting:
            if cont is self.cont:
                print "*** EXITED THROUGH ABNORMAL PASS of %s from %s to %s" % (
                        val_tree.tostring(),
                        src_cont.tostring(),
                        dst_cont.tostring())
                break
        else:
            for cont, interceptor in entering:
                if cont is self.cont:
                    print "*** ENTERED THROUGH ABNORMAL PASS of %s from %s to %s" % (
                            val_tree.tostring(),
                            src_cont.tostring(),
                            dst_cont.tostring())

class DebugState(object):
    def __init__(self):
        self.latest_command = None
        self.step_hook = None
        self.breakpoints = []  #XXX
    def on_eval(self, val, env, cont):
        if self.step_hook is not None:
            self.step_hook.on_eval(val, env, cont)
    def on_plug_reduce(self, val, cont):
        if self.step_hook is not None:
            self.step_hook.on_plug_reduce(val, cont)
    def on_abnormal_pass(self,
                         val_tree,
                         src_cont,
                         dst_cont,
                         exiting,
                         entering):
        if self.step_hook is not None:
            self.step_hook.on_abnormal_pass(val_tree,
                                            src_cont,
                                            dst_cont,
                                            exiting,
                                            entering)
    def on_error(self, e, val, env, cont):
        print "*** ERROR *** :", e.message, e
        print "Trying to evaluate %s" % val.tostring()
        if val.source_pos:
            val.source_pos.print_()
        debug_interaction(env, cont)

def debug_interaction(env, cont):
    try:
        while True:
            os.write(1, "> ")
            cmd = readline()
            if cmd == "":
                if _state.latest_command is not None:
                    cmd = _state.latest_command
                else:
                    continue
            _state.latest_command = cmd
            if cmd == ",c":
                stop_stepping()
                break
            elif cmd == ",s":
                start_stepping()
                break
            elif cmd == ",n":
                _state.step_hook = ResumeContHook(env, cont)
                break
            elif cmd == ",r":
                prev = cont.prev
                while prev is not None and prev.source_pos is None:
                    prev = prev.prev
                if prev is None:
                    stop_stepping()
                else:
                    import kernel_type as kt
                    if isinstance(cont, kt.EvalArgsCont):
                        resume_env = env
                    else:
                        # Body of a compound operative.
                        resume_env, = env.parents
                    _state.step_hook = ResumeContHook(resume_env, prev)
                break
            elif cmd == ",e":
                print_bindings(env, recursive=False)
            elif cmd == ",E":
                print_bindings(env, recursive=True)
            elif cmd == ",q":
                raise SystemExit
            else:
                import interpret
                dbgexprs = parse.parse(cmd)
                for dbgexpr in dbgexprs.data:
                    old = _state.step_hook
                    _state.step_hook = None
                    try:
                        dbg_val = interpret.run_one_expr(
                                dbgexpr,
                                env)
                        print dbg_val.tostring()
                    finally:
                        _state.step_hook = old
    except EOFError:
        stop_stepping()

#XXX Adapted from Mariano Guerra's plang; research whether there's equivalent
#    functionality in rlib.
#    Also try and get libreadline-like goodies.
def readline():
    result = []
    while True:
        s = os.read(0, 1)
        if s == '\n':
            break
        if s == '':
            if len(result) > 0:
                break
            else:
                raise EOFError
        result.append(s)
    return "".join(result)

def print_bindings(env, recursive=False, indent=0):
    for k, v in env.bindings.iteritems():
        print "    " * indent, k, ":", v.tostring()
    if recursive:
        for parent in env.parents:
            print " ---"
            print_bindings(parent, True, indent+1)

def start_stepping():
    _state.step_hook = step_hook

def stop_stepping():
    _state.step_hook = None

_state = DebugState()
on_eval = _state.on_eval
on_plug_reduce = _state.on_plug_reduce
on_abnormal_pass = _state.on_abnormal_pass
on_error = _state.on_error

step_hook = StepHook()
