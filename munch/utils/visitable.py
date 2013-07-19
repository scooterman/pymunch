

'''
    Automatically adds a visit_{class name} method on all classes that are decorated.
'''
def visitable(cls):
    visit_method = 'visit_' + cls.__name__
    def visit_func(self, visitor, **kargs):
        getattr(visitor, visit_method)(self, **kargs)

    cls.visit = visit_func
    return cls