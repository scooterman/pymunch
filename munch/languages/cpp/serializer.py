from munch.languages.cpp.visitor import CppVisitor
from munch.languages.cpp import ast

def string_semicolon(exprs, content):
    return map(lambda expr, content: content + (';' if not isinstance(expr, ast.cpp_scope) else ''), exprs, content)

class CppSerializerVisitor(CppVisitor):
    ident = '  '
    def parse(self, ast, **kwargs):
        main_ctx = []
        ast.visit(self, ident = 0, context=main_ctx, **kwargs)

        return ''.join(main_ctx)

    def get_ident(self, idx):
        return  CppSerializerVisitor.ident * idx

    def visit_cpp_expr(self, item, context, **kwargs):
        if isinstance(item.expr, ast.cpp_expr) or isinstance(item.expr, ast.cpp_expr_list):
            item.expr.visit(self, context=context, **kwargs)
        elif type(item.expr) == bool:
            context.append('true' if item.expr else 'false')
        else:
            context.append(str(item.expr))

    def visit_cpp_block(self, block, context, ident, **kwargs):
        ctx = []
        CppVisitor.visit_cpp_block(self, block, ident = ident, context=ctx, **kwargs)

        if ctx:
            expr = string_semicolon(block, ctx)
            context.append(('\n').join(expr))

    def visit_cpp_scope(self, scope, context, ident, **kwargs):
        ctx = []

        CppVisitor.visit_cpp_scope(self, scope, ident = ident + 1, context=ctx , **kwargs)

        if ctx:
            lblockident = self.get_ident(ident - 1)
            context.append('{\n' + ''.join(ctx) + '\n' + lblockident + '}')
        else:
            context.append( '{}' )

    def visit_cpp_assignment(self, expr, context, ident, **kwargs):
        assert(expr.lhs is not None)
        assert(expr.rhs is not None)

        ctx = []
        CppVisitor.visit_cpp_assignment(self, expr, ident=ident + 1, context=ctx, **kwargs)
        string  = ctx[0] + ' = ' + ctx[1]

        context.append(self.get_ident(ident) + string)

    def visit_cpp_if(self, expr, context, ident, **kwargs):
        assert(expr.if_exprs)
        
        exprs = []
        expr.if_exprs.visit(self, context = exprs)

        body = []
        self.visit_cpp_scope(expr, context = body, ident = ident )

        string = self.get_ident(ident) + 'if ({}) {}'.format(' '.join(exprs).strip(), ''.join(body))
        context.append(string)

    def visit_cpp_indirection(self, expr, context, ident, **kwargs):
        ctx = []

        CppVisitor.visit_cpp_indirection(self, expr, context=ctx, ident=ident, **kwargs)

        context.append('*(' + ''.join(ctx) + ')')

    def visit_cpp_reference(self, expr, context, ident, **kwargs):
        ctx = []

        CppVisitor.visit_cpp_reference(self, expr, context=ctx, ident=ident, **kwargs)

        context.append('&(' + ''.join(ctx) + ')')

    def visit_cpp_and(self, expr, context, **kwargs):
        ctx = []

        CppVisitor.visit_cpp_and(self, expr, context=ctx, **kwargs)

        context.append('(' + ' && '.join(ctx) + ')')

    def visit_cpp_or(self, expr, context, **kwargs):
        ctx = []

        CppVisitor.visit_cpp_or(self, expr, context=ctx, **kwargs)

        context.append('(' + ' || '.join(ctx) + ')')

    def visit_cpp_return(self, expr, context, **kwargs):
        ctx = []
        CppVisitor.visit_cpp_return(self, expr, context=ctx, **kwargs)

        context.append('return ' + ' '.join(ctx))

    def visit_cpp_break(self, expr, context, ident, **kwargs):
        context.append(self.get_ident(ident) + 'break')

    def visit_cpp_case(self, expr, context, ident, **kwargs):
        exprs = []
        expr.expr.visit(self, context=exprs, **kwargs)

        scope = []
        if isinstance(expr.body, ast.cpp_block) and not isinstance(expr.body, ast.cpp_scope):
            scope.append('\n')

        expr.body.visit(self, context=scope, ident= ident + 1, **kwargs)

        context.append( self.get_ident(ident) + 'case {}:{}'.format(' '.join(exprs), ''.join(scope)))


    def visit_cpp_default(self, expr, context, ident, **kwargs):
        scope = []
        if isinstance(expr.body, ast.cpp_block)  and not isinstance(expr.body, ast.cpp_scope):
            scope.append('\n')

        expr.body.visit(self, context=scope, ident= ident + 1, **kwargs)
        context.append( self.get_ident(ident) + 'default:{}'.format(''.join(scope)))

    def visit_cpp_switch(self, expr, context, ident, **kwargs):
        exprs = []
        expr.switch_expr.visit(self, context=exprs, **kwargs)

        scope = []
        self.visit_cpp_scope(expr, context=scope, ident= ident + 1, **kwargs)
      
        context.append( self.get_ident(ident) + 'switch({}) {}'.format(' '.join(exprs), ''.join(scope)))