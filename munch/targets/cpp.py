from munch.utils import *
from functools import wraps
import logging
import copy

logging.basicConfig(level=logging.DEBUG, format='{%(filename)s:%(lineno)d} - %(message)s')

qualtype_logger = logging.getLogger('QUALTYPE')
qualtype_logger.disabled = True

variable_logger = logging.getLogger('VARIABLE')
variable_logger.disabled = True

translation_logger = logging.getLogger('TRANSLATION')
translation_logger.disabled = True

class CppContext(object):
    def __init__(self):
        self.translated = []

class CppContextBuilder(object):
    def __init__(self):
        self.initialization = []
        self.method_translation = []
        self.class_translation = []
        self.preprocess = []
        self.variable_initializers = {}
        self.variable_checkers = {}
        self.var_from_target = {}
        self.var_to_target = {}

        self.initializer_matcher = {}
        self.var_to_target_matcher = {}
        self.var_from_target_matcher = {}
        self.var_checker_macher = {}

    def get_matcher_list(self, matcher_name):
        matcher = None
        items = None

        if matcher_name == "init":
            matcher = self.initializer_matcher
            items = self.variable_initializers
        elif matcher_name == "checker":
            matcher = self.var_checker_macher
            items = self.variable_checkers
        elif matcher_name == "to_target":
            matcher = self.var_to_target_matcher
            items = self.var_to_target
        elif matcher_name == "from_target":
            matcher = self.var_from_target_matcher
            items = self.var_from_target

        assert matcher != None
        assert items != None

        return matcher, items

    def matches(self, matcher_name, item, other):
        matcher, _ = self.get_matcher_list(matcher_name)
        return matcher[id(item)] == other

    def build_matcher(self, matcher_name, ctype):
        matcher, items = self.get_matcher_list(matcher_name)

        #we set the best match for @ctype iterating over all items from a list and getting it's proximity values
        heights = map(lambda _ctype: (_ctype, _ctype.conforms_match(ctype)), items)
        heights.sort(reverse=True, cmp=lambda a, b: a[1] - b[1])
        
        logging.debug('Building matcher for %r on list %s. Matched: %r with height %d', ctype, matcher_name, heights[0][0], heights[0][1])

        matcher[id(ctype)] = heights[0][0]

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
        logging.debug('Trying to translate method: ' + original_method.name)
        for tag, translator in self.method_translation:
            translation_logger.debug('\tTrying to match on rule: ' + tag)
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
        for ctype, trans in self.variable_initializers.iteritems():
            res = trans(in_var, context)
            if res: return res

    def apply_variable_check(self, in_var, context):
        for ctype, trans in self.variable_checkers.iteritems():
            res = trans(in_var, context)
            if res: return res

    def apply_variable_conversion_to_target(self, in_var, context):
        for ctype, trans in self.var_to_target.iteritems():
            res = trans(in_var, context)
            if res: return res

    def apply_variable_conversion_from_target(self, in_var, context):
        for ctype, trans in self.var_from_target.iteritems():
            res = trans(in_var, context)
            if res: return res

    def bake(self, data, preprocess = True, initialize = True, translate = True):
        logging.debug('baking data: %s' % data)
        ctx = CppContext()

        if preprocess:
            for tag, preprocess in self.preprocess:
                logging.debug('preprocessing:' + tag)
                preprocess(data, ctx)

        logging.debug('INITIALIZATION PHASE')
        if initialize:
            for item in data:
                for tag, init in self.initialization:
                    logging.debug('initializing: [%s] for item: %s ', tag, repr(item))
                    init(item, ctx)   


        logging.debug('TRANSLATION PHASE')                    
        if translate:            
            for item in data:
                if type(item) == cpp_method:
                    self.translate_method(item, ctx, True)

            for item in data:
                if type(item) == cpp_class:
                    self.translate_class(item, ctx, True)

        logging.debug('finished baking!')
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
            translation_logger.debug('\t\t ' + trans_id + ' matches? ' + str(comparator(original_method)))
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
            variable_logger.debug("[VARINIT] Testing ctype %r for variable %r" % (ctype, original))

            if not id(original.ctype) in context_builder.initializer_matcher:
                context_builder.build_matcher('init', original.ctype)

            if comparator(original) and context_builder.matches('init',                                                                 
                                                                original.ctype,
                                                                ctype):
                variable_logger.debug("\tMatched. Applying function: %r" % function)
            
                return function(original, context)
            
            variable_logger.debug("\tNot matched.")        

            return False

        context_builder.variable_initializers[ctype] = wrapped_variable_initialization

        return wrapped_variable_initialization

    return decorator

def variable_check(ctype, comparator, context_builder):
    def decorator(function):
        @wraps(function)      
        def wrapped_variable_check(original, context):

            if not id(original.ctype) in context_builder.var_checker_macher:
                context_builder.build_matcher('checker', original.ctype)

            variable_logger.debug("[VARCHECK] Testing ctype %r for variable %r" % (ctype, original))
            
            if comparator(original) and context_builder.matches('checker',                                                                 
                                                                original.ctype,
                                                                ctype):
                variable_logger.debug("\tMatched. Applying function: %r" % function)
                return function(original, context)
            variable_logger.debug("\tNot matched.")
            return False

        context_builder.variable_checkers[ctype] = wrapped_variable_check
        return wrapped_variable_check

    return decorator

def variable_conversion_from_target_language(ctype, comparator, context_builder):
    def decorator(function):
        @wraps(function)        
        def wrapped_variable_conversion_from_target_language(original, context):
            if not id(original.ctype) in context_builder.var_from_target_matcher:
                context_builder.build_matcher('from_target', original.ctype)

            if comparator(original) and context_builder.matches('from_target',                                                                 
                                                                original.ctype,
                                                                ctype):
                variable_logger.debug("\tMatched. Applying function: %r" % function)
                return function(original, context)

            variable_logger.debug("\tNot matched.")
            return False

        context_builder.var_from_target[ctype] = wrapped_variable_conversion_from_target_language

        return wrapped_variable_conversion_from_target_language

    return decorator

def variable_conversion_to_target_language(ctype, comparator, context_builder):
    def decorator(function):
        @wraps(function)
        def wrapped_variable_conversion_to_target_language(original, context):
            if not id(original.ctype) in context_builder.var_to_target_matcher:
                context_builder.build_matcher('to_target', original.ctype)

            if comparator(original) and context_builder.matches('to_target',                                                                 
                                                                original.ctype,
                                                                ctype):
                variable_logger.debug("\tMatched. Applying function: %r" % function)
                return function(original, context)
            variable_logger.debug("\tNot matched.")
            return False

        context_builder.var_to_target[ctype] = wrapped_variable_conversion_to_target_language

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
        assert self.expr != None        
        return '*' + str(self.expr)

class cpp_reference(object):
    def __init__(self, expr):
        self.expr = expr

    def __repr__(self):
        return '< reference >'

    def __str__(self):
        assert self.expr != None
        return '&' + str(self.expr)

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
    if_str = 'if ({exprs}) {{ \n {body} }} {elseBlock}'

    def __init__(self, expr = [], body = []):
        cpp_block.__init__(self, expr)
        self.body = list(body)
        self.cpp_else = None

    def __repr__(self):
        return '< if expression >'

    def __str__(self):
        assert(self.exprs)

        return cpp_if.if_str.format(exprs = '\n'.join(map(str, self.exprs)),
                             body = ''.join(map(lambda body: str(body) + ';\n', self.body)),
                             elseBlock = '' if not self.cpp_else else ' else ' + str(self.cpp_else))

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
        
        return ('%s %s %s' % (self.ctype,  self.name, '' if self.expr == None else '= %s' % str(self.expr))).strip()

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
    def flatten(values, output):
        for i in values:
            if type(i) in (list, tuple):
                flatten(i, output)
            elif type(i) == dict:
                for k, v in i:
                    output.append(k)
                    flatten(v, output)
            elif type(i) in (str, unicode, int, long, bool):
                output.append(hash(i))
            else:
                output.append(id(i))

    if f:
        l = [id(f)]
    else:
        l = []

    global mark

    flatten(args, l)

    l.append(id(mark))

    for k, v in kwargs:
        l.append(k)
        flatten(v, l)

    return tuple(l)

_memoized = {}
def memoize(f):
    """ 
    Some basic memoizer
    """
    def memoized(*args, **kwargs):
        key = get_id_tuple(f, args, kwargs)     
        
        if key not in _memoized:
            _memoized[key] = f(*args, **kwargs)
            _memoized[key].hash = sum(key)

        return _memoized[key]
    return memoized

@memoize
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
        return cpp_qual_type.bitflag_pointer & self._bitflags 

    def is_static(self):
        return cpp_qual_type.bitflag_static & self._bitflags 

    def is_const(self):
        return cpp_qual_type.bitflag_const & self._bitflags         

    def is_reference(self):
        return cpp_qual_type.bitflag_reference & self._bitflags 

    #returns the qualifiers for the current ctype, nested to the deepest
    #item
    def recover_qualifiers(self):
        if not type(self.name) is str:
            return self.recover_qualifiers(ctype.name)

        return 'const' if self.is_const() else '' + \
               '*' if self.is_pointer() else '' + \
               '&' if self.is_reference() else '' 

    #Simply changing an attribute can cause
    #major problems since we're changing the memoized object
    #so we have to mutate it with new attributes
    def mutate(self, **kwargs):
        pointer = self.is_pointer() or ('pointer' in kwargs and kwargs['pointer'])
        static = self.is_pointer() or ('static' in kwargs and kwargs['static'])
        const = self.is_pointer() or ('const' in kwargs and kwargs['const'])
        reference = self.is_pointer() or ('reference' in kwargs and kwargs['reference'])
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
        base = 2 * int(self.name == other.name or other.name in self.spelling)
        
        if base:
            base += (self._bitflags & other._bitflags)

        return base
   
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
             '<%s>' % (','.join(map(str, self.templates))) if self.templates else '',
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
        return '< cpp method: "%s" (%s) >' % (self.name, id(self))

    def __str__(self):
        assert(self.name)
        assert(self.returns)
        try:
            return cpp_method.body_str.format(return_type=self.returns,
                    static = 'static' if self.static else '', 
                    func_name=self.name,
                    param_list=','.join(map(str, self.parameters)),
                    body='\n'.join(map(lambda expr: str(expr) + (';' if not isinstance(expr, cpp_block) else ''),  self.exprs)),
                    return_value= '' if not self.return_value else str(self.return_value) + ';')
        except Exception, e:
            print 'Failed to process a method named:', self.name
            print 'body:', self.exprs
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
        except Exception, e:
            print 'failed to process a class named: ' , self.name
            raise e

#we create a type to mach any other type
class munch_any_type(cpp_qual_type):
    #we set any to 1, so if no item matches, any will
    def conforms_match(self, other):
        return 1

MUNCH_ANY_TYPE = munch_any_type('!@_MUNCH_YAMMY')
