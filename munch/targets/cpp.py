class CppContext(object):
    def __init__(self):
        self.before_init = []
        self.method_translation = lambda ctx, data: None
        self.class_translation = lambda ctx : None

        self.translated = []
        self.types = {}
        
        self.on_ctype_register = lambda ctype: ctype

    def register_ctype(self, ctype):
        template_hash = tuple(map(lambda ctype: ctype.hash, ctype.templates))
        
        if not ctype in self.types:
            self.types[ctype.name] = { template_hash : {}}

        self.types[ctype.name][template_hash][ctype.bitflags] = ctype
        self.on_ctype_register(ctype)

        if not ctype.initializer: ctype.initializer = lambda context,  ctype: None
        if not ctype.type_check: ctype.type_check = lambda context,  ctype: None
        if not ctype.variable_get: ctype.variable_get = lambda context,  ctype: None
        if not ctype.variable_set: ctype.variable_set = lambda context,  ctype: None
        if not ctype.type_conversion: ctype.type_conversion = lambda context,  ctype: None
        
        return ctype

    def get_registered_ctype(self, ctype):
        if ctype.name not in self.types:
            return None
    
        template_hash = tuple(map(lambda ctype: ctype.hash, ctype.templates))
        bitflags = self.types[ctype.name][template_hash]
        
        #if we have a perfect match, return it
        if ctype.bitflags in bitflags:
            return bitflags[ctype.bitflags]
        
        #else, figure out the best option, i.e., with the biggest compatibility
        
        f = 0
        for flag in bitflags:
            if flag & ctype.bitflags > f:
                f = flag
        
        return bitflags[f]

    def get_ctype(self, ctype):
        found = self.get_registered_ctype(ctype)
        
        if not found:
            return self.register_ctype(ctype)
            
        return found

    def add_type_check(self, ctype, check):
        self.get_ctype(ctype).type_check = check

    def apply_initializer(self, variable):
        assert type(variable) == cpp_variable

        found = self.get_registered_ctype(variable.ctype)
        
        if not found:
            return 'assert(false && "failed to find a suitable initializer for variable [%s]")' % variable
       
        return found.initializer(variable, found)
        
    def apply_variable_set(self, variable):
        assert type(variable) == cpp_variable
        found = self.get_registered_ctype(variable)
        
        if not found:
            return 'assert(false && "failed to find a suitable conversion cpp->target for variable [%s]")' % variable
        
        return found.variable_set(variable, found)

    def apply_type_conversion(self, ctype):
        return 'assert(false && "failed to find a suitable conversion for type [%s]")' % ctype

    def apply_variable_get(self,  variable):
        assert type(variable) == cpp_variable
        found = self.get_registered_ctype(variable.ctype)
        
        if not found:
            return 'assert(false && "failed to find a suitable target->cpp type [%s]")' % variable
        
        return found.variable_get(variable, found)

    def apply_type_check(self, variable):
        assert type(variable) == cpp_variable
        found = self.get_registered_ctype(variable.ctype)
        
        if not found:
            return 'assert(false && "error fetching type check fortype [%s]")' % variable.name
        
        return found.type_check(variable, found)

    def translate_method(self, json_method):
        method = self.method_translation(self, json_method)
        self.translated.append(method)

        return method

    def translate_class(self, in_cls):        
        cls = self.class_translation(in_cls)
        self.translated.append(cls)

        return cls

    def munch(self, data):
        map(lambda item: item(self, data), self.before_init)

        for item in data:
            if type(item) == cpp_method:
                self.translate_method(item)
            elif type(item) == cpp_class:
                self.translate_class(item)

class cpp_and:
    def __init__(self, expr = []):
        self.exprs = expr

    def __repr__(self):
        return '<and expression: "%s" >' % self.__str__()

    def __str__(self):
        assert(self.exprs)
        return ' && '.join(self.exprs)

class cpp_or:
    def __init__(self, expr = []):
        self.exprs = expr
    def __repr__(self):
        return '<or expression: "%s" >' % self.__str__()

    def __str__(self):
        assert(self.exprs)
        return ' || '.join(self.exprs)

class cpp_if:
    def __init__(self, expr = [], body = []):
        self.exprs = expr
        self.body = body
    def __repr__(self):
        return '<if expression: "%s" >' % self.__str__()

    def __str__(self):
        assert(self.exprs)
        return 'if (%s) { %s }' % (' '.join(self.exprs), '\n'.join(self.body))

class cpp_return(object):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return '<return expression: "%s" >' % self.__str__()

    def __str__(self):
        assert(self.expr != None)
        return 'return %s' % str(self.expr)

class cpp_case(object):
    case_str=\
'''
case {expr}:
    {body}
    break;
'''
    def __init__(self, expr = None, body = []):
        self.expr = expr
        self.body = body
        self.parent = None

    def __repr__(self):
        return '<case expression: "%s" >' % self.__str__()

    def __str__(self):
        assert(self.exprs)
        return cpp_case.case_str.format(expr=self.expr,body=';\n'.join(map(str, self.body)))

class cpp_case_default(object):
    default_str=\
'''
default:
    {body}
    break;
'''
    def __init__(self, body = []):
        self.body = body
        self.parent = None

    def __repr__(self):
        return '<case default expression: "%s" >' % self.__str__()

    def __str__(self):
        return cpp_case_default.case_str.format(body='\n'.join(self.body))

class cpp_switch:
    switch_str=\
'''
switch({switch_expr}) {
{case_exprs}
{default}
}
'''
    def __init__(self, switch_expr, case_exprs = [], default = ''):
        self.switch_expr = switch_expr
        self.case_exprs = case_exprs
        self.default = default
        self.parent = None

    def __repr__(self):
        return '<switch expression: "%s" >' % self.__str__()

    def __str__(self):
        assert(self.switch_expr)
        return cpp_switch.switch_str.format(switch_expr=self.switch_expr, 
            case_exprs='\n'.join(self.case_exprs),
            default=self.default)

class cpp_block(object):
    block_str=\
'''{
  %s
}
'''
    def __init__(self, exprs = []):
        self.exprs = exprs

    def __repr__(self):
        return '<block expression: "%s" >' % self.__str__()

    def __str__(self):
        assert(self.exprs)
        return cpp_block.block_str % self.expr   

class cpp_variable(object):
    def __init__(self, name, ctype, expr = None):
        self.name = name
        self.expr = expr
        self.ctype = ctype
        self.parent = None

    def __repr__(self):
        return '<cpp type: %s >' % self.__str__()

    def __str__(self):
        assert(self.ctype)
        assert(self.name)
        
        return ('%s %s %s' % (self.ctype,  self.name, '' if self.expr == None else '= %s' % str(self.expr))).strip()

mark = object()
def get_id_tuple(f, *args, **kwargs):
    """ 
    Some quick'n'dirty way to generate a unique key for an specific call.
    """
    if f:
        l = [id(f)]
    else:
        l = []

    global mark

    for arg in args:
        if type(arg) in (list, tuple):
            l += get_id_tuple(None, *arg, **kwargs)
        else:
            l.append(id(arg))

    l.append(id(mark))

    for k, v in kwargs:
        l.append(k)
        l.append(id(v))

    return tuple(l)

_memoized = {}
def memoize(f):
    """ 
    Some basic memoizer
    """
    def memoized(*args, **kwargs):
        key = get_id_tuple(f, args, kwargs)

        global _memoized
        if key not in _memoized:
            _memoized[key] = f(*args, **kwargs)
            _memoized[key].hash = sum(key)

        return _memoized[key]
    return memoized

@memoize
class cpp_type(object):
    def __init__(self, name, pointer=False, static=False, const=False, reference=False, templates=[]):
        self.name = name
        self.pointer = pointer
        self.static = static
        self.const = const
        self.reference = reference
        self.templates = templates
        self.bitflags = 0
        self.initializer = None
        self.type_check = None
        self.variable_get = None
        self.variable_set = None
        self.type_conversion = None
        self.update_bitflags()

    def __hash__(self):        
        return self.hash

    def __eq__(self, other):
        return self.name == other.name and self.bitflags == other.bitflags

    def __ne__(self, other):
        return not self == other
   
    def update_bitflags(self):
        attr = 0

        attr &= int(self.static) ** 2
        attr &= (2 * int(self.pointer)) ** 2
        attr &= (3 * int(self.const)) ** 2
        attr &= (4 * int(self.reference)) ** 2

        self.bitflags = attr

    def __repr__(self):
        return '<cpp type: %s >' % self.__str__()

    def __str__(self):
        assert(self.name)

        result = '%s %s %s%s%s%s' %\
            ('static' if self.static else '',
             'const' if self.const else '',
             self.name,
             '<%s>' % (','.join(map(str, self.templates))) if self.templates else '',
             '*' if self.pointer else '',
             '&' if self.reference else '')
        
        return result.strip()

class cpp_method_call(object):
    def __init__(self, expr, params=[]):
        self.expr = expr
        self.params = params
        self.parent = None

    def __repr__(self):
        return '<block expression: "%s" >' % self.__str__()

    def __str__(self):
        assert(self.params)
        return '%s(%s)' % (self.expr,  ','.join(map(str, self.params)))

class cpp_method(object):
    body_str =\
'''
{static} {return_type} {func_name} ({param_list}) {{
    {body}
    {return_value}
}}
'''
    def __init__(self, name, static = False,
                 returns = cpp_type('void'), params=[], return_value=None,
                 is_constructor = False):
        self.name = name
        self.static = static
        self.returns = returns
        self.parameters = params
        self.body = []
        self.return_value = return_value
        self.context = {}
        self.is_constructor = is_constructor
        self.parent = None

    def __repr__(self):
        return '<cpp method: "%s" >' % self.__str__()

    def __str__(self):
        assert(self.name)
        assert(self.returns)
       
        return cpp_method.body_str.format(return_type=self.returns,
                    static = 'static' if self.static else '', 
                    func_name=self.name,
                    param_list=','.join(map(str, self.parameters)),
                    body='\n'.join([line + ';' for line in map(str,  self.body)]),
                    return_value='%s;' % str(self.return_value))

class cpp_class(object):
    def __init__(self,  name, public=[], protected=[], private=[], bases=[]):
        self.name = name
        self.public = public
        self.protected = protected
        self.private = private
        self.bases = bases
