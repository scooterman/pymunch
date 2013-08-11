from munch.languages.cpp.visitor import CppVisitor
from munch.languages.cpp import ast


def string_semicolon(exprs, content):
    return map(lambda expr, content: content +
               (';' if (not isinstance(expr, ast.cpp_block)
                        and not isinstance(expr, ast.cpp_keyword)
                        and not isinstance(expr, ast.cpp_ident)) else ''),
               exprs, content)


class CppSerializerVisitor(CppVisitor):
    ident = ' '
    ident_block = 2

    def parse(self, ast, **kwargs):
        main_ctx = []
        ast.visit(self, ident=0, context=main_ctx, **kwargs)

        return ''.join(main_ctx)

    def get_ident(self, idx):
        return CppSerializerVisitor.ident * \
            (CppSerializerVisitor.ident_block * idx)

    def visit_cpp_keyword(self, expr, context, ident, **kwargs):
        context.append(self.get_ident(ident) + expr.keyword)

    def visit_cpp_ident(self, expr, ident, **kwargs):
        expr.expr.visit(self, ident=expr.ident, **kwargs)

    def visit_cpp_expr(self, expr, context, ident, **kwargs):
        if (isinstance(expr.expr, ast.cpp_expr)
                or isinstance(expr.expr, ast.cpp_expr_list)):
            expr.expr.visit(self, context=context, ident=ident, **kwargs)
        elif type(expr.expr) == bool:
            context.append(self.get_ident(ident) +
                           ('true' if expr.expr else 'false'))
        else:
            context.append(self.get_ident(ident) + str(expr.expr))

    def visit_cpp_block(self, expr, context, ident, **kwargs):
        ctx = []
        ident = ident + (1 if expr.scoped else 0)
        CppVisitor.visit_cpp_block(self, expr,
                                   ident=ident, context=ctx, **kwargs)

        if ctx:
            block = string_semicolon(expr, ctx)
            if expr.scoped:
                lblockident = self.get_ident(ident - 1)
                context.append('{\n' + '\n'.join(block)
                               + '\n' + lblockident + '}')
            else:
                context.append('\n'.join(block))
        elif expr.scoped:
            context.append('{}')

    def visit_cpp_assignment(self, expr, context, ident, **kwargs):
        assert(expr.lhs is not None)
        assert(expr.rhs is not None)

        ctx = []
        CppVisitor.visit_cpp_assignment(self, expr,
                                        ident=0, context=ctx, **kwargs)

        string = ctx[0] + CppSerializerVisitor.ident + '=' \
            + CppSerializerVisitor.ident + ctx[1]

        context.append(self.get_ident(ident) + string)

    def visit_cpp_if(self, expr, context, ident, **kwargs):
        assert(expr.if_exprs)

        exprs = []
        expr.if_exprs.visit(self, ident=0,
                            context=exprs, **kwargs)

        body = []

        self.visit_cpp_block(expr, context=body, ident=ident, **kwargs)

        string = self.get_ident(ident) + 'if ({}) {}'.format(
            ' '.join(exprs).strip(), ''.join(body))
        context.append(string)

    def visit_cpp_indirection(self, expr, context, ident, **kwargs):
        ctx = []

        CppVisitor.visit_cpp_indirection(self, expr,
                                         context=ctx, ident=ident, **kwargs)

        context.append('*(' + ''.join(ctx) + ')')

    def visit_cpp_reference(self, expr, context, ident, **kwargs):
        ctx = []

        CppVisitor.visit_cpp_reference(self, expr, context=ctx,
                                       ident=ident, **kwargs)

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
        expr.expr.visit(self, context=exprs, ident=0, **kwargs)

        scope = []
        if isinstance(expr, ast.cpp_block) and not expr.scoped:
            scope.append('\n')

        self.visit_cpp_block(expr, context=scope,
                             ident=ident + (1 if not expr.scoped else 0),
                             **kwargs)

        context.append(self.get_ident(ident) + 'case {}:{}'.format(
            ' '.join(exprs), ''.join(scope)))

    def visit_cpp_default(self, expr, context, ident, **kwargs):
        scope = []
        if isinstance(expr, ast.cpp_block) and not expr.scoped:
            scope.append('\n')

        self.visit_cpp_block(expr, context=scope, ident=ident + 1, **kwargs)

        context.append(self.get_ident(ident) + 'default:{}'.format(
            ''.join(scope)))

    def visit_cpp_switch(self, expr, context, ident, **kwargs):
        exprs = []
        expr.switch_expr.visit(self, context=exprs, ident=ident, **kwargs)

        scope = []
        self.visit_cpp_block(expr, context=scope, ident=ident, **kwargs)

        context.append(self.get_ident(ident) + 'switch({}){}'.format(
            ' '.join(exprs), ''.join(scope)))

    def visit_cpp_for(self, expr, context, ident, **kwargs):
        init = []
        expr.init_expr.visit(self, context=init, ident=0, **kwargs)

        compare_expr = []
        expr.compare_expr.visit(self, context=compare_expr, ident=0, **kwargs)

        inc_expr = []
        expr.inc_expr.visit(self, context=inc_expr, ident=0, **kwargs)

        scope = []

        if isinstance(expr, ast.cpp_block) and not expr.scoped:
            scope.append('\n')

        self.visit_cpp_block(expr,
                             context=scope,
                             ident=ident + (0 if expr.scoped else 1), **kwargs)

        context.append(self.get_ident(ident) + 'for({};{};{}){}'.format(
            ' '.join(init), ' '.join(compare_expr),
            ' '.join(inc_expr), ''.join(scope)))

    def visit_cpp_qual_type(self, expr, context, ident,
                            qualified=False, **kwargs):
        ctx = []
        for item in ('static', 'const', 'constexpr'):
            if getattr(expr, 'is_' + item)():
                ctx.append(item)

        parent = []
        if qualified and expr.parent:
            expr.parent.visit(self, context=parent,
                              ident=0, qualified=True, **kwargs)

        parent.append(expr.name)
        ctx.append('::'.join(parent))

        tp = ' '.join(ctx)

        if expr.is_reference():
            tp += '&'

        if expr.is_pointer():
            tp += '*'

        context.append(self.get_ident(ident) + tp)

    def visit_cpp_variable(self, expr, context, ident, **kwargs):
        context.append(self.get_ident(ident) + expr.name)

    def visit_cpp_c_cast(self, expr, context, ident, **kwargs):
        ctx = []
        expr.ctype_to_cast.visit(self, context=ctx, ident=0, **kwargs)

        expr_ctx = []
        expr.expr.visit(self, context=expr_ctx, ident=0, **kwargs)

        context.append('({})({})'.format(' '.join(ctx), ' '.join(expr_ctx)))

    def visit_cpp_variable_array(self, expr, context, ident, **kwargs):
        ctx = []
        expr.variable.visit(self, context=ctx, ident=0, **kwargs)
        context.append(' '.join(ctx))

    def visit_cpp_call(self, expr, context, ident, **kwargs):
        ctx = []
        for param in expr.params:
            param.visit(self, context=ctx, ident=0, **kwargs)

        exprctx = []
        expr.expr.visit(self, context=exprctx, ident=0, **kwargs)
        context.append(
            self.get_ident(ident) + '{}({})'
                .format(''.join(exprctx), ','.join(ctx)))

    def visit_cpp_method(self, expr, context, ident, **kwargs):
        context.append(expr.name)

    def visit_cpp_class(self, expr, context, ident, **kwargs):
        context.append(self.get_ident(ident) + expr.name)

    def visit_cpp_variable_declaration(self, expr, context, ident,
                                       qualified=False, **kwargs):
        parent = []

        if qualified and expr.parent:
            expr.parent.visit(self, context=parent, ident=0, **kwargs)

        parent.append(expr.name)

        ctype = []
        expr.ctype.visit(self, context=ctype, ident=0, **kwargs)

        ctype.append('::'.join(parent))

        context.append(self.get_ident(ident) + ' '.join(ctype))

    def visit_cpp_variable_array_declaration(self, expr,
                                             context, ident, **kwargs):
        ctx = []
        self.visit_cpp_variable_declaration(expr.variable, context=ctx,
                                            ident=0, **kwargs)
        context.append('{}[{}]'.format(' '.join(ctx), expr.length))

    def visit_cpp_method_declaration(self, expr, context,
                                     ident, qualified=False, **kwargs):
        ctx = []

        expr.returns.visit(self, context=ctx, ident=0, **kwargs)
        ctx += expr.attributes

        parent = []
        if qualified and expr.parent:
            expr.parent.visit(self, context=parent,
                              ident=0, qualified=True, **kwargs)

        parent.append(expr.name)
        ctx.append('::'.join(parent))

        lst = []
        self.visit_cpp_expr_list(expr.parameters,
                                 context=lst, ident=0, **kwargs)

        context.append('{}({})'.format(' '.join(ctx), ','.join(lst)))

    def visit_cpp_method_definition(self, expr, context, ident, **kwargs):
        decl = []
        self.visit_cpp_method_declaration(expr,
                                          context=decl, ident=0, **kwargs)

        body = []
        self.visit_cpp_block(expr, context=body, ident=ident, **kwargs)

        context.append(self.get_ident(ident) +
                       '{}{}'.format(''.join(decl), ''.join(body)))

    def visit_cpp_class_definition(self, expr, context, ident, **kwargs):
        block = ast.cpp_block(scoped=True)

        if expr.public:
            block.append(ast.cpp_ident(ident, ast.cpp_keyword('public:')))
            block += map(lambda item: ast.define(item), expr.public)

        if expr.protected:
            block.append(ast.cpp_ident(ident, ast.cpp_keyword('protected:')))
            block += map(lambda item: ast.define(item), expr.protected)

        if expr.private:
            block.append(ast.cpp_ident(ident, ast.cpp_keyword('private:')))
            block += map(lambda item: ast.define(item), expr.private)

        ctx = []
        block.visit(self, context=ctx, ident=ident,
                    scoped=True, **kwargs)

        cdef = 'class {}'.format(expr.name)

        if expr.bases:
            cdef += ' : {}'.format(
                ','.format(['public ' + c for c in expr.bases]))

        context.append(self.get_ident(ident) + '{} {}'.format(
            cdef, ''.join(ctx)))
