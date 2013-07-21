# encoding: utf-8
from munch.languages.cpp import serializer
from munch.languages.cpp.ast import *

serializer.CppSerializerVisitor.ident = '·'

def test_expr():
    visitor = serializer.CppSerializerVisitor()
    expr = cpp_expr('50')
    result = visitor.parse(expr)

    assert result == '50'

def test_nested_expr():
    visitor = serializer.CppSerializerVisitor()
    expr = cpp_expr(cpp_expr('50'))
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
    block = cpp_block(cpp_assignment('x', '22.3f'))
    result = visitor.parse(block)

    assert result == 'x = 22.3f;'

def test_block_multiline():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block(cpp_assignment('x', '22.3f'), 
                      cpp_assignment('y', '33'),
                      cpp_assignment('x', False))
    result = visitor.parse(block)

    assert result == 'x = 22.3f;\ny = 33;\nx = false;'

def test_scope():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_scope()
    result = visitor.parse(block)

    assert result == '{}'

def test_scope_multiline():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_scope(cpp_assignment('coke', '2'))
    result = visitor.parse(block)

    assert result == '{\n·coke = 2;\n}'  

def test_cpp_if():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_if(cpp_expr_list(True))

    result = visitor.parse(block)

    assert result == 'if (true) {}'      

def test_cpp_if_scope():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_scope(cpp_if(cpp_expr(True)))

    result = visitor.parse(block)

    assert result == '{\n·if (true) {}\n}'  

def test_cpp_indirection():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_indirection(cpp_expr('a'))

    result = visitor.parse(block)

    assert result == '*(a)'

def test_cpp_indirection_1():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_indirection(cpp_expr(cpp_indirection(cpp_expr('a'))))

    result = visitor.parse(block)

    assert result == '*(*(a))'

def test_cpp_reference():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_reference(cpp_expr('a'))

    result = visitor.parse(block)

    assert result == '&(a)'

def test_cpp_reference_1():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_reference(cpp_expr(cpp_reference(cpp_expr('a'))))

    result = visitor.parse(block)

    assert result == '&(&(a))'

def test_cpp_and():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_and(cpp_expr('a'), cpp_expr(True))

    result = visitor.parse(block)

    assert result == '(a && true)'

def test_cpp_and_1():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_and(cpp_expr(True))

    result = visitor.parse(block)

    assert result == '(true)'

def test_cpp_and_2():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_and(cpp_expr('a'), cpp_expr(True), cpp_expr(False))

    result = visitor.parse(block)

    assert result == '(a && true && false)'

def test_cpp_or():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_or(cpp_expr('a'), cpp_expr(True))

    result = visitor.parse(block)

    assert result == '(a || true)'

def test_cpp_or_1():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_or(cpp_expr(True))

    result = visitor.parse(block)

    assert result == '(true)'

def test_cpp_or_2():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_or(cpp_expr('a'), cpp_expr(True), cpp_expr(False))

    result = visitor.parse(block)

    assert result == '(a || true || false)'

def test_return():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_return(cpp_expr('a'))

    result = visitor.parse(block)

    assert result == 'return a'

def test_return_1():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_return(cpp_or('a', True))

    result = visitor.parse(block)

    assert result == 'return (a || true)'

def test_case():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_case(cpp_expr(10), cpp_block(cpp_assignment('a', 100), cpp_break()))

    result = visitor.parse(block)
    
    assert result == 'case 10:\n·a = 100;\n·break;'

def test_case_scope():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_case(cpp_expr(10), cpp_scope(cpp_assignment('a', 100), cpp_break()))

    result = visitor.parse(block)

    assert result == 'case 10:{\n··a = 100;\n··break;\n}'

def test_case_default():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_default(cpp_block(cpp_assignment('a', 100), cpp_break()))

    result = visitor.parse(block)

    assert result == 'default:\n·a = 100;\n·break;'

def test_switch():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_switch('a', cpp_case(10, cpp_block(cpp_assignment('a', 100), cpp_break())))

    result = visitor.parse(block)
    print result
    assert result == 'switch(a){\n'


if __name__ == '__main__':
    # test_expr()
    # test_nested_expr()
    # test_assignment()
    # test_empty_block()
    # test_block_oneliner()
    # test_block_multiline()
    # test_scope()
    # test_scope_multiline()
    # test_cpp_if()
    # test_cpp_if_scope()
    # test_cpp_indirection_1()
    # test_cpp_indirection()
    # test_cpp_reference()
    # test_cpp_reference_1()
    # test_cpp_and()
    # test_cpp_and_1()
    # test_cpp_and_2()
    # test_cpp_or()
    # test_cpp_or_1()
    # test_cpp_or_2()
    # test_return()
    # test_return_1()
    # test_case()
    # test_case_scope()
    # test_case_default()
    test_switch()

    # PAREI: remover o tipo scoped e converter para uma flag