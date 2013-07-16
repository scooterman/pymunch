from munch.languages import cpp
from munch.targets import cpp as lua_cpp

from copy import copy
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
            overloads[func][0].has_overload = False
            final_functions.append(overloads[func][0])
        else:
            newfun = cpp.cpp_method(func)
            newfun.has_overload = True
            newfun.is_overload = False
            newfun.overloads = {
                'by_arg_count' : [],
                'by_lua_type' : [],
                'by_cpp_type' : []
            }

            newfun.is_constructor =  overloads[func][0].is_constructor

            newfun.parent = cls

            for i, function in enumerate(overloads[func]):
                function.name = '%s_overload_%d' % (function.name, overload_count)
                function.is_overload = True
                function.has_overload = False
                function.orig_name = newfun.name
                overload_count += 1

                if function.is_virtual:
                    newfun.is_virtual = True

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
            
            final_functions.append(newfun)

    #filter every
    final_public = filter(lambda item: type(item) != cpp.cpp_method, cls.public)
    cls.public = final_public + final_functions

lua_context_builder = lua_cpp.CppContextBuilder()


def make_var_identifier(variable):
    variable.identifier = variable.name.replace('::', '_')\
                                       .replace(' ', '')\
                                       .replace('<','_')\
                                       .replace('>', '_')\
                                       .replace(',', '_')

cpp.cpp_qual_type.hooks.append(make_var_identifier)


#preprocessing. Handling overloads for classes and stray functions
@lua_cpp.preprocess("preprocess", 
                    lua_context_builder)
def lua_preprocess(data, context):
    classes = filter(lambda item: type(item) == cpp.cpp_class, data)
    functions = filter(lambda item: type(item) == cpp.cpp_method and item.parent == None, data)
    other = filter(lambda item: type(item) != cpp.cpp_method and type(item) != cpp.cpp_class, data)

    del data[:]

    #resolving overloads
    for item in classes:
        item.identifier_name = item.qualname\
                                        .replace('::', '_')\
                                        .replace(' ', '')\
                                        .replace('<','_')\
                                        .replace('>', '_')\
                                        .replace(',', '_')
        process_functions(item)

    #resolving dependencies
    sorted_classes = []
    class_set = set([])

    previous_count = len(classes)
    iteration = 0

    while classes:
        current = classes.pop(0)
        processed = True
        
        #print 'testing', current.name, current.dependencies
        for dependency in current.dependencies:
            if 'std' in dependency or dependency == current.qualname:
                continue

            #remove this once the generator knows how to get template items
            if '<' in dependency:
                templates = dependency[dependency.find('<') + 1:dependency.find('>')].split(',')
                current.dependencies += templates

            if not dependency in class_set and not iteration == 10:
                #print 'I dont have dependency: ', dependency
                classes.append(current)
                processed = False
                break 

        if processed:
            #print '### added', current.name
            sorted_classes.append(current)
            class_set.add(current.qualname)
            iteration = 0

        if previous_count == len(classes):            
            if iteration == 10:
                raise Exception("Couldn't resolve dependencies for the classes:" + str(classes))
            iteration += 1

        previous_count = len(classes)

    fake_cls = cpp.cpp_class('Fake')
    fake_cls.public = functions

    process_functions(fake_cls)

    data += sorted_classes + fake_cls.public + other

    context.binder_method = cpp.cpp_method('luaopen_gdx',
                returns=cpp.cpp_type('void'),
                attributes=['extern', '"C"'],
                params=[cpp.cpp_variable('L', cpp.cpp_type('lua_State', pointer=True))])
    context.luareg_declarations = []

    context.binder_method.exprs.append('lua_newtable(L)')

def make_binder(orig_class, lua_cls):
    cls_type = cpp.cpp_type('void')
    binder = cpp.cpp_method('bind',
                static=True,
                returns=cls_type,
                params=[cpp.cpp_variable('L', cpp.cpp_type('lua_State', pointer=True))])

    binder.exprs.append('lua_newtable(L)')
    binder.exprs.append('luaL_setfuncs (L, lua_reg_{},0)'.format(orig_class.identifier_name))
    binder.exprs.append('lua_setfield(L, -2, "{}")'.format(orig_class.name))

    return binder

@lua_cpp.translation_initialization("init_classes", 
                        lambda item: type(item) == cpp.cpp_class, 
                    lua_context_builder)
def init_translated_class(orig_class, context):
    assert 'translation' not in orig_class.__dict__

    lua_cls = cpp.cpp_class('lua_munch_' + orig_class.identifier_name)
    orig_class.translation = lua_cls

    luaReg = cpp.cpp_variable_array('lua_reg_' + orig_class.identifier_name, 
                                cpp.cpp_type('constexpr luaL_Reg', static=True))

    logging.debug('baking methods for class: %s : %s' % (orig_class.name ,orig_class.public))
    
    #lua_cls.public.append(make_getter(orig_class))
    
    #we now bake all methods and subclasses from this class, but not preprocess them
    class_ctx = lua_context_builder.bake(orig_class.public, preprocess=False)
    
    for item in class_ctx.translated:
        if item.public:
            lua_cls.public.append(item)
        else:
            lua_cls.protected.append(item)

        if type(item) == cpp.cpp_method and not item.is_constructor and item.public:
            luaReg.expr.append('{ "%s" , lua_munch_%s::%s }' % (item.orig_name, orig_class.identifier_name, item.name))    

    lua_cls.public.append(make_binder(orig_class, lua_cls))

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

    context.binder_method.exprs.append('{}::bind(L)'.format(lua_cls.name))
    
    vardecl = luaReg.define()
    vardecl = vardecl.replace('static', '').replace('constexpr', '')

    context.luareg_declarations.append(vardecl)

    orig_class.translation = lua_cls

#initializing methods. For each method we create a translation for it, and add some lua specific
#variables to it
@lua_cpp.translation_initialization("init_methods", 
                        lambda item: type(item) == cpp.cpp_method, 
                    lua_context_builder)
def init_translated_method(orig_method, context):
    assert 'translation' not in orig_method.__dict__

    logging.debug('entered [init_translated_method] with method:' + repr(orig_method))

    method = cpp.cpp_method('lua_munch_' + orig_method.name,
            static=True, returns= cpp.cpp_type('int'),
            params=[cpp.cpp_variable('L', cpp.cpp_type('lua_State', pointer=True))])
        
    if orig_method.parent:
        method.parent = orig_method.parent.translation

    method.orig_name = orig_method.name

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

    method.return_value = cpp.cpp_return(0)

    #we 'tie' the translated method on the original method
    #so it's easier to work with them without needing to search for them on every callback
    orig_method.translation = method

@lua_cpp.method_translation("overload_arg_count", 
                        lambda orig_method: orig_method.has_overload \
                                            and orig_method.overloads['by_arg_count'],
                        lua_context_builder)
def process_overload_by_arg_count(orig_method, context):
    logging.debug('processing a overload by arg count: %s' + orig_method.name)

    acount = orig_method.overloads['by_arg_count']    
    switch = cpp.cpp_switch('lua_gettop(L)')

    for by_arg_count in acount:
        case = cpp.cpp_case()
        case.expr = len(by_arg_count.parameters)

        params = ['L']
        if by_arg_count.is_virtual:
            params.append('lua_self')

        case.body.append(cpp.cpp_return(cpp.cpp_method_call('lua_munch_' + by_arg_count.name, params=params)))

        switch.exprs.append(case)

        #we bake the overload method and add it back to our context
        other_method = lua_context_builder.bake([by_arg_count], preprocess = False).translated[0]
        other_method.public = False
        context.translated.append(other_method)

        for item in other_method.execution:
            if type(item) == cpp.cpp_method_call:
                item.expr = orig_method.name if not orig_method.parent else 'lua_self->' + orig_method.name
                break

    orig_method.translation.execution.append(switch)

@lua_cpp.method_translation("function_virtual_callback", 
                        lambda orig_method: orig_method.is_virtual
                            and orig_method.parent
                            and type(orig_method.parent) == cpp.cpp_class
                            and not orig_method.is_overload,
                        lua_context_builder)
def process_virtual_function_callback(orig_method, context):
    lua_method = copy(orig_method.translation)    
    lua_method.parameters = orig_method.translation.parameters[:-1]
    
    lua_method.exprs = []
    lua_method.return_value = cpp.cpp_return(cpp.cpp_method_call(lua_method.name, params=['L', 'nullptr']))
    
    orig_method.translation.parent.public.append(lua_method)

@lua_cpp.method_translation("overloaded_function",
                        lambda orig_method: orig_method.has_overload,
                        lua_context_builder)
def process_main_overloaded_function(function, context):
    function.translation.exprs += function.translation.execution

@lua_cpp.method_translation("default_function",
                        lambda orig_method: not orig_method.has_overload,
                        lua_context_builder)
def process_function(function, context):    
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
            cif.body.append('lua_self = static_cast<{}*>(lua_touserdata(L, 1))'.format(function.parent.qualname))

            method.recover.append(cif)
        else:
            method.initialization.append('{0}* lua_self = static_cast<{1}*>(lua_touserdata(L, 1))'.format(function.parent.qualname, function.parent.qualname))

    for parameter in method.transformed_parameters:
        method.recover.append(lua_context_builder.apply_variable_conversion_from_target(parameter, context))

    applied_parameters = []
    #then we add type casting to the original variable type
    for tp, fp in zip(method.transformed_parameters, function.parameters):
        applied_parameters.append(tp.cast(cpp.cpp_static_cast, fp.ctype))

    if function.is_constructor:
        method.execution.append('{0}* lua_self = new {0}({1})'.format(function.parent.qualname,
                                                                      ','.join(map(str,applied_parameters))))
        method.execution.append('lua_pushlightuserdata(L, (void*) lua_self)')
        method.return_value = cpp.cpp_return(1)
    else:    
        #then we call the original method!
        fname = function.name if not function.is_overload else function.orig_name

        method.execution.append(cpp.cpp_method_call(fname if not function.parent else 'lua_self->' + fname, applied_parameters))

        if function.returns != cpp.cpp_type('void'):
            logging.debug('lua_return: translating variable %r to LUA', function.returns)
            #if the function is not void, we recover the method execution
            method_execution = method.execution[0]
            del method.execution[:]

            return_var = cpp.cpp_variable('lua_return', function.returns)

            #create a variable assignment
            method.execution.append(return_var.declare(return_var.assign(method_execution)))

            #push the value to lua
            method.lua_return.append(lua_context_builder.apply_variable_conversion_to_target(return_var, context))
            print 'lua return is', method.lua_return
            #and then change the call function to 1 so LUA knows it has one value to unpack
            method.return_value = cpp.cpp_return(1)

    method.exprs += method.initialization + method.validation + method.recover + method.execution + method.lua_return

    logging.debug("finished translating: %r", method)

def initialize_primitive(ctype, context_builder, lua_type, lua_get, lua_set):
    @lua_cpp.variable_initialization(ctype, 
                             lambda item: True,
                             context_builder)
    def initializer(variable, context):
        if variable.ctype.is_reference() or variable.ctype.is_const():            
            return cpp.cpp_variable(variable.name, variable.ctype.mutate(reference=False, const=False))

        return variable

    @lua_cpp.variable_check(ctype,
                        lambda item: True,
                        context_builder)
    def type_check(variable, context):
        return 'assert(lua_type(L,%d) == %s)' % (variable.index, lua_type)

    @lua_cpp.variable_conversion_from_target_language(ctype,
                    lambda item: True,
                    context_builder)
    def variable_get(variable, context):
        return '%s = %s(L, %d)' % (variable.name, lua_get, variable.index)

    if lua_set:
        @lua_cpp.variable_conversion_to_target_language(ctype,
                        lambda item: True,
                        context_builder)
        def variable_set(variable, context):
            return '%s(L, %s)' %(lua_set, variable.name)

    def variable_dereference(variable, context):
        return variable.name

initialize_primitive(cpp.cpp_type('int'),  lua_context_builder, 'LUA_TNUMBER','luaL_checkinteger','lua_pushinteger')
initialize_primitive(cpp.cpp_type('long'),  lua_context_builder, 'LUA_TNUMBER','luaL_checkinteger','lua_pushinteger')
initialize_primitive(cpp.cpp_type('float'), lua_context_builder, 'LUA_TNUMBER','luaL_checknumber','lua_pushnumber')
initialize_primitive(cpp.cpp_type('double'), lua_context_builder,'LUA_TNUMBER','luaL_checknumber','lua_pushnumber')
initialize_primitive(cpp.cpp_type('bool'), lua_context_builder, 'LUA_TBOOLEAN','lua_toboolean','lua_pushboolean')
initialize_primitive(cpp.cpp_type('char', pointer=True), lua_context_builder, 'LUA_TSTRING','(char*) luaL_checkstring', None)
initialize_primitive(cpp.cpp_type('unsigned char', pointer=True), lua_context_builder, 'LUA_TSTRING','(unsigned char*) luaL_checkstring', None)

initialize_primitive(cpp.cpp_type('char'), lua_context_builder, 'LUA_TSTRING','*luaL_checkstring','lua_pushstring')
cpp.cpp_type('int').spelling += ['unsigned', 'unsigned int']
cpp.cpp_type('long').spelling.append('unsigned long')

initialize_primitive(cpp.cpp_type('basic_string', templates=[cpp.cpp_type('char')]),
                                                lua_context_builder,
                                               'LUA_TSTRING',
                                               'luaL_checkstring',
                                                None)

string = cpp.cpp_type('basic_string', templates=[cpp.cpp_type('char')])

string.spelling.append('std::basic_string<char>')
string.spelling.append('std::string')

@lua_cpp.variable_conversion_to_target_language(cpp.cpp_type('unsigned char', pointer=True),
                             lambda item: True,
                             lua_context_builder)
def uptrchar_to_lua(variable, ctype):
    return 'lua_pushstring(L, (char *) %s)' %( variable.name )

@lua_cpp.variable_conversion_to_target_language(string,
                             lambda item: True,
                             lua_context_builder)
def string_to_lua(variable, ctype):
    return 'lua_pushstring(L, %s.c_str())' %(variable.name)

@lua_cpp.variable_conversion_from_target_language(string,
                             lambda item: True,
                             lua_context_builder)
def string_from_lua(variable, ctype):
    return 'luaL_checkstring(L, %d)' % (variable.index)

@lua_cpp.variable_check(cpp.MUNCH_ANY_TYPE, 
                    lambda item: True,
                    lua_context_builder)
def anytype_type_check(variable, type):
    return 'assert(lua_type(L,%d) == LUA_TLIGHTUSERDATA)' % variable.index

@lua_cpp.variable_initialization(cpp.MUNCH_ANY_TYPE,
                        lambda item: True,
                        lua_context_builder)
def anytype_initializer(variable, ctype):
    #the initialized variable shouldn't carry refs and other stuff, so we bake a new one here
    new_ctype = cpp.cpp_type(variable.ctype.name, pointer=True)    
    return cpp.cpp_variable(variable.name, new_ctype)

@lua_cpp.variable_conversion_from_target_language(cpp.MUNCH_ANY_TYPE,
                    lambda item: True,
                    lua_context_builder)
def anytype_variable_get(variable, ctype):
    var = cpp.cpp_variable('lua_touserdata(L,{})'.format(variable.index), cpp.cpp_type('void', pointer=True))
    return '%s = %s' % (variable.name, var.cast(cpp.cpp_static_cast, variable.ctype.mutate(pointer=True)))

@lua_cpp.variable_conversion_to_target_language(cpp.MUNCH_ANY_TYPE,
                    lambda item: True,
                    lua_context_builder)
def anytype_variable_set(variable, ctype):
    refvar = variable

    if not variable.ctype.is_pointer() and not variable.ctype.is_reference():        
        return 'lua_pushlightuserdata(L, %s)' % (cpp.cpp_cast(cpp.cpp_type('void', pointer=True), 'new {}({})'.format(variable.ctype.name, variable.name)))

    return 'lua_pushlightuserdata(L, %s)' % (refvar.cast(cpp.cpp_cast, cpp.cpp_type('void', pointer=True)))