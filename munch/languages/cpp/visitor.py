
class CppVisitor(object):
    def visit_cpp_expr(self, expr, **kwargs):
        pass

    def visit_cpp_expr_list(self, expr, **kwargs):
        for item in expr:
            item.visit(self, **kwargs)

    def visit_cpp_binop(self, expr, **kwargs):
        expr.lhs.visit(self, **kwargs)
        expr.rhs.visit(self, **kwargs)

    def visit_cpp_block(self, expr, **kwargs):
        self.visit_cpp_expr_list(expr, **kwargs)

    def visit_cpp_assignment(self, expr, **kwargs):
        expr.lhs.visit(self, **kwargs)
        expr.rhs.visit(self, **kwargs)

    def visit_cpp_indirection(self, expr, **kwargs):
        expr.expr.visit(self, **kwargs)

    def visit_cpp_reference(self, expr, **kwargs):
        expr.expr.visit(self, **kwargs)

    def visit_cpp_and(self, expr, **kwargs):
        self.visit_cpp_expr_list(expr, **kwargs)

    def visit_cpp_or(self, expr, **kwargs):
        self.visit_cpp_expr_list(expr, **kwargs)

    def visit_cpp_if(self, expr, ** kwargs):
        expr.if_exprs.visit(self, **kwargs)
        self.visit_cpp_block(expr, **kwargs)

    def visit_cpp_return(self, expr, **kwargs):
        self.visit_cpp_expr(expr, **kwargs)

    def visit_cpp_case(self, expr, **kwargs):
        expr.expr.visit(self, **kwargs)
        self.visit_cpp_block(expr, **kwargs)

    def visit_cpp_break(self, expr, **kwargs):
        pass

    def visit_cpp_switch(self, expr, **kwargs):
        expr.switch_expr.visit(self, **kwargs)
        self.visit_cpp_block(expr, **kwargs)

    def visit_cpp_default(self, expr, **kwargs):
        self.visit_cpp_case(expr, **kwargs)

    def visit_cpp_for(self, expr, **kwargs):
        expr.init_expr.visit(self, **kwargs)
        expr.compare_expr.visit(self, **kwargs)
        expr.inc_expr.visit(self, **kwargs)

        self.visit_cpp_block(expr, **kwargs)

    def visit_cpp_qual_type(self, expr, **kwargs):
        pass
