from __future__ import annotations

import ast
import pathlib
from typing import Union, List, Optional
from functools import cached_property

from detection.thresholds import method_interface_threshold
import detection.utils as utils
from detection.abstract_scan import (
    Report,
    ComparableEntity,
    AbstractStatementBlock,
    AbstractProject,
)


class PythonFunction(ComparableEntity):
    """Object representing Python functions and methods."""

    def __init__(
        self,
        python_function: Union[ast.FunctionDef, ast.AsyncFunctionDef],
        python_file: PythonFile,
        python_class: Optional[PythonClass] = None,
    ):
        """Parameter `python_function` requires appropriate AST subtree,
        `python_file` is a reference to the parent file,
        `python_class` is a reference to a parent class if the object represents a method.
        """
        super().__init__()
        self.name = python_function.name
        self.visualise = True
        self.python_file: PythonFile = python_file
        self.python_class: Optional[PythonClass] = python_class
        self.parts: List[PythonStatementBlock] = [
            PythonStatementBlock(t, self) for t in python_function.body
        ]
        self.args: int = len(python_function.args.args)
        self.positionals: int = len(python_function.args.posonlyargs)
        self.kwonlyargs: int = len(python_function.args.kwonlyargs)
        self.has_vararg: bool = (
            True if getattr(python_function.args, "vararg", None) else False
        )
        self.has_kwarg: bool = (
            True if getattr(python_function.args, "kwarg", None) else False
        )

    @cached_property
    def statements_from_invocations(self) -> List[PythonStatementBlock]:
        """Get statement blocks that belong to functions called in the body of this function."""
        ans = []
        for statement in self.parts:
            ans.extend(statement.statements_from_invocations)
        return ans

    @cached_property
    def all_blocks(self):
        """Get both own and called blocks at once."""
        return self.parts + self.statements_from_invocations

    def compare(self, other: PythonFunction, fast_scan: bool = False) -> Report:
        report = Report(
            100 if self.has_vararg == other.has_vararg else 0, 5, self, other
        )
        report += Report(
            100 if self.has_kwarg == other.has_kwarg else 0, 5, self, other
        )
        report += Report(
            utils.calculate_score_based_on_numbers(self.args, other.args),
            5,
            self,
            other,
        )
        report += Report(
            utils.calculate_score_based_on_numbers(self.positionals, other.positionals),
            5,
            self,
            other,
        )
        report += Report(
            utils.calculate_score_based_on_numbers(self.kwonlyargs, other.kwonlyargs),
            5,
            self,
            other,
        )
        if (not fast_scan) or report.probability > method_interface_threshold:
            report += self.compare_parts(other, "all_blocks", fast_scan)
        return report


class PythonStatementBlock(AbstractStatementBlock):
    """Represents Python statement blocks (parts of procedures)."""

    def __init__(
        self,
        statement: ast.stmt,
        parent: Union[PythonFile, PythonClass, PythonFunction],
    ):
        super().__init__(statement, ast.AST)
        self.name = "Statement"
        self.invoked_methods: List[PythonFunctionInvocation] = [
            PythonFunctionInvocation(s, self)
            for s in self._search_for_types(
                statement,
                {
                    ast.Call,
                },
            ).get(ast.Call, [])
        ]
        self.parent = parent
        self.parent_file = (
            parent.python_file
            if isinstance(parent, PythonFunction) or isinstance(parent, PythonClass)
            else parent
        )

    @cached_property
    def statements_from_invocations(self) -> List[PythonStatementBlock]:
        """Get statement blocks that belong to functions called in this block."""
        ans = []
        for invoked_method in self.invoked_methods:
            func = invoked_method.function_referenced
            if not func:
                continue
            ans.extend(func.parts)
        return ans


class PythonFunctionInvocation:
    """Helper class, represents calls of functions."""

    def __init__(self, function_invocation: ast.Call, statement: PythonStatementBlock):
        """Parameter `function_invocation` requires an appropriate AST object,
        `statement` is the parent statement block."""
        self.statement = statement
        self.name = ""
        self.qualifier_str = ""
        if isinstance(function_invocation.func, ast.Attribute):
            self.name = function_invocation.func.attr
            arr = []
            tmp = function_invocation.func.value
            while isinstance(tmp, ast.Attribute):
                arr.insert(0, tmp.attr)
                tmp = tmp.attr
            if isinstance(tmp, ast.Name):
                arr.append(tmp.id)
            self.qualifier_str = ".".join(arr)
            if not self.qualifier_str:
                self.qualifier_str = "-"

        elif isinstance(function_invocation.func, ast.Name):
            self.name = function_invocation.func.id

    @cached_property
    def function_referenced(self) -> Optional[PythonFunction]:
        """Gets a reference to the called function."""
        return self.statement.parent_file.get_function(self.name, self.qualifier_str)


class PythonImport:
    """Helper class, represents imports of the file."""

    def __init__(self, imp: Union[ast.Import, ast.ImportFrom], python_file: PythonFile):
        """Parameter `imp` is the AST import object,
        `python_file` is the parent file to which the element is imported."""
        self.modules_str: List[str] = []
        self.imported_objects_str: List[str] = []
        self.python_file: PythonFile = python_file
        if isinstance(imp, ast.Import):
            self.modules_str.extend([i.name for i in imp.names])
        elif isinstance(imp, ast.ImportFrom):
            self.modules_str = [imp.module]
            self.imported_objects_str.extend([i.name for i in imp.names])


class PythonClass(ComparableEntity):
    """Class representing Python classes."""

    def __init__(
        self, python_class: ast.ClassDef, python_file: PythonFile, *, min_body_len=0
    ):
        """Parameter `python_class` requires the AST object,
        `python_class` is a reference to the parent PythonFile."""
        super().__init__()
        self.name = python_class.name
        self.visualise = True
        self.python_file = python_file
        self.methods: List[PythonFunction] = [
            PythonFunction(a, self.python_file, self)
            for a in python_class.body
            if isinstance(a, ast.AsyncFunctionDef) or isinstance(a, ast.FunctionDef)
            if a.body and len(a.body) >= min_body_len
        ]
        self.statements: List[PythonStatementBlock] = [
            PythonStatementBlock(t, self)
            for t in python_class.body
            if not (
                isinstance(t, ast.AsyncFunctionDef)
                or isinstance(t, ast.FunctionDef)
                or isinstance(t, ast.ClassDef)
            )
        ]

    @cached_property
    def all_statements(self):
        """Get all statements of the class, including called statement blocks."""
        ans = [s for s in self.statements]
        for statement_block in self.statements:
            ans.extend(statement_block.statements_from_invocations)
        return ans

    def compare(self, other: ComparableEntity, fast_scan: bool = False) -> Report:
        report = self.compare_parts(other, "methods", fast_scan)
        report += self.compare_parts(other, "all_statements", fast_scan)
        return report


class PythonFile(ComparableEntity):
    """Class representing Python files."""

    def __init__(
        self, path: Union[str, pathlib.Path], project: PythonProject, *, min_body_len=0
    ):
        """Parameter `path` requires  path to the file in the filesystem,
        `project is a reference to the parent PythonProject.`"""
        super().__init__()
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)
        self.path = path
        self.name = self.path.name
        self.visualise = True
        self.name_without_appendix = self.name.split(".")[0]
        self.project = project
        self.imports: List[PythonImport] = []
        _ast = utils.get_python_ast(self.path)
        _body = [] if not _ast else _ast.body
        for i in _body:
            if not (isinstance(i, ast.Import) or isinstance(i, ast.ImportFrom)):
                continue
            self.imports.append(PythonImport(i, self))
        self.functions: List[PythonFunction] = [
            PythonFunction(a, self)
            for a in _body
            if (isinstance(a, ast.AsyncFunctionDef) or isinstance(a, ast.FunctionDef))
            and len(a.body) >= min_body_len
        ]
        self.classes: List[PythonClass] = [
            PythonClass(a, self, min_body_len=min_body_len)
            for a in _body
            if isinstance(a, ast.ClassDef)
        ]
        self.statement_blocks: List[PythonStatementBlock] = [
            PythonStatementBlock(t, self)
            for t in _body
            if not (
                isinstance(t, ast.AsyncFunctionDef)
                or isinstance(t, ast.FunctionDef)
                or isinstance(t, ast.ClassDef)
            )
        ]

    def get_function(
        self, function_name: str, qualifier: Optional[str] = None
    ) -> Optional[PythonFunction]:
        """Get function object from the context of the file where the function is called.
        Parameter `function_name` is the name of the searched-for function,
        `qualifier` is the dotted identifier before the function or method (`re` in `re.match()`)
        """
        if not qualifier:
            ans = list(
                filter(
                    lambda x: True if function_name == x.name else False, self.functions
                )
            )
            if len(ans) > 0:
                return ans[-1]
            for imp in self.imports:
                if function_name in imp.imported_objects_str:
                    mod = self.project.get_module(imp.modules_str[0])
                    if mod == self:  # Infinite recursion prevention
                        return None
                    elif mod:
                        return mod.get_function(function_name)
                    return None
        for imp in self.imports:
            if qualifier in imp.modules_str:
                mod = self.project.get_module(qualifier)
                if mod:
                    return mod.get_function(function_name)
                return None
        for cl in self.classes:
            # This is not 100 % accurate, method from first found class will be returned,
            # which might not match the actual object type
            ans = list(
                filter(lambda x: True if function_name == x.name else False, cl.methods)
            )
            if len(ans) > 0:
                return ans[-1]
        return None

    @cached_property
    def all_statements(self):
        """Gets combined own statement blocks and called statements."""
        ans = [s for s in self.statement_blocks]
        for statement_block in self.statement_blocks:
            ans.extend(statement_block.statements_from_invocations)
        return ans

    def compare(self, other: ComparableEntity, fast_scan: bool = False) -> Report:
        report = self.compare_parts(other, "functions", fast_scan)
        report += self.compare_parts(other, "classes", fast_scan)
        report += self.compare_parts(other, "all_statements", fast_scan)
        return report


class PythonProject(AbstractProject):
    """Class representing the Python Projects."""

    def __init__(
        self, path: Union[str, pathlib.Path], template: bool, *, min_body_len=0
    ):
        """Parameter `path` requires the root directory of the project,
        `template` is a boolean value stating whether the project should be categorized as a template.
        """
        super().__init__("Python", template)
        self.path: pathlib.Path
        if not isinstance(path, pathlib.Path):
            self.path = pathlib.Path(path)
        else:
            self.path = path
        if not self.path.exists():
            raise ValueError(f"Given path does not exist: {path}")
        self.name = self.path.name
        self.visualise = True
        self.python_files: List[PythonFile] = [
            PythonFile(p, self, min_body_len=min_body_len)
            for p in utils.get_python_files(self.path)
        ]
        self.__all_statements = []
        for p_file in self.python_files:
            self.__all_statements.extend(p_file.all_statements)
            for func in p_file.functions:
                self.__all_statements.extend(func.all_blocks)
            for p_class in p_file.classes:
                self.__all_statements.extend(p_class.all_statements)
                for method in p_class.methods:
                    self.__all_statements.extend(method.all_blocks)

    def get_module(self, identifier: str) -> Optional[PythonFile]:
        """Search for a PythonFile object from imports."""
        identifier_list = [i for i in identifier.split(".") if i]
        all_found_files = list(
            filter(
                lambda x: True
                if x.name_without_appendix == identifier_list[-1]
                else False,
                self.python_files,
            )
        )
        if len(all_found_files) == 1:
            return all_found_files[0]
        elif len(all_found_files) < 1 or len(identifier_list) <= 1:
            return None
        filtered_files = []
        for f in all_found_files:
            found = True
            parent_names = set(p.name for p in f.path.parents)
            for identifier_part in identifier_list[:-1]:
                found = identifier_part in parent_names
                if not found:
                    break
            if not found:
                continue
            filtered_files.append(f)
        if len(filtered_files) == 1:
            return filtered_files[0]
        print(f"WARNING: Python get_module: {identifier} not found!")
        return None

    def size(self) -> int:
        return len(self.python_files)

    def compare(
        self, other: AbstractProject, fast_scan: bool = False
    ) -> Optional[Report]:
        if self.project_type != other.project_type:
            return
        return self.compare_parts(other, "python_files", fast_scan)
