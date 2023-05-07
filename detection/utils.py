import ast
import pathlib
from pathlib import Path
from typing import List, Union

import javalang
from javalang import tree


def get_java_files(project_dir: Union[str, Path]) -> List[Path]:
    """Return all suitable files that contain the `.java` extension."""
    return [
        f for f in list(project_dir.glob("**/*.java")) if f.name != "module-info.java"
    ]


def get_python_files(project_dir: Union[str, Path]) -> List[Path]:
    """Return all suitable files that contain the `.py` extension."""
    return [
        f
        for f in list(project_dir.glob("**/*.py"))
        if f.name != "__init__.py" and "__pycache__" not in str(f.absolute())
    ]


def get_user_project_root(project_dir: Union[str, Path]) -> Path:
    """Return path to the root of compared project's source files."""
    if isinstance(project_dir, str):
        project_dir = Path(project_dir)
    root_paths = list(project_dir.glob("**/src/main/java"))
    root_paths.sort(key=lambda x: len(x.parts))
    if len(root_paths) < 1:
        return project_dir
    return root_paths[0]


def get_java_ast(java_file: Union[str, Path]) -> javalang.tree.CompilationUnit:
    """Return AST of the java file."""
    with open(java_file, "r") as inp_file:
        lines = "".join(inp_file.readlines())
    try:
        return javalang.parse.parse(lines)
    except Exception as e:
        print(
            f"ERROR: Problem encountered while parsing file {java_file}. Problem type: {type(e).__name__}."
        )


def get_python_ast(python_file: Union[str, Path]) -> ast.Module:
    """Return AST of the Python file."""
    with open(python_file, "r") as inp_file:
        lines = "".join(inp_file.readlines())
    try:
        return ast.parse(lines)
    except Exception as e:
        print(
            f"ERROR: Problem encountered while parsing file {python_file}. Problem type: {type(e).__name__}."
        )


def calculate_score_based_on_numbers(first: int, second: int) -> int:
    """Calculate a pair-wise metric based on number of occurrences of an element.
    Parameters represent the numbers of occurrences in each parent entity."""
    if first == 0 and second == 0:
        return 100
    return int(100 - 100 * (abs(first - second) / (first + second)))


def parse_projects_file(path: Union[pathlib.Path]) -> dict:
    """Read a file containing the list of projects to clone and compare.
    Outputs a dictionary containing url to clone from and the name for the project."""
    if not isinstance(path, pathlib.Path):
        path = pathlib.Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Could not find file {path}.")
    with open(path, "r") as file:
        lines = file.readlines()
    ans = dict()
    for line in lines:
        if not line:
            continue
        line = line.lstrip()
        split = list(line.split(" ", maxsplit=1))
        url = split[0].strip()
        name = ""
        if len(split) > 1:
            name = split[1].strip()
        if url:
            ans.update({url: name})
    return ans
