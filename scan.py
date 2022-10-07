from __future__ import annotations

import pathlib
from abc import ABC, abstractmethod
from functools import total_ordering

import javalang
import javalang.tree
import pprint
from typing import List, Union, Set
import re

import definitions

pp = pprint.PrettyPrinter(indent=4)


@total_ordering
class Report:
    def __init__(self, probability: int, first: JavaEntity, second: JavaEntity):
        self.probability: int = probability
        self.first: JavaEntity = first
        self.second: JavaEntity = second

    def __lt__(self, other: Report):
        return self.probability < other.probability

    def __eq__(self, other: Report):
        return self.probability == other.probability

    def __repr__(self):
        return f"< Report, probability: {self.probability}, comparing entities: {self.first.name}, {self.second.name}>"


class JavaEntity(ABC):

    def __init__(self):
        self.name: str = ""

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.__dict__}>"

    @abstractmethod
    def compare(self, other: JavaEntity) -> Report:
        pass


# class JavaField:
#     def __init__(self, java_field: javalang.tree.FieldDeclaration):
#         #print(f"Field input type: {type(java_field)}")
#         self.java_field = java_field
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"
#
#
# class JavaMethodInvocation:
#     def __init__(self, java_method_invocation: javalang.tree.MethodInvocation):
#         self.java_method_invocation: javalang.tree.MethodInvocation = java_method_invocation
#         self.arguments: List[javalang.tree.Expression] = java_method_invocation.arguments   # TODO: use my types
#         self.method_name = java_method_invocation.member
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"
#
#
# class JavaLocalVariable(JavaVariable):
#     def __init__(self, java_variable: javalang.tree.VariableDeclarator):
#         super().__init__(java_variable)
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"
#
#
# class JavaAssignment:
#     def __init__(self, java_assignment: javalang.tree.Assignment):
#         self.java_assignment: javalang.tree.Assignment = java_assignment
#         self.variable_name: str = java_assignment.expressionl.member
#         self.value: javalang.tree.Expression = java_assignment.value    # TODO: use my types
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"
#
#
# class JavaExpression:
#     def __init__(self, java_statement: javalang.tree.StatementExpression):
#         self.java_statement: javalang.tree.StatementExpression = java_statement
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"


class JavaMethod(JavaEntity):
    def __init__(self, java_method: javalang.tree.MethodDeclaration, java_class: JavaClass):
        # print(f"Method input type: {type(java_method)}")
        # self.java_method: javalang.tree.MethodDeclaration = java_method
        super().__init__()
        self.java_class: JavaClass = java_class
        # self.body_blocks: list[javalang.tree.Expression] = []
        # self.local_variables: list[JavaVariable] = []
        self.return_type: JavaType = JavaType(getattr(java_method.return_type, "name", None), java_class)
        self.arguments: List[JavaVariable] = []
        for parameter in java_method.parameters:
            argument = JavaVariable(parameter)
            argument.type = JavaType(parameter.type.name, java_class)
            argument.modifiers = parameter.modifiers
            self.arguments.append(argument)
        # self.arguments.sort(key=lambda x: getattr(x.type, 'type_name', None))
        self.name: str = java_method.name
        # self.assignments: list = [] #TODO
        # self.method_invocations: list = [] #TODO
        # for statement in java_method.body:
        #     if isinstance(statement, javalang.tree.TryStatement):
        #         self.body_blocks.extend(statement.block)
        #     else:
        #         self.body_blocks.append(statement)
        # for body_block in self.body_blocks:
        #     if isinstance(body_block, javalang.tree.LocalVariableDeclaration):
        #         self.local_variables.append(body_block)
        #     elif isinstance(body_block, javalang.tree.StatementExpression):
        #         if isinstance(body_block.expression, javalang.tree.Assignment):
        #             self.assignments.append(body_block.expression)
        #         elif isinstance(body_block.expression, javalang.tree.MethodInvocation):
        #             self.method_invocations.append(body_block.expression)
        #     else:
        #         pp.pprint(f"{type(body_block)} {body_block.__dict__}")
        #         raise ValueError(f"Unknown Body_block type: {type(body_block)}")

    def compare(self, other: JavaMethod) -> Report:
        score = 0
        for argument in self.arguments:
            max_cmp = 0
            for other_argument in other.arguments:
                max_cmp = max(max_cmp, argument.compare(other_argument).probability)
            score += max_cmp
        score //= (len(self.arguments))
        score //= 2
        if not self.return_type.name and not other.return_type.name:
            score += 50
        else:
            score += self.return_type.compare(other.return_type).probability // 2
        print(f"Comparing methods: {self.name}, {other.name}. Score: {score}")
        return Report(score, self, other)


class JavaClass(JavaEntity):
    def __init__(self, java_class: javalang.tree.ClassDeclaration, java_file: JavaFile):
        # print(f"Class input type: {type(java_class)}")
        # pp.pprint(java_class.__dict__)
        # self.java_class: javalang.tree.ClassDeclaration = java_class
        super().__init__()
        self.java_file: JavaFile = java_file
        self.name: str = java_class.name
        # self.fields = []
        self.methods: List[JavaMethod] = []
        self.variables: List[JavaVariable] = []
        for field in java_class.fields:
            # self.fields.append(JavaField(field))
            for declarator in field.declarators:
                if isinstance(declarator, javalang.tree.VariableDeclarator):
                    variable = JavaVariable(declarator)
                    variable.type = JavaType(field.type.name, self)
                    variable.modifiers = field.modifiers
                    self.variables.append(variable)
        # self.variables.sort(key=lambda x: getattr(x.type, 'type_name', None))
        for method in java_class.methods:
            self.methods.append(JavaMethod(method, self))

    def compare(self, other: JavaClass) -> Report:
        """Returns value between 0 and 100 based on the likelihood of plagiarism."""
        score = 0
        for method in self.methods:
            max_cmp = 0
            for other_method in other.methods:
                max_cmp = max(max_cmp, method.compare(other_method).probability)
            score += max_cmp
        score //= len(self.methods)
        score //= 2
        temp_score = 0
        for variable in self.variables:
            max_cmp = 0
            for other_variable in other.variables:
                max_cmp = max(max_cmp, variable.compare(other_variable).probability)
            temp_score += max_cmp
        temp_score //= len(self.variables)
        temp_score //= 2
        return Report(score + temp_score, self, other)


class JavaFile(JavaEntity):
    def __init__(self, path: Union[str, pathlib.Path], project: Project):
        super().__init__()
        self.path: pathlib.Path = pathlib.Path(path) if not isinstance(path, pathlib.Path) else path
        self.name = self.path.name
        with open(self.path, 'r') as inp_file:
            lines = ''.join(inp_file.readlines())
        compilation_unit = javalang.parse.parse(lines)
        self.project: Project = project
        self.package: str = compilation_unit.package.name
        self.imports: List[str] = [i.path for i in compilation_unit.imports]
        self.import_types: List[str] = [i.split('.')[-1] for i in self.imports]
        self.classes: List[JavaClass] = [JavaClass(body, self) for body in compilation_unit.types]

    def compare(self, other: JavaFile) -> Report:
        """Returns value between 0 and 100 based on the likelihood of plagiarism."""
        score = 0
        for cl in self.classes:
            max_cmp = 0
            for other_cl in other.classes:
                max_cmp = max(max_cmp, cl.compare(other_cl).probability)
            score += max_cmp
        score //= len(self.classes)
        return Report(score, self, other)


class Project(JavaEntity):
    def compare(self, other: JavaEntity) -> Report:
        pass    # TODO

    def __init__(self, path: str):
        super().__init__()
        self.path: pathlib.Path = pathlib.Path(path)
        if not self.path.exists():
            raise ValueError(f"Given path does not exist: {path}")
        self.name = self.path.name
        root_paths = [d for d in self.path.glob("**/src/main/java")]
        if len(root_paths) > 2:
            raise FileExistsError(f"Found too many project roots: {root_paths}")
        self.root_path = root_paths[0]
        self.packages: Set[str] = set()
        self.java_files: List[JavaFile] = []
        java_files = [f for f in self.root_path.glob("**/*.java")]
        for java_file in java_files:
            self.packages.add((str(java_file.parent).replace(str(self.root_path) + '/', '')).replace('/', '.'))
        for java_file in java_files:
            self.java_files.append(JavaFile(java_file, self))


class JavaType(JavaEntity):
    def __init__(self, type_name: str, java_class: JavaClass):
        super().__init__()
        self.java_class: JavaClass = java_class
        self.is_user_defined: bool = False
        self.name: str = type_name
        if not type_name:
            return
        self.compatible_format: str = definitions.translation_dict.get(self.name)
        for imp in self.java_class.java_file.imports:
            if re.match(f"^.*{self.name}$", imp) is not None:
                package = imp.replace(f".{type_name}", '')
                if package in self.java_class.java_file.project.packages:
                    self.is_user_defined = True
                else:
                    self.is_user_defined = False
                break
        if self.name == self.java_class.name:
            self.is_user_defined = True

    def compare(self, other: JavaType) -> Report:
        if not self.name and not other.name:
            return Report(50, self, other)
        if self.name == other.name:
            return Report(100, self, other)
        elif (self.compatible_format == other.name and other.name is not None) \
                or (self.name == other.compatible_format and self.name is not None):
            return Report(75, self, other)
        elif self.compatible_format is not None and self.compatible_format == other.compatible_format:
            return Report(50, self, other)
        return Report(0, self, other)


class JavaVariable(JavaEntity):
    def __init__(self, java_variable: javalang.tree.VariableDeclarator):
        # print(f"Variable input type: {type(java_variable)}")
        # pp.pprint(java_variable.__dict__)
        # self.java_variable: javalang.tree.VariableDeclarator = java_variable
        super().__init__()
        self.name: str = java_variable.name
        self.type: JavaType = None
        self.modifiers: set = None

    def compare(self, other: JavaVariable) -> Report:
        type_compare = self.type.compare(other.type).probability
        if type_compare >= 75 and self.modifiers == other.modifiers:
            return Report(100, self, other)
        if type_compare >= 50 and self.modifiers == other.modifiers:
            return Report(75, self, other)
        score = 0
        for modifier in self.modifiers:
            if modifier in other.modifiers:
                score += 100 // len(self.modifiers)
        score += type_compare
        return Report(score // 2, self, other)


project = Project("/home/lmayo/Dokumenty/baklazanka/java_test/Projekt_BDS_3/")
file1 = [f for f in project.root_path.glob("**/App.java")][0]
file2 = [f for f in project.root_path.glob("**/Main.java")][0]
project_files = [f for f in filter(lambda x: True if x.path in (file1, file2) else False, project.java_files)]
print([f.path for f in project_files])
print(project_files[0].compare(project_files[1]))

