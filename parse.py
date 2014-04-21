#-*- coding: utf-8 -*-

from rpython.rlib.parsing.ebnfparse import parse_ebnf, make_parse_function
from rpython.rlib.parsing.tree import Symbol, Nonterminal, RPythonVisitor
from rpython.rlib.parsing.parsing import ParseError

# cf. R-1RK sec. 2.1
grammar = r"""
    BOOLEAN: "#t|#f";
    IDENTIFIER: "\+|\-|[a-zA-Z!$%&\*/:<=>\?@\^_~][a-zA-Z0-9!$%&\*\+\-/:<=>\?@\^_~]*";
    NUMBER: "\-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][\+\-]?[0-9]+)?";
    STRING: "\"([^\"]|\\\")*\"";
    IGNORE: " |\n|;[^\n]*\n";
    sequence: expr >sequence< | expr;
    expr: <list> | <dotted_list> | <atom>;
    list: ["("] >sequence< [")"];
    dotted_list: ["("] >sequence< ["."] expr [")"];
    atom: <BOOLEAN> | <STRING> | <NUMBER> | <IDENTIFIER> | <nil>;
    nil: ["("] [")"];
    """

regexs, rules, ToAST = parse_ebnf(grammar)
parse = make_parse_function(regexs, rules, eof=True)

try:
    ast = parse('($one #t (#f () . ("5"))) 2; This is a comment.\n 2.5 ( 3 3.5 . "rest" ) \n"4.6" (1) (3 . ()) (4 ()) ')
    ast.view()
    transformed = ToAST().transform(ast)
    transformed.view()
except ParseError as e:
    print e.nice_error_message()
import pdb
pdb.set_trace()

