from munch.languages import cpp

from munch.utils import *
from functools import wraps
import logging

logging.basicConfig(level=logging.DEBUG, format='{%(filename)s:%(lineno)d} - %(message)s')

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
            for block in trans:
                res = block(in_var, context)
                if res: return res

    def apply_variable_check(self, in_var, context):
        for ctype, trans in self.variable_checkers.iteritems():
            for block in trans:
                res = block(in_var, context)
                if res: return res

    def apply_variable_conversion_to_target(self, in_var, context):
        for ctype, trans in self.var_to_target.iteritems():
            for block in trans:
                res = block(in_var, context)
                if res: return res

    def apply_variable_conversion_from_target(self, in_var, context):
        for ctype, trans in self.var_from_target.iteritems():
            for block in trans:
                res = block(in_var, context)
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
                if type(item) == cpp.cpp_method:
                    self.translate_method(item, ctx, True)

            for item in data:
                if type(item) == cpp.cpp_class:
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

        if not ctype in context_builder.variable_initializers:
            context_builder.variable_initializers[ctype] = []

        context_builder.variable_initializers[ctype].insert(0, wrapped_variable_initialization)

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

        if not ctype in context_builder.variable_checkers:
            context_builder.variable_checkers[ctype] = []

        context_builder.variable_checkers[ctype].insert(0, wrapped_variable_check)
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

        if not ctype in context_builder.var_from_target:
            context_builder.var_from_target[ctype] = []

        context_builder.var_from_target[ctype].insert(0, wrapped_variable_conversion_from_target_language)

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

        if not ctype in context_builder.var_to_target:
            context_builder.var_to_target[ctype] = []

        context_builder.var_to_target[ctype].insert(0, wrapped_variable_conversion_to_target_language)

        return wrapped_variable_conversion_to_target_language
    return decorator