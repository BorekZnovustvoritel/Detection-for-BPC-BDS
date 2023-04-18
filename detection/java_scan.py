from __future__ import annotations

import pathlib
from functools import cached_property

import javalang
import javalang.tree
from typing import List, Union, Set, Optional, Dict
import re

from detection.abstract_scan import (
    Report,
    ComparableEntity,
    AbstractStatementBlock,
    AbstractProject,
)
from detection.definitions import type_translation_dict
from detection.thresholds import method_interface_threshold
from detection.utils import (
    get_java_ast,
    get_user_project_root,
    get_java_files,
)


class JavaModifier(ComparableEntity):
    """Modifiers of classes, methods or variables."""

    def __init__(self, name: str):
        """Parameter `name` represents the Modifier string."""
        super().__init__()
        self.name: str = name

    def compare(self, other: JavaModifier, fast_scan: bool = False) -> Report:
        if self.name == other.name:
            return Report(100, 10, self, other)
        else:
            return Report(0, 10, self, other)


class JavaType(ComparableEntity):
    """Data type of variables or arguments, return type of methods. Can be user-implemented, imported, basic or None."""

    def __init__(self, type_name: str, package: str, project: JavaProject):
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
        self.compatible_format: str = type_translation_dict.get(self.name)

    @cached_property
    def is_user_defined(self) -> bool:
        """Was this data type declared by the programmer or not?"""
        return True if self in self.project.user_types else False

    @cached_property
    def non_user_defined_types(self) -> List[JavaType]:
        """Lists basic and externally imported data types that composed user-defined data type."""
        return self.project.user_types.get(self)

    def compare(self, other: JavaType, fast_scan: bool = False) -> Report:
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
            report = self.compare_parts(other, "non_user_defined_types", fast_scan)
            return report
        return Report(0, 10, self, other)

    def __eq__(self, other: JavaType):
        return self.name == other.name and self.package == other.package

    def __hash__(self):
        return self.name.__hash__() + self.package.__hash__()


class JavaVariable(ComparableEntity):
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

    def compare(self, other: JavaVariable, fast_scan: bool = False) -> Report:
        report = self.compare_parts(other, "modifiers", fast_scan)
        report += self.compare_parts(other, "type", fast_scan)
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


class JavaStatementBlock(AbstractStatementBlock):
    """Statements from the source code between semicolons contained in the body of a method."""

    def __init__(self, statement: javalang.tree.Statement, java_method: JavaMethod):
        """Parameter `statement` requires appropriate AST subtree,
        `java_method` holds reference to parent `JavaMethod` object."""
        super().__init__(statement, javalang.tree.Statement)
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


class JavaParameter(ComparableEntity):
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

    def compare(self, other: JavaParameter, fast_scan: bool = False) -> Report:
        return self.compare_parts(other, "type", fast_scan)


class JavaMethod(ComparableEntity):
    """Method object from the source code."""

    def __init__(
        self, java_method: javalang.tree.MethodDeclaration, java_class: JavaClass
    ):
        """Parameter `java_method` requires appropriate AST subtree,
        `java_class` is reference to the parent `JavaClass` object."""
        super().__init__()
        self.name: str = java_method.name
        self.visualise = True
        self.java_class: JavaClass = java_class
        self.raw_statement_blocks: List[javalang.tree.Node] = java_method.body
        self.statement_blocks: List[JavaStatementBlock] = []
        self.return_type_str: str = getattr(java_method.return_type, "name", None)
        self.modifiers: List[JavaModifier] = [
            JavaModifier(m) for m in java_method.modifiers
        ]
        self.arguments: List[JavaParameter] = []
        for parameter in java_method.parameters:
            argument = JavaParameter(parameter.name, parameter.type.name, self)
            self.arguments.append(argument)
        if not java_method.body:
            return
        for block in java_method.body:
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

    def compare(self, other: JavaMethod, fast_scan: bool = False) -> Report:
        report = self.compare_parts(other, "return_type", fast_scan)
        report += self.compare_parts(other, "arguments", fast_scan)
        if (not fast_scan) or report.probability > method_interface_threshold:
            report += self.compare_parts(other, "all_blocks", fast_scan)
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


class JavaClass(ComparableEntity):
    """Representation of classes from the source code."""

    def __init__(self, java_class: javalang.tree.ClassDeclaration, java_file: JavaFile):
        """Parameter `java_class` requires appropriate AST subtree,
        `java_file` is reference to the parent `JavaFile` object."""
        super().__init__()
        self.java_file: JavaFile = java_file
        self.name: str = java_class.name
        self.visualise = True
        self.methods: List[JavaMethod] = []
        self.variables: List[JavaVariable] = []
        self.modifiers: List[JavaModifier] = [
            JavaModifier(m) for m in java_class.modifiers
        ]
        for field in java_class.fields:
            for declarator in field.declarators:
                if isinstance(declarator, javalang.tree.VariableDeclarator):
                    variable = JavaVariable(field, declarator, self.java_file)
                    variable.modifiers = [JavaModifier(m) for m in field.modifiers]
                    self.variables.append(variable)
        for method in java_class.methods:
            self.methods.append(JavaMethod(method, self))

    def compare(self, other: JavaClass, fast_scan: bool = False) -> Report:
        report = self.compare_parts(other, "variables", fast_scan)
        report += self.compare_parts(other, "methods", fast_scan)
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


class JavaFile(ComparableEntity):
    """Represents files that end with the '.java' extension."""

    def __init__(self, path: Union[str, pathlib.Path], project: JavaProject):
        """Parameter `path` is path to the file,
        `project` is parent `Project` instance."""
        super().__init__()
        self.path: pathlib.Path = (
            pathlib.Path(path) if not isinstance(path, pathlib.Path) else path
        )
        self.name: str = self.path.name
        self.visualise = True
        self.name_without_appendix: str = self.name.replace(".java", "")
        compilation_unit = get_java_ast(path)
        if not compilation_unit:
            raise ValueError(f"Invalid Java file, compilation failed: {path}")
        self.project: JavaProject = project
        self.package: str = getattr(compilation_unit.package, "name", "")
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

    def compare(self, other: JavaFile, fast_scan: bool = False) -> Report:
        report = self.compare_parts(other, "classes", fast_scan)
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


class JavaProject(AbstractProject):
    """Represents whole project that needs to be compared with other projects."""

    def size(self) -> int:
        return len(self.java_files)

    def __init__(self, path: Union[str, pathlib.Path], template: bool):
        """Parameter `path` is path to the project's root directory."""
        super().__init__("Java", template)
        self.path: pathlib.Path
        if not isinstance(path, pathlib.Path):
            self.path = pathlib.Path(path)
        else:
            self.path = path
        if not self.path.exists():
            raise ValueError(f"Given path does not exist: {path}")
        self.name = self.path.name
        self.visualise = True
        self.root_path = get_user_project_root(self.path)
        self.user_types: Dict[JavaType, List[JavaType]] = {}
        self.java_files: List[JavaFile] = []
        java_files = get_java_files(self.path)
        for file in java_files:
            try:
                self.java_files.append(JavaFile(file, self))
            except ValueError:
                continue
        for file in self.java_files:
            for w_import in file.wildcard_imports:
                file.import_types.extend(
                    f.name_without_appendix for f in self.get_files_in_package(w_import)
                )
        for t in self.user_types.keys():
            type_class = self.get_class(t.package, t.name)
            if type_class:
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
        if package.startswith("$"):
            package = package[1:]
        found_classes = list(
            filter(lambda x: True if x.name == class_name else False, self.classes)
        )
        if len(found_classes) == 1:
            return found_classes[0]
        if len(found_classes) > 1:
            found_classes = list(
                filter(
                    lambda x: True if x.java_file.package == package else False,
                    found_classes,
                )
            )
        if len(found_classes) == 1:
            return found_classes[0]
        print(f"Java get_class: Cannot find {package}.{class_name} in {self.name}!")
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

    def compare(
        self, other: AbstractProject, fast_scan: bool = False
    ) -> Optional[Report]:
        if self.project_type != other.project_type:
            return
        report = self.compare_parts(other, "java_files", fast_scan)
        return report
