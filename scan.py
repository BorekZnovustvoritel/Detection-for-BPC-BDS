from __future__ import annotations

import pathlib
from abc import ABC, abstractmethod
from functools import total_ordering

import javalang
import javalang.tree
import pprint
from typing import List, Union, Set, Optional
import re

import definitions
import utils

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
        report = Report(((self.probability * self.weight + other.probability * other.weight) //
                         (self.weight + other.weight)), (self.weight + other.weight), self.first, self.second)
        if isinstance(self.first, type(other.first)) and isinstance(self.second, type(other.second)):
            report.child_reports.extend(self.child_reports + other.child_reports)
        else:
            report.child_reports.extend(self.child_reports)
            report.child_reports.append(other)
        return report


class JavaEntity(ABC):

    def __init__(self):
        self.name: str = ""

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.__dict__}>"

    @abstractmethod
    def compare(self, other: JavaEntity) -> Report:
        pass


class JavaModifier(JavaEntity):
    def __init__(self, name: str):
        super().__init__()
        self.name: str = name

    def compare(self, other: JavaModifier) -> Report:
        if self.name == other.name:
            return Report(100, 10, self, other)
        else:
            return Report(0, 10, self, other)


class JavaType(JavaEntity):
    def __init__(self, type_name: str, java_class: JavaClass):
        super().__init__()
        self.java_class: JavaClass = java_class
        self.is_user_defined: bool = False
        self.name: str = type_name
        if not type_name:
            self.compatible_format = None
            return
        self.compatible_format: str = definitions.translation_dict.get(self.name)
        self.package = ""
        for imp in self.java_class.java_file.imports:
            if re.match(f"^.*{self.name}$", imp) is not None:
                self.package = imp.replace(f".{type_name}", '')
                if self.package in self.java_class.java_file.project.packages:
                    self.is_user_defined = True
                else:
                    self.is_user_defined = False
                break
        if self.name == self.java_class.name:
            self.is_user_defined = True
        self.non_user_defined_types: List[JavaType] = []
        if self.is_user_defined:
            if self not in self.java_class.java_file.project.user_types:
                self.java_class.java_file.project.user_types.append(self)

    def compare(self, other: JavaType) -> Report:
        if not self.name and not other.name:
            return Report(100, 1, self, other)
        if self.is_user_defined != other.is_user_defined:
            return Report(0, 10, self, other)
        if not self.is_user_defined:
            if self.name == other.name:
                return Report(100, 10, self, other)
            elif (self.compatible_format == other.name and other.name is not None) \
                    or (self.name == other.compatible_format and self.name is not None):
                return Report(75, 10, self, other)
            elif self.compatible_format is not None and self.compatible_format == other.compatible_format:
                return Report(50, 10, self, other)
        else:
            report = Report(0, 0, self, other)
            other_initialized_type = other.java_class.java_file.project.get_user_type(other.package, other.name)
            for t in self.java_class.java_file.project.get_user_type(self.package, self.name).non_user_defined_types:
                subtype_report = max([t.compare(o) for o in other_initialized_type.non_user_defined_types])
                report += subtype_report
            return report
        return Report(0, 10, self, other)

    def __eq__(self, other: JavaType):
        return self.name == other.name and self.package == other.package


class JavaVariable(JavaEntity):
    def __init__(self, java_variable: javalang.tree.VariableDeclarator):
        super().__init__()
        self.name: str = java_variable.name
        self.type: JavaType = None
        self.modifiers: List[JavaModifier] = None

    def compare(self, other: JavaVariable) -> Report:
        report = Report(0, 0, self, other)
        type_compare = self.type.compare(other.type)
        report += type_compare
        if len(other.modifiers) > 0:
            for modifier in self.modifiers:
                modifier_report = max([modifier.compare(other_modifier) for other_modifier in other.modifiers])
                report += modifier_report
        return report


class JavaStatementBlock(JavaEntity):
    def __init__(self, statement: javalang.tree.Statement, method: JavaMethod, name: str):
        super().__init__()
        self.name: str = name
        self.java_method: JavaMethod = method
        self.statements: Set[javalang.tree.Statement] = set()

    def compare(self, other: JavaStatementBlock) -> Report:
        pass


class JavaMethod(JavaEntity):
    def __init__(self, java_method: javalang.tree.MethodDeclaration, java_class: JavaClass):
        # self.java_method: javalang.tree.MethodDeclaration = java_method
        super().__init__()
        self.java_class: JavaClass = java_class
        # self.body_blocks: list[javalang.tree.Expression] = []
        self.return_type: JavaType = JavaType(getattr(java_method.return_type, "name", None), java_class)
        self.modifiers: List[JavaModifier] = [JavaModifier(m) for m in java_method.modifiers]
        self.arguments: List[JavaVariable] = []
        for parameter in java_method.parameters:
            argument = JavaVariable(parameter)
            argument.type = JavaType(parameter.type.name, java_class)
            argument.modifiers = [JavaModifier(m) for m in parameter.modifiers]
            self.arguments.append(argument)
        self.name: str = java_method.name

    def compare(self, other: JavaMethod) -> Report:
        report = Report(0, 0, self, other)
        if len(other.arguments) > 0:
            for argument in self.arguments:
                max_cmp = max([argument.compare(other_argument) for other_argument in other.arguments])
                report += max_cmp
        return_type_report = self.return_type.compare(other.return_type)
        report += return_type_report
        return report


class JavaClass(JavaEntity):
    def __init__(self, java_class: javalang.tree.ClassDeclaration, java_file: JavaFile):
        super().__init__()
        self.java_file: JavaFile = java_file
        self.name: str = java_class.name
        # self.fields = []
        self.methods: List[JavaMethod] = []
        self.variables: List[JavaVariable] = []
        self.modifiers: List[JavaModifier] = [JavaModifier(m) for m in java_class.modifiers]
        for field in java_class.fields:
            for declarator in field.declarators:
                if isinstance(declarator, javalang.tree.VariableDeclarator):
                    variable = JavaVariable(declarator)
                    variable.type = JavaType(field.type.name, self)
                    variable.modifiers = [JavaModifier(m) for m in field.modifiers]
                    self.variables.append(variable)
        for method in java_class.methods:
            self.methods.append(JavaMethod(method, self))

    def compare(self, other: JavaClass) -> Report:
        report = Report(0, 0, self, other)
        if len(other.methods) > 0:
            for method in self.methods:
                method_report = max([method.compare(other_method) for other_method in other.methods])
                report += method_report
        if len(other.variables) > 0:
            for variable in self.variables:
                variable_report = max([variable.compare(other_variable) for other_variable in other.variables])
                report += variable_report
        if len(other.modifiers) > 0:
            for modifier in self.modifiers:
                modifier_report = max([modifier.compare(other_modifier) for other_modifier in other.modifiers])
                report += modifier_report
        return report

    def get_non_user_defined_types(self) -> List[JavaType]:
        ans = []
        for variable in self.variables:
            if not variable.type.is_user_defined:
                ans.append(variable)
            elif variable.type.name == self.name:
                continue  # TODO is this better or Type("this", self)?
            else:
                ans.extend(
                    self.java_file.project.get_class(variable.type.package, variable.type.name).get_non_user_defined_types())
        return ans


class JavaFile(JavaEntity):
    def __init__(self, path: Union[str, pathlib.Path], project: Project):
        super().__init__()
        self.path: pathlib.Path = pathlib.Path(path) if not isinstance(path, pathlib.Path) else path
        self.name: str = self.path.name
        self.name_without_appendix: str = self.name.replace(".java", '')
        compilation_unit = utils.get_ast(path)
        self.project: Project = project
        self.package: str = compilation_unit.package.name
        self.imports: List[str] = [i.path for i in compilation_unit.imports]
        self.import_types: List[str] = [i.split('.')[-1] for i in self.imports]
        self.classes: List[JavaClass] = [JavaClass(body, self) for body in compilation_unit.types]

    def compare(self, other: JavaFile) -> Report:
        report = Report(0, 0, self, other)
        if len(other.classes) > 0:
            for cl in self.classes:
                class_report = max(cl.compare(other_class) for other_class in other.classes)
                report += class_report
        return report


class Project(JavaEntity):
    def __init__(self, path: Union[str, pathlib.Path]):
        super().__init__()
        self.path: pathlib.Path = None
        if not isinstance(path, pathlib.Path):
            self.path = pathlib.Path(path)
        else:
            self.path = path
        if not self.path.exists():
            raise ValueError(f"Given path does not exist: {path}")
        self.name = self.path.name
        self.root_path = utils.get_user_project_root(self.path)
        self.packages: Set[str] = utils.get_packages(self.path)
        self.user_types: List[JavaType] = []
        self.java_files: List[JavaFile] = []
        java_files = utils.get_java_files(self.path)
        for file in java_files:
            self.java_files.append(JavaFile(file, self))
        for t in self.user_types:
            type_class = self.get_class(t.package, t.name)
            t.non_user_defined_types.extend(type_class.get_non_user_defined_types())

    def get_file(self, package: str, class_name: str) -> Optional[JavaFile]:
        files = list(
                 filter(lambda x: True if x.name_without_appendix == class_name and x.package == package else False,
                        self.java_files))
        if len(files) == 1:
            return files[0]
        print(f"Project.get_file: Cannot find {package}.{class_name}!")
        return None

    def get_class(self, package: str, class_name: str) -> Optional[JavaClass]:
        classes = getattr(self.get_file(package, class_name), "classes", None)
        if not classes:
            return None
        found_classes = list(filter(lambda x: True if x.name == class_name else False, classes))
        if len(found_classes) == 1:
            return found_classes[0]
        print(f"Project.get_class: Cannot find {package}.{class_name}!")
        return None

    def get_user_type(self, package: str, class_name: str) -> Optional[JavaType]:
        types = list(
            filter(lambda x: True if x.package == package and x.name == class_name else False, self.user_types)
        )
        if len(types) == 1:
            return types[0]
        print(f"Project.get_user_type: Cannot find {package}.{class_name}!")
        return None

    @property
    def classes(self):
        ans = []
        for file in self.java_files:
            ans.extend(file.classes)
        return ans

    @property
    def methods(self):
        ans = []
        for cl in self.classes:
            ans.extend(cl.methods)
        return ans

    def compare(self, other: Project) -> Report:
        report = Report(0, 0, self, other)
        unused_files: List[JavaFile] = self.java_files
        other_unused_files: List[JavaFile] = other.java_files
        for package in self.packages:
            package_name = package.split(".")[-1]
            files_in_package = list(filter(lambda x: True if package_name == x.package.split(".")[-1] else False, unused_files))
            files_to_compare = list(filter(lambda x: True if package_name == x.package.split(".")[-1] else False, other_unused_files))
            if len(files_to_compare) > 0:
                for file in files_in_package:
                    unused_files.remove(file)
                    max_report = max([file.compare(other_file) for other_file in files_to_compare])
                    report += max_report
                    if max_report.probability > definitions.treshold and max_report.second in other_unused_files:
                        other_unused_files.remove(max_report.second)
        for file in unused_files:
            report += max([file.compare(other_file) for other_file in other_unused_files])
        return report

