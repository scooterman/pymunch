from munch.languages import cpp
from munch.targets import cpp as lua_cpp
from munch.conversor.lua_lightuserdata import lua_context_builder

class cpp_unique_ptr_variable(cpp.cpp_variable):
    def assign(self, expression, lhs = None):
        return cpp.cpp_assignment('' if lhs is None else lhs, 'std::move(' + str(expression) + ')')

@lua_cpp.variable_conversion_to_target_language(cpp.MUNCH_ANY_TYPE,
                    lambda item: 'std::unique_ptr' in item.ctype.name,
                    lua_context_builder)
def cpp_unique_ptr_to_target(variable, ctype):
    return 'lua_pushlightuserdata(L, %s)' % (cpp.cpp_cast(cpp.cpp_type('void', pointer=True), 'new {}(std::move({}))'.format(variable.ctype.name, variable.name)))

orig_cpp_variable = cpp.cpp_variable
def cpp11_variable(name, ctype, expr = None):
    if 'std::unique_ptr' in ctype.name:
	   return cpp_unique_ptr_variable(name, ctype, expr)    
    return orig_cpp_variable(name, ctype, expr)

cpp.cpp_variable = cpp11_variable