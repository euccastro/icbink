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
    IDENTIFIER: "\+|\-|[a-zA-Z!$%&\*/:<=>\?@\^_~][a-zA-Z0-9!$%&\*\+\-/:<=>\?@\^_~]*";
    STRING: "\"([^\"]|\\\")*\"";
    IGNORE: " |\n|;[^\n]*\n";
    sequence: expr >sequence< | expr;
    expr: <list> | <dotted_list> | <atom>;
    list: ["("] >sequence< [")"];
    dotted_list: ["("] >sequence< ["."] expr [")"];
    atom: <BOOLEAN> | <INERT> | <IGNORE_VAL> | <SUPPRESS> | <STRING> | <IDENTIFIER> | <nil>;
    nil: ["("] [")"];
    """

class Suppress(kt.KernelValue):
    "Not a real Kernel value; just to appease RPython."
    pass
suppress = Suppress()

class Visitor(RPythonVisitor):
    def visit_SUPPRESS(self, node):
        return suppress
    def visit_sequence(self, node):
        return kt.Program(
                filter_suppressed([self.dispatch(c) for c in node.children]))
    def visit_BOOLEAN(self, node):
        return kt.true if node.token.source == "#t" else kt.false
    def visit_IDENTIFIER(self, node):
        return kt.get_interned(node.token.source)
    def visit_STRING(self, node):
        # Remove quotation marks.
        return kt.String(node.token.source[:-1][1:])
    def visit_IGNORE_VAL(self, node):
        return kt.ignore
    def visit_INERT(self, node):
        return kt.inert
    def visit_list(self, node):
        return build_pair_chain(
                filter_suppressed([self.dispatch(c) for c in node.children])
                + [kt.nil])
    def visit_dotted_list(self, node):
        return build_pair_chain(
                filter_suppressed([self.dispatch(c) for c in node.children]))
    def visit_nil(self, node):
        return kt.nil

def iter_with_prev(lst):
    prev = None
    for x in lst:
        yield x, prev
        prev = x

def filter_suppressed(lst):
    return [x
            for x, prev in iter_with_prev(lst)
            if x is not suppress and prev is not suppress]

def build_pair_chain(lst, start=0):
    end = len(lst)
    if end - start == 2:
        return kt.Pair(lst[start], lst[start+1])
    else:
        return kt.Pair(lst[start], build_pair_chain(lst, start+1))

regexs, rules, ToAST = parse_ebnf(grammar)
parse_ebnf = make_parse_function(regexs, rules, eof=True)

def parse(s):
    return Visitor().dispatch(ToAST().transform(parse_ebnf(s)))

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
