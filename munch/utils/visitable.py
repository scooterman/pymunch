

'''
    Automatically adds a visit_{class name} method on all classes that are decorated.
'''
def visitable(cls):
    cls.visit = lambda self, visitor, **kargs: getattr(visitor, 'visit_' + cls.__name__)(self, **kargs)
    return cls