from munch.languages.cpp import visitor
from munch.languages.cpp import ast

def string_semicolon(ident, exprs, content):
    return map(lambda expr, content: ident + content + (';' if not isinstance(expr, ast.cpp_scope) else ''), exprs, content)

class CppSerializerVisitor(visitor.CppVisitor):
    ident = '  '
    def parse(self, ast, **kwargs):
        main_ctx = []
        ast.visit(self, ident='', context=main_ctx, **kwargs)

        return ''.join(main_ctx)

    def visit_cpp_expr(self, item, context, **kwargs):
        if type(item.expr) == bool:
            context.append('true' if item.expr else 'false')
            return

        context.append(str(item.expr))

    def visit_cpp_block(self, block, context, ident, **kwargs):
        ctx = []
        visitor.CppVisitor.visit_cpp_block(self, block, ident=ident + CppSerializerVisitor.ident, context=ctx, **kwargs)

        if ctx:
            expr = string_semicolon(ident, block.exprs, ctx)
            context.append(('\n').join(expr))

    def visit_cpp_scope(self, scope, context, ident, **kwargs):
        ctx = []

        visitor.CppVisitor.visit_cpp_scope(self, scope, ident=ident + CppSerializerVisitor.ident, context=ctx , **kwargs)

        print '"%s"' % ident.join(['{', ''.join(map(lambda item: '\n' + ident + item, ctx)) + '\n' , '}'])
        context.append( ident.join(['{', '\n'.join(map(lambda item: '\n' + ident + item, ctx)) + '\n' , '}']) )

    def visit_cpp_assignment(self, expr, context, ident, **kwargs):
        assert(expr.lhs is not None)
        assert(expr.rhs is not None)

        ctx = []
        visitor.CppVisitor.visit_cpp_assignment(self, expr, ident=ident + CppSerializerVisitor.ident, context=ctx, **kwargs)
        string  = ctx[0] + ' = ' + ctx[1]

        context.append(string)

    def visit_cpp_if(self, ifexpr, context, ident, **kwargs):
        assert(ifexpr.if_exprs)
        
        exprs = []
        for expr in ifexpr.if_exprs:
            expr.visit(self, context = exprs)

        body = []
        self.visit_cpp_scope(ifexpr, context = body, ident = ident )

        string = 'if ({}) {}'.format(' '.join(exprs).strip(), ''.join(body))
        context.append(string)