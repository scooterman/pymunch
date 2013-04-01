from munch.targets import cpp
from munch.conversor import lua


def test_context_initialization():
    context = lua.create_context()

    cint = cpp.cpp_type('int')
    assert context.get_ctype(cint).initializer({'name' : 'test'}, cint)

def test_method_1():
    context = lua.create_context()

    method = cpp.cpp_method('method')

    context.munch([method])

    assert len(context.translated) == 1

    t_method = context.translated[0]
    
    assert t_method.static
    assert t_method.name == 'method'

    assert not t_method.lua_return

def test_method_return():  
    context = lua.create_context()  
    method = cpp.cpp_method('method', returns=cpp.cpp_type('int'), return_value = 10)

    context.munch([method])    
    assert len(context.translated) == 1
    t_method = context.translated[0]
    
    assert t_method.static
    assert t_method.name == 'lua_munch_method'

    assert t_method.lua_return

def test_method_param_lua_primitives():  
    context = lua.create_context()  
    method = cpp.cpp_method('method', 
                params=[cpp.cpp_variable('myvar', cpp.cpp_type('int'))])

    context.munch([method])    
    assert len(context.translated) == 1
    t_method = context.translated[0]
    
    assert t_method.static
    assert t_method.name == 'lua_munch_method'
    assert t_method.initialization
    assert t_method.initialization[0]

    assert t_method.initialization[0] ==  method.parameters[0]

    print t_method

    assert False
