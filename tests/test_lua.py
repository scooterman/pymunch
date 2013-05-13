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
    assert t_method.name == 'lua_munch_method'

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

def test_method_param_class():
    context = lua.create_context()
    method = cpp.cpp_method('method', 
                params=[cpp.cpp_variable('myvar', cpp.cpp_type('MyTestClass', const=True))])

    var = context.apply_initializer(method.parameters[0])

    assert type(var.ctype.name) == cpp.cpp_qual_type
    assert var.ctype.pointer == True

    context.munch([method])

    assert len(context.translated) == 1

    t_method = context.translated[0]
    
    assert t_method.static
    assert t_method.name == 'lua_munch_method'
    assert t_method.initialization
    assert t_method.initialization[0]

def test_class():
    context = lua.create_context()

    cls = cpp.cpp_class('MyTest')

    method = cpp.cpp_method('method', 
              params=[cpp.cpp_variable('myvar', cpp.cpp_type('MyTestClass', const=True))])

    cls.public.append(method)

    context.munch([cls])

    assert len(context.translated) == 1

    t_cls = context.translated[0]
    
    assert t_cls
    assert t_cls.name == 'lua_munch_MyTest'

def test_class_method_overload():
    context = lua.create_context()

    cls = cpp.cpp_class('MyTest')

    method = cpp.cpp_method('method', 
              params=[cpp.cpp_variable('myvar', cpp.cpp_type('MyTestClass', const=True))])

    method1 = cpp.cpp_method('method', 
              params=[cpp.cpp_variable('myvar', cpp.cpp_type('int', const=True))])
    
    cls.public.append(method)
    method.parent = cls

    cls.public.append(method1)
    method1.parent = cls

    context.munch([cls])

    assert len(context.translated) == 1

    t_cls = context.translated[0]
    
    assert t_cls
    assert t_cls.name == 'lua_munch_MyTest'

def test_class_base():
    context = lua.create_context()

    base = cpp.cpp_class('base')

    bmethod = cpp.cpp_method('base_method', 
              params=[cpp.cpp_variable('int', cpp.cpp_type('int'))])

    base.public.append(bmethod)
    
    bmethod.parent = base

    cls = cpp.cpp_class('MyTest')

    cls.bases.append(base)

    method = cpp.cpp_method('method', 
              params=[cpp.cpp_variable('myvar', cpp.cpp_type('MyTestClass', const=True))])

    method1 = cpp.cpp_method('method', 
              params=[cpp.cpp_variable('myvar', cpp.cpp_type('int', const=True))])
    
    cls.public.append(method)
    method.parent = cls

    cls.public.append(method1)
    method1.parent = cls

    context.munch([base, cls])

    assert len(context.translated) == 2

    t_cls = context.translated[1]
    
    assert t_cls
    assert t_cls.name == 'lua_munch_MyTest'

    print context.translated[0] 
    print t_cls

    assert False