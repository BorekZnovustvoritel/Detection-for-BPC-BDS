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
    def __init__(self, probability: int, weight: int, first: JavaEntity, second: JavaEntity):
        self.probability: int = probability
        self.weight: int = weight
        self.first: JavaEntity = first
        self.second: JavaEntity = second
        self.child_reports: List[Report] = []

    def __lt__(self, other: Report):
        return self.probability < other.probability

    def __eq__(self, other: Report):
        return self.probability == other.probability

    def __repr__(self):
        return f"< Report, probability: {self.probability}, comparing entities: {self.first.name}, " \
               f"{self.second.name}, Child reports: {self.child_reports}>"

    def __add__(self, other: Report):
        return Report(((self.probability * self.weight + other.probability * other.weight) //
                       (self.weight + other.weight)), (self.weight + other.weight) // 2, self.first, self.second)


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

class JavaModifier(JavaEntity):
    def __init__(self, name: str):
        super().__init__()
        self.name: str = name

    def compare(self, other: JavaModifier) -> Report:
        if self.name == other.name:
            return Report(100, 10, self, other)
        else:
            return Report(0, 10, self, other)


class JavaMethod(JavaEntity):
    def __init__(self, java_method: javalang.tree.MethodDeclaration, java_class: JavaClass):
        # self.java_method: javalang.tree.MethodDeclaration = java_method
        super().__init__()
        self.java_class: JavaClass = java_class
        # self.body_blocks: list[javalang.tree.Expression] = []
        # self.local_variables: list[JavaVariable] = []
        self.return_type: JavaType = JavaType(getattr(java_method.return_type, "name", None), java_class)
        self.modifiers: List[JavaModifier] = [JavaModifier(m) for m in java_method.modifiers]
        self.arguments: List[JavaVariable] = []
        for parameter in java_method.parameters:
            argument = JavaVariable(parameter)
            argument.type = JavaType(parameter.type.name, java_class)
            argument.modifiers = [JavaModifier(m) for m in parameter.modifiers]
            self.arguments.append(argument)
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
        report = Report(0, 0, self, other)
        for argument in self.arguments:
            max_cmp = max([argument.compare(other_argument) for other_argument in other.arguments])
            report.child_reports.append(max_cmp)
            report += max_cmp
        return_type_report = self.return_type.compare(other.return_type)
        report += return_type_report
        report.child_reports.append(return_type_report)
        return report


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
        self.modifiers: List[JavaModifier] = [JavaModifier(m) for m in java_class.modifiers]
        for field in java_class.fields:
            # self.fields.append(JavaField(field))
            for declarator in field.declarators:
                if isinstance(declarator, javalang.tree.VariableDeclarator):
                    variable = JavaVariable(declarator)
                    variable.type = JavaType(field.type.name, self)
                    variable.modifiers = [JavaModifier(m) for m in field.modifiers]
                    self.variables.append(variable)
        # self.variables.sort(key=lambda x: getattr(x.type, 'type_name', None))
        for method in java_class.methods:
            self.methods.append(JavaMethod(method, self))

    def compare(self, other: JavaClass) -> Report:
        """Returns value between 0 and 100 based on the likelihood of plagiarism."""
        report = Report(0, 0, self, other)
        for method in self.methods:
            method_report = max([method.compare(other_method) for other_method in other.methods])
            report += method_report
            report.child_reports.append(method_report)
        for variable in self.variables:
            variable_report = max([variable.compare(other_variable) for other_variable in other.variables])
            report += variable_report
            report.child_reports.append(variable_report)
        for modifier in self.modifiers:
            modifier_report = max([modifier.compare(other_modifier) for other_modifier in other.modifiers])
            report += modifier_report
            report.child_reports.append(modifier_report)
        return report


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
        report = Report(0, 0, self, other)
        for cl in self.classes:
            class_report = max([cl.compare(other_class) for other_class in other.classes])
            report += class_report
            report.child_reports.append(class_report)
        return report


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
            return Report(100, 1, self, other)
        if self.name == other.name:
            return Report(100, 10, self, other)
        elif (self.compatible_format == other.name and other.name is not None) \
                or (self.name == other.compatible_format and self.name is not None):
            return Report(75, 10, self, other)
        elif self.compatible_format is not None and self.compatible_format == other.compatible_format:
            return Report(50, 10, self, other)
        return Report(0, 10, self, other)


class JavaVariable(JavaEntity):
    def __init__(self, java_variable: javalang.tree.VariableDeclarator):
        # print(f"Variable input type: {type(java_variable)}")
        # pp.pprint(java_variable.__dict__)
        # self.java_variable: javalang.tree.VariableDeclarator = java_variable
        super().__init__()
        self.name: str = java_variable.name
        self.type: JavaType = None
        self.modifiers: List[JavaModifier] = None

    def compare(self, other: JavaVariable) -> Report:
        report = Report(0, 0, self, other)
        type_compare = self.type.compare(other.type)
        report += type_compare
        report.child_reports.append(type_compare)   # TODO
        for modifier in self.modifiers:
            modifier_report = max([modifier.compare(other_modifier) for other_modifier in other.modifiers])
            report += modifier_report
            report.child_reports.append(modifier_report)
        return report


project = Project("/home/lmayo/Dokumenty/baklazanka/java_test/Projekt_BDS_3/")
file1 = [f for f in project.root_path.glob("**/App.java")][0]
file2 = [f for f in project.root_path.glob("**/App2.java")][0]
project_files = [f for f in filter(lambda x: True if x.path in (file1, file2) else False, project.java_files)]
print([f.path for f in project_files])
print(project_files[0].compare(project_files[1]))

