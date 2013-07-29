# encoding: utf-8
from munch.languages.cpp import serializer
from munch.languages.cpp.ast import *

serializer.CppSerializerVisitor.ident = '·'
serializer.CppSerializerVisitor.ident_block = 1

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

    assert result == 'a·=·10'

def test_empty_block():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block()
    result = visitor.parse(block)

    assert result == ''

def test_block_oneliner():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block(cpp_assignment('x', '22.3f'))

    result = visitor.parse(block)
    
    assert result == 'x·=·22.3f;'

def test_block_multiline():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block(cpp_assignment('x', '22.3f'), 
                      cpp_assignment('y', '33'),
                      cpp_assignment('x', False))

    result = visitor.parse(block)

    assert result == 'x·=·22.3f;\ny·=·33;\nx·=·false;'

def test_scope():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block(scoped=True)
    result = visitor.parse(block)

    assert result == '{}'

def test_scope_multiline():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block(cpp_assignment('coke', '2'), scoped=True)
    
    result = visitor.parse(block)
    
    assert result == '{\n·coke·=·2;\n}'  

def test_cpp_if():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_if(cpp_expr_list(True))

    result = visitor.parse(block)

    assert result == 'if (true) {}'      

def test_cpp_if_scope():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_block(cpp_if(cpp_expr(True)), scoped=True)

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
    block = cpp_case(cpp_expr(10), cpp_assignment('a', 100), cpp_break())

    result = visitor.parse(block)
    assert result == 'case 10:\n·a·=·100;\n·break;'

def test_case_scope():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_case(cpp_expr(10), cpp_assignment('a', 100), cpp_break(), scoped=True)

    result = visitor.parse(block)
    assert result == 'case 10:{\n··a·=·100;\n··break;\n}'

def test_case_default():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_default(cpp_assignment('a', 100), cpp_break())

    result = visitor.parse(block)

    assert result == 'default:\n·a·=·100;\n·break;'

def test_switch():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_switch('a', cpp_case(10, cpp_block(cpp_assignment('a', 100), cpp_break())))

    result = visitor.parse(block)

    assert result == 'switch(a){\n·case 10:\n··a·=·100;\n··break;\n}'

def test_for():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_for(cpp_expr('a = 0'), 'a < 100', 'a++', cpp_expr('printf("hi mom\\n")'))

    result = visitor.parse(block)

    assert result == 'for(a = 0;a < 100;a++)\n·printf("hi mom\\n");'

def test_for_scoped():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_for(cpp_expr('a = 0'), 'a < 100', 'a++', cpp_expr('printf("hi mom\\n")'), scoped=True)

    result = visitor.parse(block)

    assert result == 'for(a = 0;a < 100;a++){\n·printf("hi mom\\n");\n}'

def test_qualtype_1():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_qual_type('int')

    result = visitor.parse(block)

    assert result == 'int'

def test_qualtype_2():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_qual_type('int', const=True)

    result = visitor.parse(block)

    assert result == 'const int'

def test_qualtype_3():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_qual_type('int', static=True)

    result = visitor.parse(block)

    assert result == 'static int'

def test_qualtype_4():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_qual_type('int', pointer=True)

    result = visitor.parse(block)

    assert result == 'int*'

def test_qualtype_5():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_qual_type('int', reference=True)

    result = visitor.parse(block)

    assert result == 'int&'

def test_qualtype_6():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_qual_type('int', static= True, reference=True)

    result = visitor.parse(block)

    assert result == 'static int&'

def test_qualtype_7():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_qual_type('int', const=True, static= True, reference=True)

    result = visitor.parse(block)

    assert result == 'static const int&'

def test_qualtype_8():
    visitor = serializer.CppSerializerVisitor()
    block = cpp_qual_type('int')
    block.parent = cpp_expr('test')

    result = visitor.parse(block, qualified=True)

    assert result == 'test::int'

if __name__ == '__main__':
    g = globals()
    for func in filter(lambda functions: 'test' in functions, globals()):
        print 'testing:', func
        g[func]()
