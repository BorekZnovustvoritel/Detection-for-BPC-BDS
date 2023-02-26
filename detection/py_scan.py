from __future__ import annotations

import ast
import pathlib
from typing import Union, List, Type, Dict
import detection.utils as utils

from abstract_scan import Report, ComparableEntity


class PythonProject(ComparableEntity):
    def __init__(self, path: Union[str, pathlib.Path]):
        super().__init__()
        self.path: pathlib.Path
        if not isinstance(path, pathlib.Path):
            self.path = pathlib.Path(path)
        else:
            self.path = path
        if not self.path.exists():
            raise ValueError(f"Given path does not exist: {path}")
        self.name = self.path.name
        self.python_files: List[PythonFile] = [PythonFile(p, self) for p in utils.get_python_files(self.path)]

    def compare(self, other: PythonProject) -> Report:
        return self.compare_parts(other, "python_files")


class PythonFile(ComparableEntity):
    def compare(self, other: ComparableEntity) -> Report:
        report = self.compare_parts(other, "functions")
        report += self.compare_parts(other, "classes")
        return report

    def __init__(self, path: Union[str, pathlib.Path], project: PythonProject):
        super().__init__()
        if not isinstance(path, pathlib.Path):
            path = pathlib.Path(path)
        self.path = path
        self.name = self.path.name
        self.project = project
        _ast = utils.get_python_ast(self.path)
        _body = [] if not _ast else _ast.body
        self.functions: List[PythonFunction] = [PythonFunction(a, self) for a in _body if
                                                isinstance(a, ast.AsyncFunctionDef) or isinstance(a, ast.FunctionDef)]
        self.classes: List[PythonClass] = [PythonClass(a, self) for a in _body if isinstance(a, ast.ClassDef)]
        self.dicts_to_compare: List[PythonStatementBlock] = [PythonStatementBlock(t, self) for t in _body if not (
                isinstance(t, ast.AsyncFunctionDef) or isinstance(t, ast.FunctionDef) or isinstance(t,
                                                                                                    ast.ClassDef))]


class PythonClass(ComparableEntity):

    def compare(self, other: ComparableEntity) -> Report:
        report = self.compare_parts(other, "methods")
        return report

    def __init__(self, python_class: ast.ClassDef, python_file: PythonFile):
        super().__init__()
        self.name = python_class.name
        self.python_file = python_file
        _ast = python_class
        self.methods: List[PythonFunction] = [PythonFunction(a, self.python_file) for a in _ast.body if
                                              isinstance(a, ast.AsyncFunctionDef) or isinstance(a, ast.FunctionDef)]
        self.dicts_to_compare: List[PythonStatementBlock] = [PythonStatementBlock(t, self) for t in _ast.body if not (
                isinstance(t, ast.AsyncFunctionDef) or isinstance(t, ast.FunctionDef) or isinstance(t,
                                                                                                    ast.ClassDef))]


class PythonFunction(ComparableEntity):
    def compare(self, other: ComparableEntity) -> Report:
        pass

    def __init__(self, python_function: Union[ast.FunctionDef, ast.AsyncFunctionDef], python_file: PythonFile):
        super().__init__()
        self.name = python_function.name
        self.python_file: PythonFile = python_file
        self.parts: List[PythonStatementBlock] = [PythonStatementBlock(t, self) for t in python_function.body]
        self.args: int = len(python_function.args.args)
        self.positionals: int = len(python_function.args.posonlyargs)
        self.kwargs: int = len(python_function.args.kwonlyargs)


class PythonStatementBlock(ComparableEntity):

    def compare(self, other: ComparableEntity) -> Report:
        pass

    def __init__(self, statement: ast.stmt, parent: Union[PythonFile, PythonClass, PythonFunction]):
        super().__init__()
        self.name = "Statement"
        self.invoked_methods: List[PythonFunctionInvocation] = \
            utils.search_for_types(statement, {ast.Call, }, ast.stmt)[ast.Call]
        self.parent = parent
        self.parts = utils.tree_to_dict(statement, ast.AST)

    def statements_from_invocations(self) -> List[PythonStatementBlock]:
        pass


class PythonFunctionInvocation:
    def __init__(self, function_invocation: ast.Call, statement: PythonStatementBlock):
        method = True if isinstance(function_invocation.func, ast.Attribute) else False
        self.statement = statement
        self.qualifier_str = function_invocation.func.value.id if method else None
        self.name = function_invocation.func.attr if method else function_invocation.func.id
