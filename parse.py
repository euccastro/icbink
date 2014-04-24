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
    IDENTIFIER: "\+|\-|[a-zA-Z!$%&\*/:<=>\?@\^_~][a-zA-Z0-9!$%&\*\+\-/:<=>\?@\^_~]*";
    STRING: "\"([^\"]|\\\")*\"";
    IGNORE_VAL: "#ignore";
    INERT: "#inert";
    IGNORE: " |\n|;[^\n]*\n";
    sequence: expr >sequence< | expr;
    expr: <list> | <dotted_list> | <atom>;
    list: ["("] >sequence< [")"];
    dotted_list: ["("] >sequence< ["."] expr [")"];
    atom: <BOOLEAN> | <STRING> | <IDENTIFIER> | <nil>;
    nil: ["("] [")"];
    """

class Visitor(RPythonVisitor):
    def visit_sequence(self, node):
        return kt.Program([self.dispatch(c) for c in node.children])
    def visit_BOOLEAN(self, node):
        return kt.true if node.token.source == "#t" else kt.false
    def visit_IDENTIFIER(self, node):
        return kt.get_interned(node.token.source)
    def visit_STRING(self, node):
        # Remove quotation marks.
        return kt.String(node.token.source[:-1][1:])
    def visit_IGNORE_VAL(self, node):
        return kt.ignore
    def visit_INERT_VAL(self, node):
        return kt.inert
    def visit_list(self, node):
        return build_pair_chain([self.dispatch(c) for c in node.children]
                                + [kt.nil])
    def visit_dotted_list(self, node):
        return build_pair_chain([self.dispatch(c) for c in node.children])
    def visit_nil(self, node):
        return kt.nil

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

def test():
    try:
        ast = parse('($one #t (#f () . ("5"))) "2"; This is a comment.\n"2.5" ( "3" "3.5" . "rest" ) \n"4.6" ("1") ("3" . ()) ("4" ()) ')
        #ast.view()
        transformed = ToAST().transform(ast)
        #transformed.view()
        program = Visitor().dispatch(transformed)
    except ParseError as e:
        print e.nice_error_message()
    import pdb
    pdb.set_trace()

if __name__ == '__main__':
    test()
