
from munch.targets import cpp
from copy import deepcopy

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

            newfun.is_constructor =  overloads[func][0].is_constructor
            newfun.parent = overloads[func][0].parent

            for i, function in enumerate(overloads[func]):
                function.name = '%s_overload_%d' % (function.name, overload_count)
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

            final_functions.append(newfun)

    #filter every
    final_public = filter(lambda item: type(item) != cpp.cpp_method, cls.public)
    cls.public = final_public + final_functions

def lua_before_init(context, data):
    classes = filter(lambda item: type(item) == cpp.cpp_class, data)
    functions = filter(lambda item: type(item) == cpp.cpp_method, data)
    other = filter(lambda item: type(item) != cpp.cpp_method and type(item) != cpp.cpp_class, data)

    del data[:]

    for item in classes:
        process_functions(item)

    fake_cls = cpp.cpp_class('Fake')
    fake_cls.public = functions

    process_functions(fake_cls)

    data += classes + fake_cls.public + other

def lua_method_translation(context, func_ctx, function): 
    method = cpp.cpp_method('lua_munch_' + function.name,
            static=True, returns=cpp.cpp_type('int'),
            params=[cpp.cpp_variable('L', cpp.cpp_type('lua_State', pointer=True))])

    if function.parent:
        method.parameters.append(cpp.cpp_variable('lua_self', cpp.cpp_type(function.parent.name, pointer=True)))

    if function.is_constructor:
        method.function_name = 'TODO#CONSTRUCTOR'

    #now we embed the default object with a very specific format that will be useful later
    method.initialization = [] # will contain initialization steps
    method.validation = [] # will contain validation steps
    method.recover = [] # will contain the steps to translate the lua arg to a C++ arg
    method.execution = [] # will contain execution steps, i.e, calling the native method
    method.lua_return = [] # will contain the steps to push a value back to lua

    method.return_value = cpp.cpp_return(0)
    
    #then, we have two differences, when the method is overloaded or not
    if function.is_overload:
        stack_init = 1 if not function.is_constructor else 0

        acount = function.overloads['by_arg_count']
        
        if acount:
            switch = cpp.cpp_switch('lua_gettop(L)')
            
            for by_arg_count in acount:
                switch.case_exprs.append(cpp.cpp_method_call(by_arg_count['name']))
                other_method = context.translate_method(by_arg_count)

                for item in other_method.execution:
                    if type(item) == cpp.cpp_method_call:
                        item.expr = function.name if not function.parent else 'lua_self->' + function.name
                        break

                if func_ctx and type(func_ctx) == cpp.cpp_class:
                    func_ctx.public.append(other_method)

            method.execution.append(switch)

        aluatype = function.overloads['by_lua_type']

        if aluatype:        
            cifs = []
            for by_lua_type in aluatype:   
                cand = cpp.cpp_and()           
                for i, param in enumerate(by_lua_type.parameters):
                    cparam = context.get_registered_ctype(param.ctype)

                    cand.exprs.append('lua_type(L, %d) == %s'
                        % (stack_init + i, cparam.lua_type))

                by_lua_type.is_overload = False

                other_method = context.translate_method(by_lua_type)

                for item in other_method.execution:
                    if type(item) == cpp.cpp_method_call:
                        item.expr = function.name if not function.parent else 'lua_self->' + function.name
                        break

                if func_ctx and type(func_ctx) == cpp.cpp_class:
                    func_ctx.public.append(other_method)

                cif = cpp.cpp_if()
                cif.exprs.append(cand)
                ret = cpp.cpp_return(cpp.cpp_method_call('lua_munch_' + by_lua_type.name, params = ['L', 'lua_self']))
                cif.body.append(ret)

                cifs.append(cif)

            def enqueue_ifs(a,b):
                a.cpp_else = b
                return b

            reduce(enqueue_ifs, cifs)

            method.execution.append(cifs[0])

        if func_ctx and type(func_ctx) == cpp.cpp_class:
            lua_method = deepcopy(method)
            lua_method.parameters.pop(-1)

            lua_method.body = []
            lua_method.return_value = cpp.cpp_return(cpp.cpp_method_call(method.name, params=['L', 'nullptr']))
            
            func_ctx.public.append(lua_method)

    else:
        #adding an index value to each positional parameter
        for i, parameter in enumerate(function.parameters):
            parameter.index = i if function.is_constructor else i + 2

        #firstly we add the default initializers for each mapped type
        for parameter in function.parameters:
            method.initialization.append(context.apply_initializer(parameter))
        
        #this additional step will ensure that the amount of parameters is correct
        method.validation.append('assert(lua_gettop(L) == %d)' % (len(function.parameters) + 0 if function.is_constructor else 1))

        #then we add type checking
        for parameter in function.parameters:
            method.validation.append(context.apply_type_check(parameter))

        #then we get the variables from LUA
        if function.parent:
            cif = cpp.cpp_if(['lua_self != nullptr'])
            cif.body.append('lua_self = lua_munch_%s::get(L)' % (function.parent.name))

            method.recover.append(cif)

        for parameter in function.parameters:
            method.recover.append(context.apply_variable_get(parameter))

        applied_parameters = []
        for parameter in function.parameters:
            applied_parameters.append(context.apply_variable_dereference(parameter))

        #then we call the original method!
        method.execution.append(cpp.cpp_method_call(function.name if not function.parent else 'lua_self->' + function.name, applied_parameters))

        if function.returns != cpp.cpp_type('void'):
            method.lua_return.append(context.apply_variable_set(cpp.cpp_variable('return', function.returns)))
            method.return_value = cpp.cpp_return(1)
    
    #now convert to something the cpp translator is waiting, i.e. the body
    method.body += method.initialization + method.validation + method.recover + method.execution + method.lua_return

    return method

def lua_class_translation(context, class_def):
    lua_cls = cpp.cpp_class('lua_munch_' + class_def.name)

    luaReg = cpp.cpp_variable_array('lua_reg_' + class_def.name, 
                                cpp.cpp_type('luaL_Reg', static=True))

    for item in class_def.public:
        generated_method = context.translate_method(item, lua_cls)

        lua_cls.public.append(generated_method)

        if type(item) == cpp.cpp_method:
            luaReg.expr.append('{ "%s" , lua_munch_%s::lua_munch_%s }' % (item.name, class_def.name, item.name)) 

    #the base methods are shims that only retrieve the self and pass it down to the
    #base class
    for base in class_def.bases:
        for item in base.public:
            if type(item) != cpp.cpp_method:
                continue

            method = cpp.cpp_method('lua_munch_' + item.name,
                static=True, returns=cpp.cpp_type('int'),
                params=[cpp.cpp_variable('L', cpp.cpp_type('lua_State', pointer=True))])

            if item.parent:
                item.parameters.append(cpp.cpp_variable('lua_self', cpp.cpp_type(item.parent.name, pointer=True)))
                method.body.append('%s* lua_self = lua_munch_%s::get(L)' % (class_def.name, class_def.name))

            method.body.append(cpp.cpp_return(cpp.cpp_method_call('lua_munch_%s::lua_munch_%s' % (item.parent.name, item.name), params=['L', 'lua_self'])))

            lua_cls.public.append(method)

            luaReg.expr.append('{ "%s" , lua_munch_%s::lua_munch_%s }' % (item.name, class_def.name, item.name))             

    luaReg.expr.append('{ 0, 0 }')

    lua_cls.public.append(luaReg)

    return lua_cls

def initialize_primitive(ctype, lua_type, lua_get, lua_set):
    def initializer(variable, ctype):
        return variable

    def type_check(variable, ctype):
        return 'assert(lua_type(L,%d) == %s)' % (variable.index, lua_type)

    def variable_get(variable, ctype):
        return '%s = %s(L, %d)' % (variable.name, lua_get, variable.index)

    def variable_set(variable, ctype):
        return '%s(L, %s)' %(variable.name)

    def variable_dereference(variable, ctype):
        return variable.name

    ctype.initializer = initializer
    ctype.type_check = type_check
    ctype.variable_get = variable_get
    ctype.variable_set = variable_set
    ctype.variable_dereference = variable_dereference
    ctype.lua_type = lua_type

    return ctype

def anytype_type_check(variable, type):
    return 'assert(lua_type(L,%d) == LUA_TUSERDATA)' % variable.index

def anytype_initializer(variable, ctype):
    return cpp.cpp_variable(variable.name, cpp.cpp_type(variable.ctype, pointer=True))

def anytype_variable_get(variable, ctype):
    return '%s = lua_munch_%s::get(L)' % (variable.name, variable.ctype.name)

def anytype_variable_set(variable, ctype):
    return 'TODODODODODOD'

def anytype_variable_dereference(variable, ctype):
    return cpp.cpp_dereference(variable.name)

def create_context():
    context = cpp.CppContext()
    context.before_init.append(lua_before_init)

    context.register_ctype(initialize_primitive(cpp.cpp_type('int'),  'LUA_TNUMBER','luaL_checkinteger','lua_pushnumber'))
    context.register_ctype(initialize_primitive(cpp.cpp_type('float'),'LUA_TNUMBER','luaL_checknumber','lua_pushnumber'))
    context.register_ctype(initialize_primitive(cpp.cpp_type('double'),'LUA_TNUMBER','luaL_checknumber','lua_pushnumber'))
    context.register_ctype(initialize_primitive(cpp.cpp_type('bool'), 'LUA_TBOOL','lua_toboolean','lua_pushboolean'))
    context.register_ctype(initialize_primitive(cpp.cpp_type('char', pointer=True), 'LUA_TSTRING','luaL_checknumber','lua_pushnumber'))
    
    #we receiva strings as an char pointer
    string = initialize_primitive(cpp.cpp_type('basic_string', templates=[cpp.cpp_type('char')]),
                                               'LUA_TSTRING',
                                               'luaL_checknumber',
                                               'lua_pushnumber')

    context.register_ctype(string)

    string.initializer = lambda variable, ctype:\
        cpp.cpp_variable(variable.name, cpp.cpp_type('char', pointer=True))
    
    context.MUNCH_ANY_TYPE.type_check = anytype_type_check
    context.MUNCH_ANY_TYPE.initializer = anytype_initializer
    context.MUNCH_ANY_TYPE.variable_get = anytype_variable_get
    context.MUNCH_ANY_TYPE.variable_set = anytype_variable_set
    context.MUNCH_ANY_TYPE.variable_dereference = anytype_variable_dereference
    context.MUNCH_ANY_TYPE.lua_type = 'LUA_TUSERDATA'

    #setting our method translation routine
    context.method_translation = (lua_method_translation)
    context.class_translation = (lua_class_translation)

    return context
