from __future__ import annotations

import pathlib
from functools import cached_property
from math import sqrt
from abc import ABC, abstractmethod
from functools import total_ordering

import javalang
import javalang.tree
from typing import List, Union, Set, Optional, Dict, Type
import re

from detection.definitions import translation_dict, node_translation_dict, thorough_scan
from detection.thresholds import skip_attr_list_threshold, method_interface_threshold
from detection.utils import get_ast, get_user_project_root, get_packages, get_java_files


@total_ordering
class Report:
    """Pairwise comparison result. Used as Model from the M-V-C architecture."""

    def __init__(
        self, probability: int, weight: int, first: JavaEntity, second: JavaEntity
    ):
        self.probability: int = probability
        self.weight: int = weight
        self.first: JavaEntity = first
        self.second: JavaEntity = second
        self.child_reports: List[Report] = []

    def __lt__(self, other: Report):
        return (
            self.probability < other.probability
            if self.probability != other.probability
            else self.weight < other.weight
        )

    def __eq__(self, other: Report):
        return self.probability == other.probability and self.weight == other.weight

    def __repr__(self):
        return (
            f"< Report, probability: {self.probability}, comparing entities: {self.first.name}, "
            f"{self.second.name}, Child reports: {self.child_reports}>"
        )

    def __add__(self, other: Report):
        weight = self.weight + other.weight
        if weight == 0:
            weight = 1
        report = Report(
            (self.probability * self.weight + other.probability * other.weight)
            // weight,
            (self.weight + other.weight),
            self.first,
            self.second,
        )
        if isinstance(self.first, type(other.first)) or isinstance(
            self.second, type(other.second)
        ):
            report.child_reports.extend(self.child_reports + other.child_reports)
        else:
            report.child_reports.extend(self.child_reports)
            report.child_reports.append(other)
        return report


class JavaEntity(ABC):
    """Abstract object class for all the comparable parts of projects."""

    def __init__(self):
        self.name: str = ""

    def __repr__(self):
        return f"<{self.__class__.__name__}: {self.__dict__}>"

    @abstractmethod
    def compare(self, other: JavaEntity) -> Report:
        """Compare two objects of the same class inherited from `JavaEntity`. Produces `Report` object."""
        pass

    def compare_parts(self, other: JavaEntity, attr: str) -> Report:
        """Helper method that compares comparable attributes of objects.
        This method is responsible for the hierarchical behavior of comparisons."""
        if not isinstance(other, type(self)):
            raise TypeError("Cannot compare different types of JavaEntity!")
        report = Report(0, 0, self, other)
        self_attr_val = getattr(self, attr, None)
        other_attr_val = getattr(other, attr, None)
        if self_attr_val is None:
            raise ValueError(
                f"Instance of '{type(self)}' does not have attribute '{attr}'!"
            )
        if isinstance(self_attr_val, List):
            if not self_attr_val or not other_attr_val:
                return Report(0, 0, self, other)
            if not thorough_scan and (
                1
                - sqrt(
                    abs(len(self_attr_val) - len(other_attr_val))
                    / (len(self_attr_val) + len(other_attr_val))
                )
                < skip_attr_list_threshold
            ):
                return Report(0, 10, self, other)
            matrix = []
            self_unused_vals = set(self_attr_val)
            other_unused_vals = set(other_attr_val)
            for self_val in self_attr_val:
                matrix.extend(
                    self_val.compare(other_val) for other_val in other_attr_val
                )
            while matrix:
                max_report = max(matrix)
                self_unused_vals.remove(max_report.first)
                other_unused_vals.remove(max_report.second)
                matrix = list(
                    filter(
                        lambda x: False
                        if max_report.second == x.second or max_report.first == x.first
                        else True,
                        matrix,
                    )
                )
                report += max_report
            for unused in self_unused_vals:
                report += Report(0, 10, unused, NotFound())
            for unused in other_unused_vals:
                report += Report(0, 10, NotFound(), unused)
        elif isinstance(self_attr_val, JavaEntity):
            report += self_attr_val.compare(other_attr_val)
        else:
            raise ValueError(
                f"Cannot compare attribute '{attr}' of instance of '{type(self)}'!"
            )
        return report


class NotFound(JavaEntity):
    """Indicate that some part of the projects could not be matched to anything."""

    def compare(self, other: JavaEntity) -> Report:
        pass

    def __init__(self):
        super().__init__()
        self.name: str = "NOT FOUND"


class JavaModifier(JavaEntity):
    """Modifiers of classes, methods or variables."""

    def __init__(self, name: str):
        """Parameter `name` represents the Modifier string."""
        super().__init__()
        self.name: str = name

    def compare(self, other: JavaModifier) -> Report:
        if self.name == other.name:
            return Report(100, 10, self, other)
        else:
            return Report(0, 10, self, other)


class JavaType(JavaEntity):
    """Data type of variables or arguments, return type of methods. Can be user-implemented, imported, basic or None."""

    def __init__(self, type_name: str, package: str, project: Project):
        """Parameter `type_name` is the type identifier represented in source code,
        `package` represents the package where this type was declared
         and `project` keeps track of the parent `Project` object."""
        super().__init__()
        self.project = project
        self.name: str = type_name
        self.package: str = package
        if not type_name:
            self.compatible_format = None
            return
        self.compatible_format: str = translation_dict.get(self.name)

    @cached_property
    def is_user_defined(self) -> bool:
        """Was this data type declared by the programmer or not?"""
        return True if self in self.project.user_types else False

    @cached_property
    def non_user_defined_types(self) -> List[JavaType]:
        """Lists basic and externally imported data types that composed user-defined data type."""
        return self.project.user_types.get(self)

    def compare(self, other: JavaType) -> Report:
        if not self.name and not other.name:
            return Report(100, 1, self, other)
        if self.is_user_defined != other.is_user_defined:
            return Report(0, 10, self, other)
        if not self.is_user_defined:
            if self.name == other.name:
                return Report(100, 10, self, other)
            elif (self.compatible_format == other.name and other.name is not None) or (
                self.name == other.compatible_format and self.name is not None
            ):
                return Report(75, 10, self, other)
            elif (
                self.compatible_format is not None
                and self.compatible_format == other.compatible_format
            ):
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
    """Holds reference to a variable from the source code."""

    def __init__(
        self,
        variable_declaration: Union[
            javalang.tree.VariableDeclaration, javalang.tree.FieldDeclaration
        ],
        variable_declarator: javalang.tree.VariableDeclarator,
        java_file: JavaFile,
    ):
        """Parameter `variable_declaration` requires appropriate AST subtree,
        `variable` declarator requires AST subtree contained in the `variable_declaration`,
         `java_file` specifies parent file. (Single declaration can have multiple declarations.
         That is why 2 subtrees are required in order to construct this object.)"""
        super().__init__()
        self.java_file: JavaFile = java_file
        self.name: str = variable_declarator.name
        self.modifiers: List[JavaModifier] = [
            JavaModifier(m) for m in variable_declaration.modifiers
        ]
        self.type_name: str = variable_declaration.type.name

    @cached_property
    def type(self) -> JavaType:
        """Returns `JavaType` instance."""
        return self.java_file.get_type(self.type_name)

    def compare(self, other: JavaVariable) -> Report:
        report = self.compare_parts(other, "modifiers")
        report += self.compare_parts(other, "type")
        return report


class JavaMethodInvocation:
    """Helper class, represents invoked method from the body of another method."""

    def __init__(
        self,
        method_invocation: javalang.tree.MethodInvocation,
        statement: JavaStatementBlock,
    ):
        """Parameter `method_invocation` requires appropriate AST subtree,
        `statement` is reference to the parent `JavaStatementBlock` object."""
        self.statement: JavaStatementBlock = statement
        self.qualifier_str: str = method_invocation.qualifier
        self.name: str = method_invocation.member

    @cached_property
    def qualifier(self) -> Optional[JavaVariable]:
        """Java variable upon which the method was called."""
        if self.qualifier_str:
            qualifier = self.statement.java_method.get_local_variable(
                self.qualifier_str
            )
            if not qualifier:
                qualifier = self.statement.java_method.java_class.get_variable(
                    self.qualifier_str
                )
            return qualifier
        else:
            return None

    @cached_property
    def method_referenced(self) -> Optional[JavaMethod]:
        """`JavaMethod` object of the method that was called."""
        qualifier = self.qualifier
        if not qualifier:
            local_methods = list(
                filter(
                    lambda x: True if self.name == x.name else False,
                    self.statement.java_method.java_class.methods,
                )
            )
            if len(local_methods) == 1:
                return local_methods[0]
        else:
            t = qualifier.type
            if t.is_user_defined:
                cls = list(
                    filter(
                        lambda x: True if x.name == t.name else False,
                        self.statement.java_method.java_class.java_file.project.get_classes_in_package(
                            t.package
                        ),
                    )
                )
                if len(cls) != 1:
                    return None
                m = list(
                    filter(
                        lambda x: True if x.name == self.name else False, cls[0].methods
                    )
                )
                if len(m) != 1:
                    return None
                return m[0]


class JavaStatementBlock(JavaEntity):
    """Statements from the source code between semicolons contained in the body of a method."""

    def __init__(self, statement: javalang.tree.Statement, java_method: JavaMethod):
        """Parameter `statement` requires appropriate AST subtree,
        `java_method` holds reference to parent `JavaMethod` object."""
        super().__init__()
        self.name: str = f"Statement {statement.position}"
        self.java_method: JavaMethod = java_method
        self.local_variables: List[JavaVariable] = []
        searched_nodes = self._search_for_types(
            statement,
            {javalang.tree.VariableDeclaration, javalang.tree.MethodInvocation},
        )
        for declaration in searched_nodes.get(javalang.tree.VariableDeclaration, []):
            for declarator in declaration.declarators:
                var = JavaVariable(
                    declaration, declarator, self.java_method.java_class.java_file
                )
                self.local_variables.append(var)

        self.invoked_methods: List[JavaMethodInvocation] = [
            JavaMethodInvocation(m, self)
            for m in searched_nodes.get(javalang.tree.MethodInvocation, [])
        ]
        self.parts: Dict[Type, int] = self._tree_to_dict(statement)

    @cached_property
    def statements_from_invocations(self) -> List[JavaStatementBlock]:
        """Statements from methods called from the body of this method."""
        ans = []
        for invoked_method in self.invoked_methods:
            m = invoked_method.method_referenced
            if m == self.java_method:
                continue
            if m is not None:
                ans.extend(m.statement_blocks)
        return ans

    def compare(self, other: JavaStatementBlock) -> Report:
        report = Report(0, 0, self, other)
        for node_type in self.parts:
            self_occurrences = self.parts[node_type]
            other_occurrences = other.parts.get(node_type, 0)
            if other_occurrences > 0:
                report += Report(
                    int(
                        100
                        - 100
                        * (
                            abs(self_occurrences - other_occurrences)
                            / (self_occurrences + other_occurrences)
                        )
                    ),
                    10,
                    self,
                    other,
                )
            else:
                backup_node_type = node_translation_dict.get(node_type, None)
                if backup_node_type is not None:
                    other_occurrences = other.parts.get(backup_node_type, 0)
                    if other_occurrences > 0:
                        report += Report(
                            int(
                                50
                                - 50
                                * (
                                    abs(self_occurrences - other_occurrences)
                                    / (self_occurrences + other_occurrences)
                                )
                            ),
                            10,
                            self,
                            other,
                        )
                else:
                    report += Report(0, 10, self, other)
        return report

    def _search_for_types(
        self, statement: javalang.tree.Node, block_types: Set[Type]
    ) -> Dict[Type, List[javalang.tree.Node]]:
        """Go through AST and fetch subtrees rooted in specified node types.
        Parameter `statement` represents AST, `block_types` is set of searched node types.
        Returns dictionary structured as so: `{NodeType1: [subtree1, subtree2, ...], NodeType2: [...]}`"""
        ans = {}
        if not isinstance(statement, javalang.tree.Node):
            return ans
        node_type = type(statement)
        if node_type in block_types:
            if node_type in ans.keys():
                ans.update(
                    {
                        node_type: ans[node_type]
                        + [
                            statement,
                        ]
                    }
                )
            else:
                ans.update(
                    {
                        node_type: [
                            statement,
                        ]
                    }
                )
        for attribute in getattr(statement, "attrs", []):
            child = getattr(statement, attribute, None)
            if isinstance(child, javalang.tree.Node):
                dict_to_add = self._search_for_types(child, block_types)
                for key in dict_to_add:
                    if key in ans.keys():
                        ans.update({key: ans[key] + dict_to_add[key]})
                    else:
                        ans.update(dict_to_add)
        return ans

    def _tree_to_dict(self, tree: javalang.tree.Node) -> Dict[Type, int]:
        """Flattens AST to dictionary structured as so: {NodeType: number_of_occurrences}"""
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
            for key in self._tree_to_dict(child):
                if key in ans.keys():
                    ans.update({key: ans[key] + 1})
                else:
                    ans.update({key: 1})
        return ans


class JavaParameter(JavaEntity):
    """Arguments of methods."""

    def __init__(self, parameter_name: str, parameter_type: str, method: JavaMethod):
        """Parameter `parameter_name` represents the identifier for the argument,
        `parameter_type` is an identifier of the parameter type,
        `method` is parent `JavaMethod` object."""
        super().__init__()
        self.name: str = parameter_name
        self.type_string: str = parameter_type
        self.method: JavaMethod = method

    @cached_property
    def type(self):
        """`JavaType` of the parameter."""
        return self.method.java_class.java_file.get_type(self.type_string)

    def compare(self, other: JavaParameter) -> Report:
        return self.compare_parts(other, "type")


class JavaMethod(JavaEntity):
    """Method object from the source code."""

    def __init__(
        self, java_method: javalang.tree.MethodDeclaration, java_class: JavaClass
    ):
        """Parameter `java_method` requires appropriate AST subtree,
        `java_class` is reference to the parent `JavaClass` object."""
        super().__init__()
        self.java_method: javalang.tree.MethodDeclaration = java_method
        self.name: str = self.java_method.name
        self.java_class: JavaClass = java_class
        self.raw_statement_blocks: List[javalang.tree.Node] = java_method.body
        self.statement_blocks: List[JavaStatementBlock] = []
        self.return_type_str: str = getattr(java_method.return_type, "name", None)
        self.modifiers: List[JavaModifier] = [
            JavaModifier(m) for m in java_method.modifiers
        ]
        self.arguments: List[JavaParameter] = []
        for parameter in self.java_method.parameters:
            argument = JavaParameter(parameter.name, parameter.type.name, self)
            self.arguments.append(argument)
        if not self.java_method.body:
            return
        for block in self.java_method.body:
            if isinstance(block, javalang.tree.Statement) and len(block.attrs) == 1:
                return
            self.statement_blocks.append(JavaStatementBlock(block, self))

    @cached_property
    def local_variables(self) -> List[JavaVariable]:
        """Variables declared in the body of this method."""
        ans = []
        for statement_block in self.statement_blocks:
            ans.extend(statement_block.local_variables)
        return ans

    @cached_property
    def return_type(self):
        """`JavaType` object of the return type."""
        return self.java_class.java_file.get_type(self.return_type_str)

    def compare(self, other: JavaMethod) -> Report:
        report = self.compare_parts(other, "return_type")
        report += self.compare_parts(other, "arguments")
        if report.probability > method_interface_threshold:
            report += self.compare_parts(other, "all_blocks")
        return report

    def get_local_variable(self, var_name: str) -> Optional[JavaVariable]:
        """Get local variable by its name."""
        ans = list(
            filter(
                lambda x: True if x.name == var_name else False, self.local_variables
            )
        )
        if len(ans) > 0:
            return ans[-1]
        return None

    @cached_property
    def statements_from_invocations(self) -> List[JavaStatementBlock]:
        """Statements from other methods invoked from the body of this method."""
        ans = []
        for block in self.statement_blocks:
            ans.extend(block.statements_from_invocations)
        return ans

    @cached_property
    def all_blocks(self):
        """Statements from own body and from invoked methods."""
        return self.statement_blocks + self.statements_from_invocations


class JavaClass(JavaEntity):
    """Representation of classes from the source code."""

    def __init__(self, java_class: javalang.tree.ClassDeclaration, java_file: JavaFile):
        """Parameter `java_class` requires appropriate AST subtree,
        `java_file` is reference to the parent `JavaFile` object."""
        super().__init__()
        self.java_class: javalang.tree.ClassDeclaration = java_class
        self.java_file: JavaFile = java_file
        self.name: str = java_class.name
        self.methods: List[JavaMethod] = []
        self.variables: List[JavaVariable] = []
        self.modifiers: List[JavaModifier] = [
            JavaModifier(m) for m in java_class.modifiers
        ]
        for field in self.java_class.fields:
            for declarator in field.declarators:
                if isinstance(declarator, javalang.tree.VariableDeclarator):
                    variable = JavaVariable(field, declarator, self.java_file)
                    variable.modifiers = [JavaModifier(m) for m in field.modifiers]
                    self.variables.append(variable)
        for method in self.java_class.methods:
            self.methods.append(JavaMethod(method, self))

    def compare(self, other: JavaClass) -> Report:
        report = self.compare_parts(other, "modifiers")
        report += self.compare_parts(other, "variables")
        report += self.compare_parts(other, "methods")
        return report

    def get_non_user_defined_types(self) -> List[JavaType]:
        """Return all class attribute types as list of types not defined by the user."""
        ans = []
        for variable in self.variables:
            if not variable.type.is_user_defined:
                ans.append(variable)
            elif variable.type.name == self.name:
                continue
            else:
                ans.extend(
                    self.java_file.project.get_class(
                        variable.type.package, variable.type.name
                    ).get_non_user_defined_types()
                )
        return ans

    def get_variable(self, var_name: str):
        """Find variable by its name."""
        ans = list(
            filter(lambda x: True if x.name == var_name else False, self.variables)
        )
        if len(ans) > 0:
            return ans[-1]
        return None


class JavaFile(JavaEntity):
    """Represents files that end with the '.java' extension."""

    def __init__(self, path: Union[str, pathlib.Path], project: Project):
        """Parameter `path` is path to the file,
        `project` is parent `Project` instance."""
        super().__init__()
        self.path: pathlib.Path = (
            pathlib.Path(path) if not isinstance(path, pathlib.Path) else path
        )
        self.name: str = self.path.name
        self.name_without_appendix: str = self.name.replace(".java", "")
        compilation_unit = get_ast(path)
        self.project: Project = project
        self.package: str = compilation_unit.package.name
        self.wildcard_imports = [i.path for i in compilation_unit.imports if i.wildcard]
        self.imports: List[str] = [
            i.path for i in compilation_unit.imports if not i.wildcard
        ]
        self.import_types: List[str] = [i.split(".")[-1] for i in self.imports]
        self.classes: List[JavaClass] = [
            JavaClass(body, self) for body in compilation_unit.types
        ]
        for cls in self.classes:
            self.project.user_types.update(
                {JavaType(cls.name, self.package, self.project): []}
            )

    def compare(self, other: JavaFile) -> Report:
        report = self.compare_parts(other, "classes")
        return report

    def get_type(self, type_name: str) -> JavaType:
        """Get `JavaType` object from its string identifier."""
        if not type_name:
            return JavaType(None, None, self.project)
        ans = self.project.get_user_type(self.package, type_name)
        if ans is not None:
            return ans
        for imp in self.imports:
            if re.match(rf"^.*\.{type_name}$", imp) is not None:
                ans = self.project.get_user_type(
                    imp.replace(f".{type_name}", ""), type_name
                )
                if ans is not None:
                    return ans
                return JavaType(
                    type_name, imp.replace(f".{type_name}", ""), self.project
                )
        for wildcard_import in self.wildcard_imports:
            ans = self.project.get_user_type(wildcard_import, type_name)
            if ans is not None:
                return ans
        return JavaType(type_name, "", self.project)


class Project(JavaEntity):
    """Represents whole project that needs to be compared with other projects."""

    def __init__(self, path: Union[str, pathlib.Path]):
        """Parameter `path` is path to the project's root directory."""
        super().__init__()
        self.path: pathlib.Path
        if not isinstance(path, pathlib.Path):
            self.path = pathlib.Path(path)
        else:
            self.path = path
        if not self.path.exists():
            raise ValueError(f"Given path does not exist: {path}")
        self.name = self.path.name
        self.root_path = get_user_project_root(self.path)
        self.packages: Set[str] = get_packages(self.path)
        self.user_types: Dict[JavaType, List[JavaType]] = {}
        self.java_files: List[JavaFile] = []
        java_files = get_java_files(self.path)
        for file in java_files:
            java_file = JavaFile(file, self)
            self.java_files.append(java_file)
        for file in self.java_files:
            for w_import in file.wildcard_imports:
                file.import_types.extend(
                    f.name_without_appendix for f in self.get_files_in_package(w_import)
                )
        for t in self.user_types.keys():
            type_class = self.get_class(t.package, t.name)
            self.user_types.update({t: type_class.get_non_user_defined_types()})

    def get_file(self, package: str, class_name: str) -> Optional[JavaFile]:
        """Returns `JavaFile` object filtered by package and class name."""
        files = list(
            filter(
                lambda x: True
                if x.name_without_appendix == class_name and x.package == package
                else False,
                self.java_files,
            )
        )
        if len(files) == 1:
            return files[0]
        return None

    def get_files_in_package(self, package: str) -> List[JavaFile]:
        """Returns all `JavaFile` instances in a package."""
        return list(
            filter(lambda x: True if x.package == package else False, self.java_files)
        )

    def get_classes_in_package(self, package: str) -> List[JavaClass]:
        """Returns all `JavaClass` instances in a package."""
        ans = []
        for file in self.get_files_in_package(package):
            ans.extend(file.classes)
        return ans

    def get_class(self, package: str, class_name: str) -> Optional[JavaClass]:
        """Return `JavaClass` object filtered by package and name."""
        found_classes = list(
            filter(lambda x: True if x.name == class_name else False, self.classes)
        )
        if len(found_classes) == 1:
            return found_classes[0]
        print(f"Project.get_class: Cannot find {package}.{class_name}!")
        return None

    def get_user_type(self, package: str, class_name: str) -> Optional[JavaType]:
        """Return user-defined `JavaType` filtered by package and class name."""
        types = list(
            filter(
                lambda x: True
                if x.package == package and x.name == class_name
                else False,
                self.user_types.keys(),
            )
        )
        if len(types) == 1:
            return types[0]
        return None

    @cached_property
    def classes(self):
        """All classes in project."""
        ans = []
        for file in self.java_files:
            ans.extend(file.classes)
        return ans

    @cached_property
    def methods(self):
        """All methods in project."""
        ans = []
        for cl in self.classes:
            ans.extend(cl.methods)
        return ans

    def compare(self, other: Project) -> Report:
        report = self.compare_parts(other, "java_files")
        return report
