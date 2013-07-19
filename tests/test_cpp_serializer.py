from munch.languages.cpp import serializer
from munch.languages.cpp.ast import *


def test_expr():
    visitor = serializer.CppSerializerVisitor()
    expr = cpp_expr('50')
    result = visitor.parse(expr)

    assert result == '50'

def test_assignment():
    visitor = serializer.CppSerializerVisitor()
    assignment = cpp_assignment('a', 10)
    result = visitor.parse(assignment)

    assert result == 'a = 10'

def test_empty_block():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block()
    result = visitor.parse(block)

    assert result == ''

def test_block_oneliner():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block([cpp_assignment('x', '22.3f')])
    result = visitor.parse(block)

    assert result == 'x = 22.3f;'

def test_block_multiline():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block([cpp_assignment('x', '22.3f'), cpp_assignment('y', '33'), cpp_assignment('x', False)])
    result = visitor.parse(block)

    assert result == 'x = 22.3f;\ny = 33;\nx = false;'

def test_scope():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_scope()
    result = visitor.parse(block)

    assert result == '{\n}'

def test_scope_multiline():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_scope([cpp_assignment('coke', '2')])
    result = visitor.parse(block)

    assert result == '{\n  coke = 2;\n}'  

def test_cpp_if():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_if([cpp_expr(True)])

    result = visitor.parse(block)

    assert result == 'if (true) {\n}'      

def test_cpp_if_scope():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_scope([cpp_if([cpp_expr(True)])])

    result = visitor.parse(block)

    print result
    assert result == 'if (true) {\n}'  

if __name__ == '__main__':
    test_expr()
    test_assignment()
    test_empty_block()
    test_block_oneliner()
    test_block_multiline()
    test_scope()
    test_scope_multiline()
    test_cpp_if()
    test_cpp_if_scope()