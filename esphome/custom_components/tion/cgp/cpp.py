from typing import Union

import esphome.codegen as cg
import esphome.cpp_generator as cpp

int8 = cg.global_ns.namespace("int8_t")
char = cg.global_ns.namespace("char")
std_strncpy = cg.std_ns.class_("strncpy")
to_string = cg.esphome_ns.class_("to_string")
esp_logd = cg.esphome_ns.class_("ESP_LOGD")
esp_logv = cg.esphome_ns.class_("ESP_LOGV")
esp_truefalse = cg.esphome_ns.class_("TRUEFALSE")
gpio_num_t = cg.global_ns.enum("gpio_num_t")


def std_get(a: cpp.MockObjClass) -> cpp.MockObjClass:
    return cg.std_ns.class_("get").template(a)


def std_map(a: cpp.MockObjClass, b: cpp.MockObjClass) -> cpp.MockObjClass:
    return cg.std_ns.class_("map").template(a, b)


def std_unordered_map(a: cpp.MockObjClass, b: cpp.MockObjClass) -> cpp.MockObjClass:
    return cg.std_ns.class_("unordered_map").template(a, b)


def static_cast(typ: cpp.MockObjClass, obj: cpp.MockObjClass):
    return cg.MockObj("static_cast").template(typ)(obj)


class MockObjPtr(cg.MockObj):
    def __init__(self, base):
        super().__init__(base, "->")


class PrepocessorStatement(cg.Statement):
    __slots__ = ("name", "text")

    def __init__(self, name: str, text: str):
        self.name = name
        self.text = text

    def __str__(self):
        return f"#{self.name} {self.text}"


class StatementList(cg.Statement):
    __slots__ = ("statements",)

    def __init__(self, statements):
        self.statements = statements if isinstance(statements, list) else [statements]

    def __str__(self):
        ss = []
        for stmt in self.statements:
            if stmt is not None:
                ss.append(str(cg.statement(stmt)))
        return "\n".join(ss)

    def __iter__(self):
        return iter(self.statements)


class CodeBlock(cg.Statement):
    __slots__ = ("prefix", "suffix", "statements", "ident")

    def __init__(self, prefix, suffix, statements, ident: bool = True):
        self.prefix = f"{prefix} " if prefix else ""
        self.suffix = f" {suffix}" if suffix else ""
        self.statements = statements
        self.ident = ident

    def __str__(self):
        ss = []
        ss.append(f"{self.prefix}{{")
        ss.append(str(StatementList(self.statements)))
        ss.append(f"}}{self.suffix}")
        res = "\n".join(ss)
        if self.ident:
            res = cpp.indent_all_but_first_and_last(res)
        return res


class IfDefStatement(cg.Statement):
    __slots__ = ("names", "statements")

    def __init__(self, names, statements):
        self.names = names if isinstance(names, list) else [names]
        self.statements = StatementList(statements).statements

    def __str__(self):
        if len(self.names) == 0:
            return str(StatementList(self.statements))
        name = " && ".join([f"defined({name})" for name in self.names])
        return str(
            StatementList(
                [
                    PrepocessorStatement("if", name),
                    *self.statements,
                    PrepocessorStatement("endif", f"// {name}"),
                ]
            )
        )


class _KeywordStatement(cg.Statement):
    __slots__ = ("keyword", "expression", "statements")

    def __init__(self, keyword, expression, statements):
        self.keyword = keyword
        self.expression = expression
        self.statements = statements

    def __str__(self):
        return str(
            CodeBlock(f"{self.keyword} ({self.expression})", None, self.statements)
        )


class IfStatement(_KeywordStatement):
    def __init__(self, expression, statements):
        super().__init__("if", expression, statements)


class ElseIfStatement(_KeywordStatement):
    def __init__(self, expression, statements):
        super().__init__("else if", expression, statements)


class ElseStatement(cg.Statement):
    __slots__ = ("statements",)

    def __init__(self, statements):
        self.statements = statements

    def __str__(self):
        return str(CodeBlock("else", None, self.statements))


class ReturnExpression(cg.Expression):
    __slots__ = ("expression",)

    def __init__(self, expression):
        self.expression = expression

    def __str__(self):
        return str(f"return {self.expression}")


class VarAssignmentExpression(cpp.AssignmentExpression):
    def __init__(self, name, rhs):
        super().__init__(
            None, None, name, cg.RawExpression(rhs) if isinstance(rhs, str) else rhs
        )


class NamespaceStatement(cg.Statement):
    __slots__ = ("name", "statements")

    def __init__(self, name, statements):
        self.name = name
        self.statements = statements

    def __str__(self):
        return str(
            CodeBlock(
                f"namespace {self.name}",
                f"// namespace {self.name}",
                self.statements,
                False,
            )
        )


class StructStatement(cg.Statement):
    __slots__ = ("name", "statements", "packed", "ns")

    def __init__(
        self,
        name: Union[str, cg.MockObjClass],
        statements: list,
        use_ns: bool = True,
        packed: bool = False,
    ):
        self.ns = str(name).split("::")
        self.name = self.ns.pop()
        self.statements = statements
        self.packed = "PACKED" if packed else ""
        if use_ns:
            self.ns.insert(0, "esphome")
        else:
            self.ns = []
        self.ns.reverse()

    def __str__(self):
        res = CodeBlock(f"struct {self.name}", f"{self.packed};", self.statements)
        for ns in self.ns:
            res = NamespaceStatement(ns, res)
        return str(res)


class VarDeclaration(cg.Expression):
    __slots__ = ("type", "name", "rhs", "array_size")

    def __init__(self, type_, name, rhs, array_size: int = 0):
        self.type = type_
        self.name = name
        self.rhs = cg.safe_exp(rhs)
        self.array_size = array_size

    def __str__(self):
        if self.array_size:
            return f"{self.type} {self.name}[{self.array_size}]{{{self.rhs}}}"
        return f"{self.type} {self.name}{{{self.rhs}}}"


class ConditionalExperession(cg.Expression):
    __slots__ = ("condition", "true_expr", "false_expr")

    def __init__(self, condition, true_expr, false_expr):
        self.condition = cg.safe_exp(condition)
        self.true_expr = cg.safe_exp(true_expr)
        self.false_expr = cg.safe_exp(false_expr)

    def __str__(self):
        return f"{self.condition} ? {self.true_expr} : {self.false_expr}"


class IdentExperession(cg.Expression):
    __slots__ = ("expression",)

    def __init__(self, expression):
        self.expression = expression

    def __str__(self):
        return cpp.indent_all_but_first_and_last(str(self.expression))


class ConstAutoAssignmentExpression(cpp.AssignmentExpression):
    def __init__(self, name, rhs):
        super().__init__("const auto", "", name, rhs)
