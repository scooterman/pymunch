from munch.targets import cpp
from copy import deepcopy
import logging

def is_basic(t):
    return t.name == 'int' or t.name == 'float' or t.name == 'basic_string' \
          or t.name == 'bool' or t.name == 'char'

#this function will
def process_functions(cls):
    overloads = {}
    
    for item in cls.public:
        if type(item) == cpp.cpp_method:
            if item.name in overloads:
                overloads[item.name].append(item)
            else:
                overloads[item.name] = [item]

    final_functions = []

    overload_count = 0

    for func in overloads:
        #if there is only one function with this name, it's not an overload it safely
        if len(overloads[func]) == 1:
            overloads[func][0].is_overload = False
            final_functions.append(overloads[func][0])
        else:
            newfun = cpp.cpp_method(func)
            newfun.is_overload = True
            newfun.overloads = {
                'by_arg_count' : [],
                'by_lua_type' : [],
                'by_cpp_type' : []
            }

            newfun.is_virtual = overloads[func][0].is_virtual
            newfun.is_constructor =  overloads[func][0].is_constructor

            newfun.parent = cls

            for i, function in enumerate(overloads[func]):
                function.name = '%s_overload_%d' % (function.name, overload_count)
                function.is_overload = False
                overload_count += 1

                #resolving functions that can be deduced by the count of it's arguments    
                same_qnt = False
                
                for other_f in  overloads[func]:

                    if other_f == function: continue

                    if len(function.parameters) == len(other_f.parameters):
                        same_qnt = True
                        break

                if not same_qnt:
                    newfun.overloads['by_arg_count'].append(function)
                    continue

                #resolving functions that can be deduced by the type of it's lua arguments
                for other_f in overloads[func]:
                    if other_f == function: continue

                    same_basic_types = False

                    for a,b in zip(function.parameters, other_f.parameters):
                        if a.ctype == b.ctype and not is_basic(a):
                            same_basic_types = True
                            break

                    if same_basic_types:
                        break

                if not same_basic_types:
                    newfun.overloads['by_lua_type'].append(function)
                    continue

                newfun.overloads['by_cpp_type'].append(function)

            print repr(newfun), newfun.is_overload
            final_functions.append(newfun)

    #filter every
    final_public = filter(lambda item: type(item) != cpp.cpp_method, cls.public)
    cls.public = final_public + final_functions

    print cls.public


lua_context_builder = cpp.CppContextBuilder()

#preprocessing. Handling overloads for classes and stray functions
@cpp.preprocess("preprocess", 
                    lua_context_builder)
def lua_preprocess(data, context):
    classes = filter(lambda item: type(item) == cpp.cpp_class, data)
    functions = filter(lambda item: type(item) == cpp.cpp_method and item.parent == None, data)
    other = filter(lambda item: type(item) != cpp.cpp_method and type(item) != cpp.cpp_class, data)

    del data[:]

    for item in classes:
        item.identifier_name = item.qualname.replace('::', '_')
        process_functions(item)

    fake_cls = cpp.cpp_class('Fake')
    fake_cls.public = functions

    process_functions(fake_cls)

    data += classes + fake_cls.public + other

def make_getter(lua_cls):
    getter_str = '''static {ClassPtr}* get(lua_State* L, unsigned index) {{
        assert( lua_islightuserdata(L, index));
        return static_cast<{ClassPtr}*>(lua_touserdata(L, index));
}}'''

    return getter_str.format(ClassPtr=lua_cls.qualname)

@cpp.translation_initialization("init_classes", 
                        lambda item: type(item) == cpp.cpp_class, 
                    lua_context_builder)
def init_translated_class(orig_class, context):
    assert 'translation' not in orig_class.__dict__

    lua_cls = cpp.cpp_class('lua_munch_' + orig_class.identifier_name)

    luaReg = cpp.cpp_variable_array('lua_reg_' + orig_class.identifier_name, 
                                cpp.cpp_type('constexpr luaL_Reg', static=True))

    logging.debug('baking methods for class: %s : %s' % (orig_class.name ,orig_class.public))
    
    #we now bake all methods and subclasses from this class, but not preprocess them
    class_ctx = lua_context_builder.bake(orig_class.public, preprocess=False)

    for item in class_ctx.translated:
        if item.public:
            lua_cls.public.append(item)
        else:
            lua_cls.protected.append(item)

        if type(item) == cpp.cpp_method and not item.is_constructor and item.public:
            luaReg.expr.append('{ "%s" , lua_munch_%s::%s }' % (item.orig_name, orig_class.identifier_name, item.name)) 

    lua_cls.protected.append(make_getter(orig_class))

    #the base methods are shims that only retrieve it's self and pass it down to the
    #base class
    for base in orig_class.bases:
        for item in base.public:
            if type(item) != cpp.cpp_method:
                continue

            method = cpp.cpp_method('lua_munch_' + item.name,
                static=True, returns=cpp.cpp_type('int'),
                params=[cpp.cpp_variable('L', cpp.cpp_type('lua_State', pointer=True))])

            if item.parent:
                item.parameters.append(cpp.cpp_variable('lua_self', cpp.cpp_type(item.parent.name, pointer=True)))
                method.exprs.append('%s* lua_self = lua_munch_%s::get(L, %d)' % (orig_class.qualname, orig_class.identifier_name, 1))

            method.exprs.append(cpp.cpp_return(cpp.cpp_method_call('lua_munch_%s::lua_munch_%s' % (item.parent.name, item.name), params=['L', 'lua_self'])))

            lua_cls.public.append(method)

            if not item.is_constructor:
                luaReg.expr.append('{ "%s" , lua_munch_%s::lua_munch_%s }' % (item.name, orig_class.name, item.name))             

    luaReg.expr.append('{ 0, 0 }')

    lua_cls.public.append(luaReg)
    orig_class.translation = lua_cls


#initializing methods. For each method we create a translation for it, and add some lua specific
#variables to it
@cpp.translation_initialization("init_methods", 
                        lambda item: type(item) == cpp.cpp_method, 
                    lua_context_builder)
def init_translated_method(orig_method, context):
    assert 'translation' not in orig_method.__dict__

    logging.debug('entered [init_translated_method] with method:' + repr(orig_method))

    method = cpp.cpp_method('lua_munch_' + orig_method.name,
            static=True, returns= cpp.cpp_type('int'),
            params=[cpp.cpp_variable('L', cpp.cpp_type('lua_State', pointer=True))])
    
    method.orig_name = orig_method.name

    if orig_method.is_virtual:
        method.parameters.append(cpp.cpp_type(orig_method.parent.qualname, pointer= True))

    method.public = True

    #now we embed the default object with a very specific format that will be useful later
    method.initialization = [] # will contain initialization steps
    method.validation = [] # will contain validation steps
    method.recover = [] # will contain the steps to translate the lua arg to a C++ arg
    method.execution = [] # will contain execution steps, i.e, calling the native method
    method.lua_return = [] # will contain the steps to push a value back to lua

    if not 'is_overload' in method.__dict__:
        method.is_overload = False

    if orig_method.parent and orig_method.is_virtual:
        method.parameters.append(cpp.cpp_variable('lua_self', cpp.cpp_type(orig_method.parent.qualname, pointer=True)))

    if orig_method.is_constructor:
        method.name = 'lua_munch_' + orig_method.parent.name + '_constructor'

    method.return_value = cpp.cpp_return(0)

    #we 'tie' the translated method on the original method
    #so it's easier to work with them without needing to search for them on every callback
    orig_method.translation = method

@cpp.method_translation("default_function",
                        lambda orig_method: True,
                        lua_context_builder)
def process_function(function, context):
    logging.debug('translating:' + repr(function))
    method = function.translation

    #will hold the real variables the method uses, after initialization
    method.transformed_parameters = []

    #adding an index value to each positional parameter
    #firstly we add the default initializers for each mapped type
    for i, parameter in enumerate(function.parameters):
        overriden_variable = lua_context_builder.apply_variable_initialization(parameter, context)
        overriden_variable.index = parameter.index = i if function.is_constructor else i + 2              
        
        method.transformed_parameters.append(overriden_variable)
        method.initialization.append(overriden_variable)
    
    #this additional step will ensure that the amount of parameters is correct
    method.validation.append('assert(lua_gettop(L) == %d)' % (len(function.parameters) + (0 if function.is_constructor else 1)))

    #then we add type checking
    for parameter in method.transformed_parameters:
        method.validation.append(lua_context_builder.apply_variable_check(parameter, context))

    #then we get the variables from LUA
    if function.parent and not function.is_constructor:
        if function.is_virtual:
            cif = cpp.cpp_if(['lua_self != nullptr'])
            cif.body.append('lua_self = lua_munch_%s::get(L, 1)' % (function.parent.identifier_name))

            method.recover.append(cif)
        else:
            method.initialization.append('{0}* lua_self = lua_munch_{1}::get(L, 1)'.format(function.parent.qualname, function.parent.identifier_name))

    for parameter in function.parameters:
        method.recover.append(lua_context_builder.apply_variable_conversion_from_target(parameter, context))

    applied_parameters = []
    #then we add type casting to the original variable type
    for tp, fp in zip(method.transformed_parameters, function.parameters):
        applied_parameters.append(tp.cast(cpp.cpp_static_cast, fp.ctype))

    if function.is_constructor:
        method.execution.append('{0}* lua_self = new {0}({1})'.format(function.parent.qualname,
                                                                      ''.join([param.name for param in function.parameters])))
        method.execution.append('lua_pushlightuserdata(L, (void*) lua_self)')
        method.return_value = cpp.cpp_return(1)
    else:    
        #then we call the original method!
        method.execution.append(cpp.cpp_method_call(function.name if not function.parent else 'lua_self->' + function.name, applied_parameters))

        if function.returns != cpp.cpp_type('void'):
            #if the function is not void, we recover the method execution
            method_execution = method.execution[0]

            #create a variable assignment
            assign = cpp.cpp_assignment(cpp.cpp_variable('lua_return', function.returns), method_execution)

            #put id back to the execution
            method.execution[0] = assign

            #push the value to lua
            method.lua_return.append(lua_context_builder.apply_variable_conversion_to_target(assign.expr_a, context))

            #and then change the call function to 1 so LUA knows it has one value to unpack
            method.return_value = cpp.cpp_return(1)

    method.exprs += method.initialization + method.validation + method.recover + method.execution + method.lua_return


def initialize_primitive(ctype, context_builder, lua_type, lua_get, lua_set):
    @cpp.variable_initialization(ctype, 
                             lambda item: True,
                             context_builder)
    def initializer(variable, context):
        if variable.ctype.is_reference():
            return cpp.cpp_variable(variable.name, variable.ctype.mutate(reference=False))

        return variable

    @cpp.variable_check(ctype,
                        lambda item: True,
                        context_builder)
    def type_check(variable, context):
        return 'assert(lua_type(L,%d) == %s)' % (variable.index, lua_type)

    @cpp.variable_conversion_from_target_language(ctype,
                    lambda item: True,
                    context_builder)
    def variable_get(variable, context):
        return '%s = %s(L, %d)' % (variable.name, lua_get, variable.index)

    @cpp.variable_conversion_to_target_language(ctype,
                    lambda item: True,
                    context_builder)
    def variable_set(variable, context):
        return '%s(L, %s)' %(lua_set, variable.name)

    def variable_dereference(variable, context):
        return variable.name

initialize_primitive(cpp.cpp_type('int'),  lua_context_builder, 'LUA_TNUMBER','luaL_checkinteger','lua_pushnumber')
initialize_primitive(cpp.cpp_type('float'), lua_context_builder, 'LUA_TNUMBER','luaL_checknumber','lua_pushnumber')
initialize_primitive(cpp.cpp_type('double'), lua_context_builder,'LUA_TNUMBER','luaL_checknumber','lua_pushnumber')
initialize_primitive(cpp.cpp_type('bool'), lua_context_builder, 'LUA_TBOOL','lua_toboolean','lua_pushboolean')
initialize_primitive(cpp.cpp_type('char', pointer=True), lua_context_builder, 'LUA_TSTRING','luaL_checknumber','lua_pushnumber')

initialize_primitive(cpp.cpp_type('basic_string', templates=[cpp.cpp_type('char')]),
                                                lua_context_builder,
                                               'LUA_TSTRING',
                                               'luaL_checknumber',
                                               'lua_pushnumber')

#overrinding the default variable initialization for std::string
@cpp.variable_initialization(cpp.cpp_type('basic_string', templates=[cpp.cpp_type('char')]),
                             lambda item: True,
                             lua_context_builder)
def string_initializer(variable, ctype):
    return cpp.cpp_variable(variable.name, cpp.cpp_type('char', pointer=True))

@cpp.variable_check(cpp.MUNCH_ANY_TYPE, 
                    lambda item: True,
                    lua_context_builder)
def anytype_type_check(variable, type):
    return 'assert(lua_type(L,%d) == LUA_TLIGHTUSERDATA)' % variable.index

@cpp.variable_initialization(cpp.MUNCH_ANY_TYPE,
                        lambda item: True,
                        lua_context_builder)
def anytype_initializer(variable, ctype):
    #the initialized variable shouldn't carry refs and other stuff, so we bake a new one here
    new_ctype = cpp.cpp_type(variable.ctype.name, pointer=True)    
    return cpp.cpp_variable(variable.name, new_ctype)

@cpp.variable_conversion_from_target_language(cpp.MUNCH_ANY_TYPE,
                    lambda item: True,
                    lua_context_builder)
def anytype_variable_get(variable, ctype):
    return '%s = lua_munch_%s::get(L, %d)' % (variable.name, variable.ctype.name.replace('::','_'), variable.index)

@cpp.variable_conversion_to_target_language(cpp.MUNCH_ANY_TYPE,
                    lambda item: True,
                    lua_context_builder)
def anytype_variable_set(variable, ctype):
    return 'lua_pushlightuserdata(L, %s)' % (variable.cast(cpp.cpp_static_cast, cpp.cpp_type('void', pointer=True)))

def anytype_variable_dereference(variable, ctype):
    return cpp.cpp_dereference(variable.name)