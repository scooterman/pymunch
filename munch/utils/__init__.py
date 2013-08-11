

def apply_pipeline(lst, *items):
    '''
    Iters over a list applying a list of @items on each
    obs: I could use map here, but map returns a list and eats up some memory
    '''
    for applicable in lst:
        items = applicable(*items)

    return items


def flatten(exprs, prepend='', append=lambda expr: str(expr)):
    if type(exprs) is None:
        return ''

    if type(exprs) != list:
        return str(exprs)

    return prepend.join(
        map(lambda expr: ''
            if expr is None else (append(expr)
            if type(expr) != list else flatten(expr, append)), exprs))
