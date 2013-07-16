from functools import wraps

mark = object()
#retrieves the id tuple of a function and an arbitrary set of args and kwargs. It's suposed
#to be unique if the input is the same
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

'''
 Memoizes the input function with arbirtrary args and kwargs. 
 A call with the same function with the same args should return the same object
 memoization_dict: the dictionary that will be used to store the memoized objects
'''
def memoize(memoization_dict):
    def decorator(f):
        @wraps(f)
        def memoized(*args, **kwargs):
            key = get_id_tuple(f, args, kwargs)     
            
            if key not in memoization_dict:
                memoization_dict[key] = f(*args, **kwargs)
                memoization_dict[key].hash = sum(key)

            return memoization_dict[key]
        return memoized
    return decorator