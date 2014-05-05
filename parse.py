#!/usr/bin/env python

#-*- coding: utf-8 -*-

__all__ = ['parse']

from rpython.rlib.parsing.ebnfparse import parse_ebnf, make_parse_function
from rpython.rlib.parsing.parsing import ParseError
from rpython.rlib.parsing.tree import RPythonVisitor

import kernel_type as kt


# cf. R-1RK sec. 2.1, although I don't claim all regexes are correct at this
# point.  They're just something to work with; I'll review them for correctness
# later.
grammar = r"""
    BOOLEAN: "#t|#f";
    INERT: "#inert";
    IGNORE_VAL: "#ignore";
    SUPPRESS: "#;";
    LEFT_PAREN: "\(";
    RIGHT_PAREN: "\)";
    IDENTIFIER: "\+|\-|[a-zA-Z!$%&\*/:<=>\?@\^_~][a-zA-Z0-9!$%&\*\+\-/:<=>\?@\^_~]*";
    STRING: "\"([^\"]|\\\")*\"";
    IGNORE: " |\n|;[^\n]*\n";
    sequence: expr >sequence< | expr;
    expr: <list> | <dotted_list> | <atom>;
    list: LEFT_PAREN >sequence< RIGHT_PAREN;
    dotted_list: LEFT_PAREN >sequence< ["."] expr RIGHT_PAREN;
    atom: <BOOLEAN> | <INERT> | <IGNORE_VAL> | <SUPPRESS> | <STRING> | <IDENTIFIER> | <nil>;
    nil: LEFT_PAREN RIGHT_PAREN;
    """

class Suppress(kt.KernelValue):
    "Not a real Kernel value; just to appease RPython."
    pass
suppress = Suppress()
suppress_next = Suppress()

class SourceFile(object):
    _immutable_fields_ = ['path', 'lines']
    def __init__(self, path, lines):
        self.path = path
        self.lines = lines

class SourcePos(object):
    _immutable_fields_ = ['source_file', 'line', 'column']
    def __init__(self, source_file, line, column):
        self.source_file = source_file
        self.line = line
        self.column = column
    def print_(self):
        # Editors show 1-based line and column numbers, while
        # source_pos objects are 0-based.
        print "%s, line %s, column %s:" % (self.source_file.path,
                                           self.line + 1,
                                           self.column + 1)
        print self.source_file.lines[self.line]
        print "%s^" % (" " * self.column)

class Visitor(RPythonVisitor):
    def __init__(self, source_file=None):
        RPythonVisitor.__init__(self)
        self.source_file = source_file
    def visit_SUPPRESS(self, node):
        return suppress_next
    def visit_sequence(self, node):
        return self.visit_list(node)
    def visit_BOOLEAN(self, node):
        return kt.Boolean(node.token.source == '#t',
                          self.make_src_pos(node))
    def visit_IDENTIFIER(self, node):
        return kt.Symbol(node.token.source,
                         self.make_src_pos(node))
    def visit_STRING(self, node):
        # Remove quotation marks.
        return kt.String(node.token.source[:-1][1:],
                         self.make_src_pos(node))
    def visit_IGNORE_VAL(self, node):
        return kt.Ignore(self.make_src_pos(node))
    def visit_INERT(self, node):
        return kt.Inert(self.make_src_pos(node))
    def visit_list(self, node):
        return build_pair_chain(
                filter_suppressed([self.dispatch(c) for c in node.children])
                + [kt.nil],
                self.make_src_pos(node))
    def visit_dotted_list(self, node):
        return build_pair_chain(
                filter_suppressed([self.dispatch(c) for c in node.children]),
                self.make_src_pos(node))
    def visit_nil(self, node):
        return kt.Null(self.make_src_pos(node))
    def visit_LEFT_PAREN(self, node):
        return suppress
    def visit_RIGHT_PAREN(self, node):
        return suppress
    def make_src_pos(self, node):
        src_pos = node.getsourcepos()
        return SourcePos(self.source_file, src_pos.lineno, src_pos.columnno)

def iter_with_prev(lst):
    prev = None
    for x in lst:
        yield x, prev
        prev = x

def filter_suppressed(lst):
    return [x
            for x, prev in iter_with_prev(lst)
            if not isinstance(x, Suppress)
               and prev is not suppress_next]

def build_pair_chain(lst, source_pos, start=0):
    end = len(lst)
    if end - start == 2:
        return kt.Pair(lst[start], lst[start+1], source_pos=source_pos)
    else:
        return kt.Pair(lst[start], build_pair_chain(lst, None, start+1), source_pos=source_pos)

regexs, rules, ToAST = parse_ebnf(grammar)
parse_ebnf = make_parse_function(regexs, rules, eof=True)

def parse(s, path='<no path>'):
    source_file = SourceFile(path, s.split("\n"))
    return Visitor(source_file).dispatch(ToAST().transform(parse_ebnf(s)))

def test(s):
    try:
        ast = parse_ebnf(s)
        ast.view()
        transformed = ToAST().transform(ast)
        transformed.view()
        program = Visitor().dispatch(transformed)
        print program.tostring()
    except ParseError as e:
        print e.nice_error_message()
    import pdb
    pdb.set_trace()

if __name__ == '__main__':
    import sys
    src = file(sys.argv[1]).read()
    print src
    test(src)
