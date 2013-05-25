from munch.utils import *
from functools import wraps
import logging
import inspect

logging.basicConfig(level=logging.DEBUG)

class CppContext(object):
    def __init__(self):
        self.translated = []

class CppContextBuilder(object):
    def __init__(self):
        self.initialization = []
        self.method_translation = []
        self.class_translation = []
        self.preprocess = []
        self.variable_initializers = []
        self.variable_checkers = []
        self.var_from_target = []
        self.var_to_target = []

    def add_preprocess(self, translator_name, processor):
        self.preprocess.append((translator_name, processor))

    def add_translation(self, context_name, translator_name, translator, before):
        queue = self.initialization if context_name == 'initialization' else \
                self.class_translation if context_name == 'class' else \
                self.method_translation if context_name == 'method' else None

        if before:
            for i, item in enumerate(queue):
                if item[0] == before:
                    queue.insert(i - 1, (translator_name, translator))
        else:
            queue.append((translator_name, translator))

    def translate_method(self, original_method, context, append = False):
        for tag, translator in self.method_translation:
            translator(original_method, context)

        if append and original_method.translation:
            context.translated.append(original_method.translation)

        return original_method.translation

    def translate_class(self, in_cls, context, append = True):       
        for tag, translator in self.class_translation:
            translator(in_cls, context)
        
        if append and in_cls.translation:
            context.translated.append(in_cls.translation)

        return in_cls.translation

    def apply_variable_initialization(self, in_var, context):
        for ctype, trans in self.variable_initializers:
            res = trans(in_var, context)
            if res: return res

    def apply_variable_check(self, in_var, context):
        for ctype, trans in self.variable_checkers:
            res = trans(in_var, context)
            if res: return res

    def apply_variable_conversion_to_target(self, in_var, context):
        for ctype, trans in self.var_to_target:
            res = trans(in_var, context)
            if res: return res

    def apply_variable_conversion_from_target(self, in_var, context):
        for ctype, trans in self.var_from_target:
            res = trans(in_var, context)
            if res: return res

    def bake(self, data, context = None):
        ctx = CppContext()

        for tag, preprocess in self.preprocess:
            logging.debug('preprocessing:' + tag)
            preprocess(data, ctx)

        for item in data:
            for tag, init in self.initialization:
                logging.debug('initializing:' + tag)
                init(item, ctx)   

        for item in data:
            if type(item) == cpp_method:
                self.translate_method(item, ctx, True)

        for item in data:
            if type(item) == cpp_class:
                self.translate_class(item, ctx, True)

        return ctx

def preprocess(trans_id, context_builder, before = None):    
    def decorator(function):
        context_builder.add_preprocess(trans_id, function)
        @wraps(function)
        def wrapped(data, context):
            function(data,context)       
        
        return wrapped
    return decorator

def translation_initialization(trans_id, comparator, context_builder, before = None):
    def decorator(function):        
        @wraps(function)
        def wrapped_translation_initialization(original_method, context):
            if comparator(original_method):
                function(original_method, context)
        
        context_builder.add_translation('initialization', trans_id, wrapped_translation_initialization, before)
        return wrapped_translation_initialization

    return decorator

def method_translation(trans_id, comparator, context_builder, before = None):
    def decorator(function):
        @wraps(function)
        def wrapped_method_translation(original_method, context):
            if comparator(original_method):
                function(original_method, context)
        
        context_builder.add_translation('method', trans_id, wrapped_method_translation, before)
        return wrapped_method_translation

    return decorator

def class_translation(trans_id, comparator, context_builder, before = None):
    def decorator(function):
        @wraps(function)
        def wrapped_class_translation(original, context):
            if comparator(original):
                function(original, context)
        
        context_builder.add_translation('class', trans_id, wrapped_class_translation, before)
        return wrapped_class_translation

    return decorator

def type_translation(trans_id, comparator, context_builder, before = None):
    def decorator(function):
        @wraps(function)
        def wrapped_type_translation(original, context):
            if comparator(original):
                function(original, context)
        
        context_builder.add_translation('type', trans_id, wrapped_type_translation, before)
        return wrapped_type_translation

    return decorator

def variable_initialization(ctype, comparator, context_builder):
    def decorator(function):
        @wraps(function)        
        def wrapped_variable_initialization(original, context):
            logging.debug("[VARINIT] Testing ctype %r for variable %r" % (ctype, original))

            if comparator(original) and ctype == original.ctype:
                logging.debug("\tMatched. Applying function: %r" % function)
            
                return function(original, context)
            
            logging.debug("\tNot matched.")            
            return False

        context_builder.variable_initializers.append((ctype, wrapped_variable_initialization))
        return wrapped_variable_initialization

    return decorator

def variable_check(ctype, comparator, context_builder):
    def decorator(function):
        @wraps(function)      
        def wrapped_variable_check(original, context):
            logging.debug("[VARCHECK] Testing ctype %r for variable %r" % (ctype, original))
            if comparator(original) and original.ctype == ctype:
                logging.debug("\tMatched. Applying function: %r" % function)
                return function(original, context)
            logging.debug("\tNot matched.")
            return False

        context_builder.variable_checkers.append((ctype, wrapped_variable_check))
        return wrapped_variable_check

    return decorator

def variable_conversion_from_target_language(ctype, comparator, context_builder):
    def decorator(function):
        @wraps(function)        
        def wrapped_variable_conversion_from_target_language(original, context):
            if comparator(original) and original.ctype == ctype:
                return function(original, context)
            return False

        context_builder.var_from_target.append((ctype, wrapped_variable_conversion_from_target_language))

        return wrapped_variable_conversion_from_target_language

    return decorator

def variable_conversion_to_target_language(ctype, comparator, context_builder):
    def decorator(function):
        @wraps(function)
        def wrapped_variable_conversion_to_target_language(original, context):
            if comparator(original) and ctype == original.ctype:
                return function(original, context)
            return False

        context_builder.var_to_target.append((ctype, wrapped_variable_conversion_to_target_language))

        return wrapped_variable_conversion_to_target_language
    return decorator

class cpp_assignment(object):
    def __init__(self, expr_a, expr_b):
        self.expr_a = expr_a
        self.expr_b = expr_b

    def __repr__(self):
        return '< assignment >'

    def __str__(self):
        assert(self.expr_a)
        assert(self.expr_b)

        return str(self.expr_a) + ' = ' + str(self.expr_b)

class cpp_dereference(object):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return '< dereference >'

    def __str__(self):
        assert self.expr
        assert type(self.expr) == cpp_variable or type(self.exr) == str
        return '*' + str(self.expr.name)

class cpp_and:
    def __init__(self, expr = []):
        self.exprs = list(expr)

    def __repr__(self):
        return '< and expression >'

    def __str__(self):
        assert(self.exprs)
        return ' && '.join(self.exprs)

class cpp_or:
    def __init__(self, expr = []):
        self.exprs = list(expr)
    def __repr__(self):
        return '< or expression >'

    def __str__(self):
        assert(self.exprs)
        return ' || '.join(self.exprs)

class cpp_block(object):
    def __init__(self, exprs = []):
        self.exprs = list(exprs)

    def __repr__(self):
        return '< block expression of size %d >' % len(self.exprs)

    def __str__(self):
        assert(self.exprs)
        return '{%s}' % self.expr   


class cpp_if (cpp_block):
    def __init__(self, expr = [], body = []):
        cpp_block.__init__(self)
        self.body = list(body)
        self.cpp_else = None

    def __repr__(self):
        return '< if expression >'

    def __str__(self):
        assert(self.exprs)
        return 'if (%s) { \n %s } %s' % \
            ('\n'.join(map(str, self.exprs)), 
             ''.join(map(lambda body: str(body) + ';\n', self.body)),
             '' if not self.cpp_else else ' else %s ' % str(self.cpp_else))

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
                            body='\n'.join(map(lambda ast: str(ast) + ';', self.body)),
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
        return cpp_case_default.case_str.format(body='\n'.join(self.body))

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
            case_exprs='\n'.join(map(str, self.exprs)),
            default=self.default)


class cpp_variable(object):
    def __init__(self, name, ctype, expr = None):
        self.name = name
        self.expr = expr
        self.ctype = ctype
        self.parent = None

    def __repr__(self):
        return '<cpp variable: "%s %s" >' % (self.ctype, self.name)

    def __str__(self):
        assert(self.ctype)
        assert(self.name)
        
        return ('%s %s %s' % (self.ctype,  self.name, '' if self.expr == None else '= %s' % str(self.expr))).strip()

class cpp_variable_array(object):
    def __init__(self, name, ctype, expr = []):
        self.name = name
        self.expr = list(expr)
        self.ctype = ctype
        self.parent = None

    def __repr__(self):
        return '< cpp variable array: %s[%d] >' % (self.name, len(self.expr))

    def __str__(self):
        assert(self.ctype)
        assert(self.name)

        return ('%s %s %s' % (self.ctype,  self.name, '' if self.expr == None else '[%d] = { %s }' % (len(self.expr), ','.join(map(str, self.expr))))).strip()

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
def cpp_type(*args, **kwargs):
    return cpp_qual_type(*args, **kwargs)

class cpp_qual_type(object):
    def __init__(self, name, pointer=False, static=False, const=False, reference=False, templates=[]):
        self.name = name
        self.pointer = pointer
        self.static = static
        self.const = const
        self.reference = reference
        self.templates = list(templates)
        self.bitflags = 0
        self.initializer = None
        self.type_check = None
        self.variable_get = None
        self.variable_set = None
        self.type_conversion = None
        self.variable_dereference = None
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
             str(self.name),
             '<%s>' % (','.join(map(str, self.templates))) if self.templates else '',
             '*' if self.pointer else '',
             '&' if self.reference else '')
        
        return result.strip()

class cpp_method_call(object):
    def __init__(self, expr, params=[]):
        self.expr = expr
        self.params = list(params)
        self.parent = None

    def __repr__(self):
        return '<method call: "%s" >' % self.expr

    def __str__(self):
        assert(self.expr)
        return '%s(%s)' % (str(self.expr),  ','.join(map(str, self.params)))

class cpp_method(cpp_block):
    body_str =\
'''
{static} {return_type} {func_name} ({param_list}) {{
    {body}
    {return_value}
}}'''
    def __init__(self, name, static = False,
                 returns = cpp_type('void'), params=[], return_value=None,
                 is_constructor = False, is_virtual = False):
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

    def __repr__(self):
        return '< cpp method: "%s" >' % self.name

    def __str__(self):
        assert(self.name)
        assert(self.returns)
       
        return cpp_method.body_str.format(return_type=self.returns,
                    static = 'static' if self.static else '', 
                    func_name=self.name,
                    param_list=','.join(map(str, self.parameters)),
                    body='\n'.join(map(lambda expr: str(expr) + ';' if not isinstance(expr, cpp_block) else '',  self.exprs)),
                    return_value= '' if not self.return_value else str(self.return_value) + ';')

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
        return cpp_class.cpp_class_str.format(ClassName = self.name,
            Bases = '' if not self.bases else ':' + ','.join(map(str, self.bases)),
            PublicDeclarations = '' if not self.public else 'public:\n' + '\n'.join(map(lambda item: str(item) + (';' if not isinstance(item, cpp_block) else ''), self.public)), 
            ProtectedDeclarations = '' if not self.protected else 'protected:\n' + ';\n'.join(map(str, self.protected)),
            PrivateDeclarations = '' if not self.private else 'private:\n' + ';\n'.join(map(str, self.private)),
        )


#we create a type to mach any other type
class munch_any_type(cpp_qual_type):
    def __eq__(self, other):
        return True

    def __neq__(self, other):
        return False

MUNCH_ANY_TYPE = munch_any_type('!@_MUNCH_YAMMY')
