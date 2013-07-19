import logging
from munch.utils.memoize import memoize
from munch.utils import flatten, visitable

import traceback

flatten_block = lambda expr: str(expr) + ';\n' if not isinstance(expr, cpp_block) else '\n'

qualtype_logger = logging.getLogger('QUALTYPE')
qualtype_logger.disabled = True


@visitable.visitable
class cpp_expr(object):
    '''
        cpp_expr is the basic block of any cpp construct. Will hold the things that are 
        basic to all structures
    '''
    def __init__(self, expr):
        self.expr = expr

@visitable.visitable
class cpp_binop(cpp_expr):
    '''
        Will hold a basic 2-ary expressions
    '''
    def __init__(self, lhs, rhs):
        self.lhs = cpp_expr(lhs)
        self.rhs = cpp_expr(rhs)

@visitable.visitable
class cpp_block(cpp_expr):
    '''
        Will hold a basic N-ary set of expressions
    '''
    def __init__(self, exprs = []):
        self.exprs = list(exprs)

    def __repr__(self):
        return '< block expression of size %d >' % len(self.exprs)

@visitable.visitable
class cpp_scope(cpp_block):
    '''
        An scope is a block that opens a new context, usually with {}'s
    '''
    pass

@visitable.visitable
class cpp_assignment(cpp_binop):
    def __repr__(self):
        return '< assignment >'

class cpp_dereference(object):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return '< dereference >'

    def __str__(self):
        assert self.expr != None        
        return '*(' + str(self.expr) + ')'

class cpp_reference(object):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return '< reference >'

    def __str__(self):
        assert self.expr != None
        return '&(' + str(self.expr) + ')'

class cpp_and:
    def __init__(self, expr = []):
        self.exprs = list(expr)

    def __repr__(self):
        return '< and expression >'

    def __str__(self):
        assert(self.exprs)
        return ' && ('.join(flatten(self.exprs)) + ')'

class cpp_or:
    def __init__(self, expr = []):
        self.exprs = list(expr)
    def __repr__(self):
        return '< or expression >'

    def __str__(self):
        assert(self.exprs)
        return ' || ('.join(flatten(self.exprs)) + ')'

@visitable.visitable
class cpp_if (cpp_scope):
    def __init__(self, expr = [], body = []):
        cpp_scope.__init__(self, body)
        self.if_exprs = list(expr)

        self.cpp_else = None

    def __repr__(self):
        return '< if expression >'

class cpp_return(object):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return '< return expression  >'

    def __str__(self):
        assert(self.expr != None)
        return 'return %s' % str(self.expr)

class cpp_case(object):
    case_str=\
'''
case {expr}:
    {body}
    {Break}
'''
    def __init__(self, expr = None, body = []):
        self.expr = expr
        self.body = list(body)
        self.parent = None

    def __repr__(self):
        return '< case expression >'

    def __str__(self):
        assert(self.expr != None)
        return cpp_case.case_str.format(expr=str(self.expr),
                            body= flatten(self.body, ';', lambda expr: str(expr) + '\n'),
                            Break='break;' if self.body and type(self.body[-1]) != cpp_return else '').strip()

class cpp_case_default(object):
    default_str=\
'''
default:
    {body}
    break;
'''
    def __init__(self, body = []):
        self.body = list(body)
        self.parent = None

    def __repr__(self):
        return '< case default expression >'

    def __str__(self):
        return cpp_case_default.case_str.format(body=flatten(self.body, ';', lambda expr: str(expr) + '\n'))

class cpp_switch (cpp_block):
    switch_str=\
'''
switch({switch_expr}) {{
{case_exprs}
{default}
}}
'''
    def __init__(self, switch_expr, case_exprs = [], default = ''):
        self.switch_expr = switch_expr
        self.exprs = list(case_exprs)
        self.default = str(default)
        self.parent = None

    def __repr__(self):
        return '< switch expression >'

    def __str__(self):
        assert(self.switch_expr)
        return cpp_switch.switch_str.format(switch_expr=str(self.switch_expr), 
            case_exprs=flatten(self.exprs, '', lambda expr: str(expr) + '\n'),
            default=self.default)

class cpp_variable(object):
    def __init__(self, name, ctype, expr = None):
        self.name = name
        self.expr = expr
        self.ctype = ctype
        self.parent = None

    def __repr__(self):
        return '<cpp variable: "%s %s" >' % (self.ctype, self.name)
   
    def declare(self, expr = None):
        return str(self) + str(expr)

    #shorthand to assign items to this qualtype. Use this if you have to assign
    #this variable to something as we change it for c++11 items
    def assign(self, expression, lhs = None):
        return cpp_assignment('' if lhs == None else lhs, expression)

    def reference(self):
        return cpp_reference(self)

    def dereference(self):
        return cpp_dereference(self)

    def define(self):
        print 'parenteee', self.parent, ('' if not self.parent else self.parent.name + '::') + self.name
        return self.ctype.define() + ' ' + ('' if not self.parent else self.parent.name + '::') + self.name

    #casts this variable to another ctype
    #returns a cast_class object with all convertions made
    def cast(self, cast_class, to_ctype):

        logging.debug("[CAST] trying to cast %r from %r to %r" % (self, self.ctype, to_ctype))

        #if the original type is equal to the cast type, we return a transparent string
        if self.ctype == to_ctype:
            logging.debug("[CAST] equal objects, returning")
            return self.name

        if not self.ctype.is_pointer() and not self.ctype.is_reference() and \
            to_ctype.is_reference():
            logging.debug("[CAST] is referenceable, returning")
            return self.name

        res_var = self.name

        if self.ctype.name == to_ctype.name:
            if to_ctype.is_pointer():
                if not self.ctype.is_pointer():
                    res_var = cpp_reference(res_var)

            if to_ctype.is_reference() or not to_ctype.is_pointer():
                if self.ctype.is_pointer():
                    res_var = cpp_dereference(res_var)
        else:
            if to_ctype.is_pointer():
                if not self.ctype.is_pointer():
                    res_var = cast_class(to_ctype, cpp_reference(res_var))
                if self.ctype.is_pointer():
                    res_var = cast_class(to_ctype, res_var)

            if to_ctype.is_reference() or not to_ctype.is_pointer():
                if self.ctype.is_pointer():
                    res_var = cpp_dereference(res_var)

        return res_var

    def __str__(self):
        assert(self.ctype)
        assert(self.name)

        return ('%s %s %s' % (self.ctype, ('' if not self.parent else self.parent.name + '::') + self.name, '' if self.expr == None else '= %s' % str(self.expr))).strip()

class cpp_static_cast(object):
    def __init__(self, ctype_to_cast, expression):
        self.ctype_to_cast = ctype_to_cast
        self.expression = expression

    def __repr__(self):
        return '<cpp static cast: "%s %s" >' % (self.ctype_to_cast, self.expression)

    def __str__(self):
        return 'static_cast<{}>({})'.format(
                self.ctype_to_cast,
                self.expression
            )

class cpp_cast(object):
    def __init__(self, ctype_to_cast, expression):
        self.ctype_to_cast = ctype_to_cast
        self.expression = expression

    def __repr__(self):
        return '<cpp static cast: "%s %s" >' % (self.ctype_to_cast, self.expression)

    def __str__(self):
        return '({})({})'.format(
                self.ctype_to_cast,
                self.expression
            )

class cpp_variable_array(object):
    def __init__(self, name, ctype, expr = []):
        self.name = name
        self.expr = list(expr)
        self.ctype = ctype
        self.parent = None

    def __repr__(self):
        return '< cpp variable array: %s[%d] >' % (self.name, len(self.expr))

    def define(self):
        assert(self.ctype)
        assert(self.name)

        return '{} {} {}'.format(self.ctype,
                                 ('' if not self.parent else self.parent.name + '::') + self.name,
                                 '' if self.expr == None else '[{}]'.format(len(self.expr)))       

    def __str__(self):
        assert(self.ctype)
        assert(self.name)

        return '{} {} {}'.format(self.ctype,
                                 self.name,
                                 '' if self.expr == None else '[{}] = {{ {} }}'.format(
                                            len(self.expr), 
                                            flatten(self.expr, ','))
                                )

@memoize({})
def cpp_type_internal(*args, **kwargs):
    return cpp_qual_type(*args, **kwargs)

def cpp_type(name, pointer=False, static=False, const=False, reference=False, templates=[], spelling=[]):
    return cpp_type_internal(name, pointer, static, const, reference, templates, spelling)

class cpp_qual_type(object):
    bitflag_static = 1
    bitflag_pointer = 2
    bitflag_const = 4
    bitflag_reference = 8

    hooks = []

    def __init__(self, name, pointer=False, static=False, const=False, reference=False, templates=[], spelling=[]):
        self.name = name
        self.templates = list(templates)
        self.spelling = list(spelling)
        self._bitflags = 0
        self.initializer = None
        self.type_check = None
        self.variable_get = None
        self.variable_set = None
        self.type_conversion = None
        self.variable_dereference = None

        self.update_bitflags(pointer, static, const, reference)

        map(lambda hook: hook(self), cpp_qual_type.hooks)

    def is_pointer(self):
        return bool(cpp_qual_type.bitflag_pointer & self._bitflags)

    def is_static(self):
        return bool(cpp_qual_type.bitflag_static & self._bitflags)

    def is_const(self):
        return bool(cpp_qual_type.bitflag_const & self._bitflags)

    def is_reference(self):
        return bool(cpp_qual_type.bitflag_reference & self._bitflags)

    #returns the qualifiers for the current ctype, nested to the deepest
    #item
    def recover_qualifiers(self):
        if not type(self.name) is str:
            return self.recover_qualifiers(self.name)

        return 'const' if self.is_const() else '' + \
               '*' if self.is_pointer() else '' + \
               '&' if self.is_reference() else '' 

    #Simply changing an attribute can cause
    #major problems since we're changing the memoized object
    #so we have to mutate it with new attributes
    def mutate(self, **kwargs):
        pointer = self.is_pointer() if not 'pointer' in kwargs else kwargs['pointer']
        static = self.is_static() if not 'static' in kwargs else kwargs['static']
        const = self.is_const() if not 'const' in kwargs else kwargs['const']
        reference = self.is_reference() if not 'reference' in kwargs else kwargs['reference']
        templates = self.templates if not 'templates' in kwargs else kwargs['templates']
        spelling = self.spelling if not 'spelling' in kwargs else kwargs['spelling']

        return cpp_type(self.name, pointer, static, const, reference, templates, spelling)

    def __hash__(self):        
        return id(self)

    def __eq__(self, other):
        qualtype_logger.debug('QUALTYPE __eq__: %r[%s, %d] == %r[%s, %d]' %(self, self.name, self._bitflags, other, other.name, other._bitflags))
        return (self.name == other.name or other.name in self.spelling) and self._bitflags == other._bitflags

    def __ne__(self, other):
        return not self == other

    def conforms_match(self, other):
        if other.is_pointer() != self.is_pointer():
            return -1

        val = 10 * int(self.name == other.name)
        
        if not val:
            val = 5 * int(self.name in other.spelling or other.name in self.spelling)

        val += int(self.is_const() and other.is_const())
        val += int(self.is_reference() and other.is_reference())

        return val
   
    def update_bitflags(self, pointer, static, const, reference):
        attr = 0        
        qualtype_logger.debug('QUALTYPE update bitflags for %r: %d %d %d %d', self, pointer, static, const, reference)
        attr |= cpp_qual_type.bitflag_static * int(static)
        attr |= cpp_qual_type.bitflag_pointer * int(pointer)
        attr |= cpp_qual_type.bitflag_const * int(const)
        attr |= cpp_qual_type.bitflag_reference * int(reference)

        qualtype_logger.debug('QUALTYPE bitflags for %r: %d' , self, attr)
        self._bitflags = attr

    def __repr__(self):
        return '< cpp type: %s >' % self.__str__()  

    def __str__(self):
        assert(self.name)

        result = '%s %s %s%s%s%s' %\
            ('static' if self.is_static() else '',
             'const' if self.is_const() else '',
             str(self.name),
             '<%s>' % flatten(self.templates, ',') if self.templates else '',
             '*' if self.is_pointer() else '',
             '&' if self.is_reference() else '')
        
        return result.strip()

class cpp_method_call(object):
    def __init__(self, expr, params=[]):
        self.expr = expr
        self.params = list(params)
        self.parent = None

    def __repr__(self):
        return '<method call: "%s" (%s) >' % (self.expr, id(self))

    def __str__(self):
        assert(self.expr)
        return '%s(%s)' % (str(self.expr),  flatten(self.params, ','))

class cpp_method(cpp_block):
    body_str =\
'''
{attributes} {static} {return_type} {func_name} ({param_list}) {{
    {body}
    {return_value}
}}'''
    def __init__(self, name, static = False,
                 returns = cpp_type('void'), params=[], return_value=None,
                 is_constructor = False, is_virtual = False, attributes = []):
        cpp_block.__init__(self)
        self.name = name
        self.static = static
        self.returns = returns
        self.parameters = list(params)
        self.return_value = return_value
        self.context = {}
        self.is_constructor = is_constructor
        self.parent = None
        self.is_virtual = is_virtual
        self.attributes = list(attributes)

    def __repr__(self):
        return '< cpp method: "%s" (%s) >' % (self.name, id(self))

    def __str__(self):
        assert(self.name)
        assert(self.returns)

        try:
            return cpp_method.body_str.format(return_type=self.returns,
                    attributes = flatten(self.attributes, ' '),
                    static = 'static' if self.static else '', 
                    func_name=self.name,
                    param_list=flatten(self.parameters, ','),
                    body=flatten(self.exprs, '', flatten_block),
                    return_value= '' if not self.return_value else str(self.return_value) + ';')
        except Exception, e:
            print 'Failed to process a method named:', self.name
            print 'body:', self.exprs
            traceback.print_exc()
            raise e

class cpp_class(object):
    cpp_class_str=\
'''
class {ClassName} {Bases}
{{
{PublicDeclarations}
{ProtectedDeclarations}
{PrivateDeclarations}  
}};'''

    def __init__(self,  name, public=[], protected=[], private=[], bases=[]):
        self.name = name
        self.public = list(public)
        self.protected = list(protected)
        self.private = list(private)
        self.bases = list(bases)

    def __repr__(self):
        return '< cpp class: "%s" >' % self.name

    def __str__(self):
        assert(self.name)
        try:
            return cpp_class.cpp_class_str.format(ClassName = self.name,
                Bases = '' if not self.bases else ':' + ','.join(map(str, self.bases)),
                PublicDeclarations = '' if not self.public else 'public:\n' + '\n'.join(map(lambda item: str(item) + (';' if not isinstance(item, cpp_block) else ''), self.public)), 
                ProtectedDeclarations = '' if not self.protected else 'protected:\n' + ';\n'.join(map(lambda item: str(item) + (';' if not isinstance(item, cpp_block) else ''), self.protected)),
                PrivateDeclarations = '' if not self.private else 'private:\n' + ';\n'.join(map(lambda item: str(item) + (';' if not isinstance(item, cpp_block) else ''), self.private)),
            )
        except Exception:
            print 'failed to process a class named: ' , self.name
            traceback.print_exc()

#we create a type to mach any other type
class munch_any_type(cpp_qual_type):
    #we set any to 1, so if no item matches, any will
    def conforms_match(self, other):
        return 1

MUNCH_ANY_TYPE = munch_any_type('!@_MUNCH_YAMMY')