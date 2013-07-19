
class CppVisitor(object):
    def visit_cpp_expr(self, expr, **kwargs):
        pass   

    def visit_cpp_binop(self, expr, **kwargs):
        expr.lhs.visit(self, **kwargs)
        expr.rhs.visit(self, **kwargs)

    def visit_cpp_block(self, block, **kwargs):
        for expr in block.exprs:
            expr.visit(self, **kwargs)

    def visit_cpp_scope(self, scope, **kwargs):
        self.visit_cpp_block(scope, **kwargs)

    def visit_cpp_assignment(self, assignment, **kwargs):
        assignment.lhs.visit(self, **kwargs)
        assignment.rhs.visit(self, **kwargs)

    def visit_cpp_if(self, ifexpr, ** kwargs):
        for expr in ifexpr.if_exprs:
            expr.visit(self, **kwargs)

        self.visit_cpp_scope(ifexpr, **kwargs)