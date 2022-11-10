from __future__ import annotations

import pathlib
from functools import cached_property
from copy import copy
from abc import ABC, abstractmethod
from collections.abc import Iterable
from functools import total_ordering

import javalang
import javalang.tree
import pprint
from typing import List, Union, Set, Optional, Dict, Type
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
        return self.probability < other.probability if self.probability != other.probability else self.weight < other.weight

    def __eq__(self, other: Report):
        return self.probability == other.probability and self.weight == other.weight

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

    def compare_parts(self, other: JavaEntity, attr: str) -> Report:
        if not isinstance(other, type(self)):
            raise TypeError("Cannot compare different types of JavaEntity!")
        report = Report(0, 0, self, other)
        self_attr_val = getattr(self, attr, None)
        other_attr_val = getattr(other, attr, None)
        if self_attr_val is None:
            raise ValueError(f"Instance of '{type(self)}' does not have attribute '{attr}'!")
        if isinstance(self_attr_val, Iterable):
            other_unused_values = copy(other_attr_val)
            if len(other_unused_values) > 0:
                for value in self_attr_val:
                    if len(other_unused_values) < 1:
                        break
                    max_match = max([value.compare(other_value) for other_value in other_unused_values])
                    report += max_match
                    if report.probability > definitions.threshold:
                        other_unused_values.remove(max_match.second)
                report += Report(0, len(other_unused_values) * 10, self, other)
        elif isinstance(self_attr_val, JavaEntity):
            another_report = self_attr_val.compare(other_attr_val)
            report += another_report
        else:
            raise ValueError(f"Cannot compare attribute '{attr}' of instance of '{type(self)}'!")
        return report


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
    def __init__(self, type_name: str, package: str, project: Project):
        super().__init__()
        self.project = project
        self.name: str = type_name
        self.package: str = package
        if not type_name:
            self.compatible_format = None
            return
        self.compatible_format: str = definitions.translation_dict.get(self.name)

    @cached_property
    def is_user_defined(self) -> bool:
        return True if self in self.project.user_types else False

    @cached_property
    def non_user_defined_types(self) -> List[JavaType]:
        return self.project.user_types.get(self)

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
            report = self.compare_parts(other, "non_user_defined_types")
            return report
        return Report(0, 10, self, other)

    def __eq__(self, other: JavaType):
        return self.name == other.name and self.package == other.package

    def __hash__(self):
        return self.name.__hash__() + self.package.__hash__()


class JavaVariable(JavaEntity):
    def __init__(self, variable_declaration: Union[javalang.tree.VariableDeclaration, javalang.tree.FieldDeclaration],
                 variable_declarator: javalang.tree.VariableDeclarator, java_file: JavaFile):
        super().__init__()
        self.java_file: JavaFile = java_file
        self.name: str = variable_declarator.name
        self.modifiers: List[JavaModifier] = [JavaModifier(m) for m in variable_declaration.modifiers]
        self.type_name: str = variable_declaration.type.name

    @cached_property
    def type(self) -> JavaType:
        return self.java_file.get_type(self.type_name)

    def compare(self, other: JavaVariable) -> Report:
        report = self.compare_parts(other, "modifiers")
        report += self.compare_parts(other, "type")
        return report


class JavaMethodInvocation:
    def __init__(self, method_invocation: javalang.tree.MethodInvocation, statement: JavaStatementBlock):
        self.statement: JavaStatementBlock = statement
        self.qualifier_str: str = method_invocation.qualifier
        self.name: str = method_invocation.member

    @cached_property
    def qualifier(self) -> Optional[JavaVariable]:
        if self.qualifier_str:
            qualifier = self.statement.java_method.get_local_variable(self.qualifier_str)
            if not qualifier:
                qualifier = self.statement.java_method.java_class.get_variable(self.qualifier_str)
            return qualifier
        else:
            return None

    @cached_property
    def method_referenced(self) -> Optional[JavaMethod]:
        qualifier = self.qualifier
        if not qualifier:
            local_methods = list(
                filter(lambda x: True if self.name == x.name else False, self.statement.java_method.java_class.methods))
            if len(local_methods) == 1:
                return local_methods[0]
        else:
            t = qualifier.type
            if t.is_user_defined:
                cls = list(filter(lambda x: True if x.name == t.name else False,
                                  self.statement.java_method.java_class.java_file.project.get_classes_in_package(
                                      t.package)))
                if len(cls) != 1:
                    return None
                m = list(filter(lambda x: True if x.name == self.name else False, cls[0].methods))
                if len(m) != 1:
                    return None
                return m[0]


class JavaStatementBlock(JavaEntity):
    def __init__(self, statement: javalang.tree.Statement, java_method: JavaMethod):
        super().__init__()
        self.name: str = f"Statement {statement.position}"
        self.java_method: JavaMethod = java_method
        self.local_variables: List[JavaVariable] = []
        for declaration in self._search_for_type(statement, javalang.tree.VariableDeclaration):
            for declarator in declaration.declarators:
                var = JavaVariable(declaration, declarator, self.java_method.java_class.java_file)
                self.local_variables.append(var)

        self.invoked_methods: List[JavaMethodInvocation] = [JavaMethodInvocation(m, self) for m in
                                                            self._search_for_type(statement,
                                                                                  javalang.tree.MethodInvocation)]
        self.parts: Dict[Type, int] = self._tree_to_dict(statement)
        for statement_block in self.raw_statements_from_invocations:
            self.parts.update(self._tree_to_dict(statement_block))

    @cached_property
    def raw_statements_from_invocations(self) -> List[javalang.tree.Node]:
        ans = []
        for invoked_method in self.invoked_methods:
            m = invoked_method.method_referenced
            if m is not None:
                ans.extend(m.raw_statement_blocks)
        return ans

    def compare(self, other: JavaStatementBlock) -> Report:
        report = Report(0, 0, self, other)
        for node_type in self.parts:
            self_occurrences = self.parts[node_type]
            other_occurrences = other.parts.get(node_type, 0)
            if other_occurrences > 0:
                report += Report(
                    int(100 - 100 * (
                                abs(self_occurrences - other_occurrences) / (self_occurrences + other_occurrences))),
                    10, self, other)
            else:
                backup_node_type = definitions.node_translation_dict.get(node_type, None)
                if backup_node_type is not None:
                    other_occurrences = other.parts.get(backup_node_type, 0)
                    if other_occurrences > 0:
                        report += Report(int(50 - 50 * (
                                abs(self_occurrences - other_occurrences) / (self_occurrences + other_occurrences))),
                                         10, self, other)
                else:
                    report += Report(0, 10, self, other)
        return report

    def _search_for_type(self, statement: javalang.tree.Node, block_type: Type) -> List:  # TODO use once
        ans = []
        for attribute in getattr(statement, "attrs", []):
            child = getattr(statement, attribute, None)
            if isinstance(child, block_type):
                ans.append(child)
            if isinstance(child, javalang.tree.Node):
                ans.extend(self._search_for_type(child, block_type))
        return ans

    def _tree_to_dict(self, tree: javalang.tree.Node) -> Dict[Type, int]:
        ans: Dict[Type, int] = {}
        node_type = type(tree)
        if node_type in ans.keys():
            ans.update({node_type: ans.get(node_type) + 1})
        else:
            ans.update({node_type: 1})
        for attribute in getattr(tree, "attrs", []):
            child = getattr(tree, attribute, None)
            if not isinstance(child, javalang.tree.Node):
                continue
            ans.update(self._tree_to_dict(child))
        return ans


class JavaParameter(JavaEntity):
    def __init__(self, parameter_name: str, parameter_type: str, method: JavaMethod):
        super().__init__()
        self.name: str = parameter_name
        self.type_string: str = parameter_type
        self.method: JavaMethod = method

    @cached_property
    def type(self):
        return self.method.java_class.java_file.get_type(self.type_string)

    def compare(self, other: JavaParameter) -> Report:
        return self.compare_parts(other, "type")


class JavaMethod(JavaEntity):
    def __init__(self, java_method: javalang.tree.MethodDeclaration, java_class: JavaClass):
        super().__init__()
        self.java_method: javalang.tree.MethodDeclaration = java_method
        self.name: str = self.java_method.name
        self.java_class: JavaClass = java_class
        self.raw_statement_blocks: List[javalang.tree.Node] = java_method.body
        self.statement_blocks: List[JavaStatementBlock] = []
        self.return_type_str: str = getattr(java_method.return_type, "name", None)
        self.modifiers: List[JavaModifier] = [JavaModifier(m) for m in java_method.modifiers]
        self.arguments: List[JavaParameter] = []
        self.handles_exceptions: bool = True if java_method.throws is not None else False
        for parameter in self.java_method.parameters:
            argument = JavaParameter(parameter.name, parameter.type.name, self)
            self.arguments.append(argument)

    def continue_init(self):
        for block in self.java_method.body:
            self.statement_blocks.append(JavaStatementBlock(block, self))

    @cached_property
    def local_variables(self) -> List[JavaVariable]:
        ans = []
        for statement_block in self.statement_blocks:
            ans.extend(statement_block.local_variables)
        return ans

    @cached_property
    def return_type(self):
        return self.java_class.java_file.get_type(self.return_type_str)

    def compare(self, other: JavaMethod) -> Report:
        report = self.compare_parts(other, "return_type")
        report += self.compare_parts(other, "arguments")
        if report.probability > definitions.method_interface_threshold:
            report += self.compare_parts(other, "statement_blocks")
        return report

    def get_local_variable(self, var_name: str) -> Optional[JavaVariable]:
        ans = list(filter(lambda x: True if x.name == var_name else False, self.local_variables))
        if len(ans) > 0:
            return ans[-1]
        return None


class JavaClass(JavaEntity):
    def __init__(self, java_class: javalang.tree.ClassDeclaration, java_file: JavaFile):
        super().__init__()
        self.java_class: javalang.tree.ClassDeclaration = java_class
        self.java_file: JavaFile = java_file
        self.name: str = java_class.name
        self.methods: List[JavaMethod] = []
        self.variables: List[JavaVariable] = []
        self.modifiers: List[JavaModifier] = [JavaModifier(m) for m in java_class.modifiers]

    def compare(self, other: JavaClass) -> Report:
        report = self.compare_parts(other, "modifiers")
        report += self.compare_parts(other, "variables")
        report += self.compare_parts(other, "methods")
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
                    self.java_file.project.get_class(variable.type.package,
                                                     variable.type.name).get_non_user_defined_types())
        return ans

    def get_variable(self, var_name: str):
        ans = list(filter(lambda x: True if x.name == var_name else False, self.variables))
        if len(ans) > 0:
            return ans[-1]
        return None

    def continue_init(self):
        for field in self.java_class.fields:
            for declarator in field.declarators:
                if isinstance(declarator, javalang.tree.VariableDeclarator):
                    variable = JavaVariable(field, declarator, self.java_file)
                    variable.modifiers = [JavaModifier(m) for m in field.modifiers]
                    self.variables.append(variable)
        for method in self.java_class.methods:
            self.methods.append(JavaMethod(method, self))


class JavaFile(JavaEntity):
    def __init__(self, path: Union[str, pathlib.Path], project: Project):
        super().__init__()
        self.path: pathlib.Path = pathlib.Path(path) if not isinstance(path, pathlib.Path) else path
        self.name: str = self.path.name
        self.name_without_appendix: str = self.name.replace(".java", '')
        compilation_unit = utils.get_ast(path)
        self.project: Project = project
        self.package: str = compilation_unit.package.name
        self.wildcard_imports = [i.path for i in compilation_unit.imports if i.wildcard]
        self.imports: List[str] = [i.path for i in compilation_unit.imports if not i.wildcard]
        self.import_types: List[str] = [i.split('.')[-1] for i in self.imports]
        self.classes: List[JavaClass] = [JavaClass(body, self) for body in compilation_unit.types]
        for cls in self.classes:
            self.project.user_types.update({JavaType(cls.name, self.package, self.project): []})

    def compare(self, other: JavaFile) -> Report:
        report = self.compare_parts(other, "classes")
        return report

    def get_type(self, type_name: str) -> JavaType:
        if not type_name:
            return JavaType(None, None, self.project)
        ans = self.project.get_user_type(self.package, type_name)
        if ans is not None:
            return ans
        for imp in self.imports:
            if re.match(rf"^.*\.{type_name}$", imp) is not None:
                ans = self.project.get_user_type(imp.replace(f".{type_name}", ''), type_name)
                if ans is not None:
                    return ans
                return JavaType(type_name, imp.replace(f".{type_name}", ''), self.project)
        for wildcard_import in self.wildcard_imports:
            ans = self.project.get_user_type(wildcard_import, type_name)
            if ans is not None:
                return ans
        return JavaType(type_name, "", self.project)


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
        self.user_types: Dict[JavaType, List[JavaType]] = {}
        self.java_files: List[JavaFile] = []
        java_files = utils.get_java_files(self.path)
        for file in java_files:
            java_file = JavaFile(file, self)
            self.java_files.append(java_file)
        for file in self.java_files:
            for w_import in file.wildcard_imports:
                file.import_types.extend(f.name_without_appendix for f in self.get_files_in_package(w_import))
        for cls in self.classes:
            cls.continue_init()
        for t in self.user_types.keys():
            type_class = self.get_class(t.package, t.name)
            self.user_types.update({t: type_class.get_non_user_defined_types()})
        for method in self.methods:
            method.continue_init()

    def get_file(self, package: str, class_name: str) -> Optional[JavaFile]:
        files = list(
            filter(lambda x: True if x.name_without_appendix == class_name and x.package == package else False,
                   self.java_files))
        if len(files) == 1:
            return files[0]
        return None

    def get_files_in_package(self, package: str) -> List[JavaFile]:
        return list(filter(lambda x: True if x.package == package else False, self.java_files))

    def get_classes_in_package(self, package: str) -> List[JavaClass]:
        ans = []
        for file in self.get_files_in_package(package):
            ans.extend(file.classes)
        return ans

    def get_class(self, package: str, class_name: str) -> Optional[JavaClass]:
        found_classes = list(filter(lambda x: True if x.name == class_name else False, self.classes))
        if len(found_classes) == 1:
            return found_classes[0]
        print(f"Project.get_class: Cannot find {package}.{class_name}!")
        return None

    def get_user_type(self, package: str, class_name: str) -> Optional[JavaType]:
        types = list(
            filter(lambda x: True if x.package == package and x.name == class_name else False, self.user_types.keys())
        )
        if len(types) == 1:
            return types[0]
        return None

    @cached_property
    def classes(self):
        ans = []
        for file in self.java_files:
            ans.extend(file.classes)
        return ans

    @cached_property
    def methods(self):
        ans = []
        for cl in self.classes:
            ans.extend(cl.methods)
        return ans

    def compare(self, other: Project) -> Report:
        report = self.compare_parts(other, "java_files")
        return report
