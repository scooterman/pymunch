
from munch.targets import cpp

def is_basic(t):
    return t.name == 'int' or t.name == 'float' or t.name == 'basic_string' \
          or t.name == 'bool' or t.name == 'char'

#this function will
def process_functions(cls):
    overloads = {}
    
    for func in cls['functions']:
        if func['name'] in overloads:
            overloads[func['name']].append(func)
        else:
            overloads[func['name']] = [func]

    final_functions = []

    overload_count = 0

    for func in overloads:
        #if there is only one function with this name, it's not an overload it safely
        if len(overloads[func]) == 1:
            overloads[func][0]['is_overload'] = False
            final_functions.append(overloads[func][0])
        else:
            newfun = {
                'name' : func,
                'is_overload' : True,
                'func_type' : overloads[func][0]['func_type'],
                'overloads' : {
                    'by_arg_count' : [],
                    'by_lua_type' : [],
                    'by_cpp_type' : []
                }
            }

            for i, function in enumerate(overloads[func]):
                function['name'] = 'luacpp_%s_overload_%d' % (function['name'], overload_count)
                overload_count += 1

                #resolving functions that can be deduced by the count of it's arguments    
                same_qnt = False
                for other_f in  overloads[func]:
                    if other_f == function: continue

                    if len(function['params']) == len(other_f['params']):
                        same_qnt = True
                        break

                if not same_qnt:
                    newfun['overloads']['by_arg_count'].append(function)
                    continue

                #resolving functions that can be deduced by the type of it's lua arguments
                for other_f in overloads[func]:
                    if other_f == function: continue

                    same_basic_types = False
                    
                    for a,b in zip(function['params'], other_f['params']):
                        if a['type'] == b['type'] and not is_basic(a):
                            same_basic_types = True
                            break

                    if same_basic_types:
                        break

                if not same_basic_types:
                    newfun['overloads']['by_lua_type'].append(function)
                    continue

                newfun['overloads']['by_cpp_type'].append(function)

            final_functions.append(newfun)

    cls['functions'] = final_functions

def lua_before_init(context, data):
    for item in data:
        if type(item) == cpp.cpp_class:
            process_functions(item)    

def lua_method_translation(context, function): 
    method = cpp.cpp_method('lua_munch_' + function.name,
            static=True, returns=cpp.cpp_type('int'),
            params=[cpp.cpp_variable('L', cpp.cpp_type('lua_State', pointer=True))])

    if function.is_constructor:
        method.function_name = 'TODO#CONSTRUCTOR'

    #now we embed the default object with a very specific format that will be useful later
    method.initialization = [] # will contain initialization steps
    method.validation = [] # will contain validation steps
    method.recover = [] # will contain the steps to translate the lua arg to a C++ arg
    method.execution = [] # will contain execution steps, i.e, calling the native method
    method.lua_return = [] # will contain the steps to push a value back to lua

    method.return_value = cpp.cpp_return(0)
    
    #then, we have tho differences, when the method is overloaded or not
    if 'is_overload' in function.context and function.context['is_overload']:
        stack_init = 1 if not function.is_constructor else 0

        acount = function.context['overloads']['by_arg_count']
        
        if acount:
            switch = cpp.cpp_switch('lua_gettop(L)')
            
            for by_arg_count in acount:
                switch.case_exprs.append(cpp.cpp_method_call(by_arg_count['name']))
                context.translate_method(by_arg_count)

            method.execution.append(switch)

        aluatype = function.context['overloads']['by_lua_type']

        if aluatype:        
            current = None
            for by_lua_type in aluatype:   
                cand = cpp.cpp_and()           
                for param in by_lua_type['params']:
                    cand.append('lua_type(L, %d) == %s'
                        % (stack_init, context.resolve_lua_type(by_lua_type['type'])))

                other_method = context.translate(by_lua_type)

                #we can remove the original validation, saving some cycles
                other_method.validation = None

                cif = cpp.cpp_if()
                current.expr.append(cand)
                current.body.append(cpp.method_call(by_arg_count['name']))

                if current:
                    current.cpp_else = cif
                
                current = cif
            method.execution.append(cand)
    else:
        stack_index = 0
        if function.parent and type(function.parent) == cpp.cpp_class:
            stack_index += 1

        #adding an index value to each positional parameter
        for i, parameter in enumerate(function.parameters):
            parameter.index = i + 0 if function.is_constructor else 1

        #firstly we add the default initializers for each mapped type
        for parameter in function.parameters:
            method.initialization.append(context.apply_initializer(parameter))
        
        #this additional step will ensure that the amount of parameters is correct
        method.validation.append('assert(lua_gettop({Lua}) == %d)' % len(function.parameters))

        #then we add type checking
        for parameter in function.parameters:
            method.validation.append(context.apply_type_check(parameter))

        #then we get the variables from LUA
        for parameter in function.parameters:
            method.recover.append(context.apply_variable_get(parameter))        

        #then we call the original method!
        method.execution.append(cpp.cpp_method_call(function.name, function.parameters))

        if function.returns != cpp.cpp_type('void'):
            method.lua_return.append(context.apply_variable_set(cpp.cpp_variable('return', function.returns)))
            method.return_value = cpp.cpp_return(1)
        
        #now convert to something the cpp translator is waiting, i.e. the body
        method.body += method.initialization + method.validation + method.recover + method.execution + method.lua_return

        print 'generated method is:', method

        return method

def create_context():

    context = cpp.CppContext()
    context.before_init.append(lua_before_init)

    def initialize_primitive(ctype, lua_type, lua_get, lua_set):
        def initializer(variable, ctype):
            return variable

        def type_check(variable, ctype):
            return 'assert(lua_type(L,%d) == %s)' % (variable.index, lua_type)

        def variable_get(variable, ctype):
            return '%s = %s(L, %d)' % (variable.name, lua_get, variable.index)

        def variable_set(variable, ctype):
            return '%s(L, %s)' %(variable.name)

        ctype.initializer = initializer
        ctype.type_check = type_check
        ctype.variable_get = variable_get
        ctype.variable_set = variable_set

        return ctype

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

    #setting our method translation routine
    context.method_translation = (lua_method_translation)

    return context
