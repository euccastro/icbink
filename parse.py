from rpython.rlib.parsing.ebnfparse import parse_ebnf, make_parse_function
from rpython.rlib.parsing.tree import Symbol, Nonterminal, RPythonVisitor
from rpython.rlib.parsing.parsing import ParseError

grammar = r"""
    STRING: "\"([^\"]|\\\")*\"";
    NUMBER: "\-?(0|[1-9][0-9]*)(\.[0-9]+)?([eE][\+\-]?[0-9]+)?";
    IGNORE: " |\n|;[^\n]*\n";
    sequence: expr >sequence< | expr;
    expr: <list> | <dotted_list> | <atom>;
    list: ["("] >sequence< [")"];
    dotted_list: ["("] >sequence< ["."] expr [")"];
    atom: <STRING> | <NUMBER> | <nil>;
    nil: ["("] [")"];
    """

regexs, rules, ToAST = parse_ebnf(grammar)
parse = make_parse_function(regexs, rules, eof=True)

try:
    ast = parse('(1 "one" (6 () . ("5"))) 2; This is a comment.\n 2.5 ( 3 3.5 . "rest" ) \n"4.6" (1) (3 . ()) (4 ()) ')
    ast.view()
    transformed = ToAST().transform(ast)
    transformed.view()
except ParseError as e:
    print e.nice_error_message()
import pdb
pdb.set_trace()

