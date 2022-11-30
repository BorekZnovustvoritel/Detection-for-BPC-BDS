from pathlib import Path
from typing import List, Union, Set

import javalang
from javalang import tree


def get_self_project_root() -> Path:
    """Returns path to the root location where the detection program is located. Needed for configuration purposes."""
    return Path(__file__).parent.parent


def get_java_files(project_dir: Union[str, Path]) -> List[Path]:
    """Return all files that contain the `.java` extension."""
    return list(project_dir.glob("**/*.java"))


def get_user_project_root(project_dir: Union[str, Path]) -> Path:
    """Return path to the root of compared project's source files."""
    if isinstance(project_dir, str):
        project_dir = Path(project_dir)
    root_paths = list(project_dir.glob("**/src/main/java"))
    if len(root_paths) > 2:
        raise FileExistsError(f"Found too many project roots: {root_paths}")
    if len(root_paths) < 1:
        return project_dir
    return root_paths[0]


def get_ast(java_file: Union[str, Path]) -> javalang.tree.CompilationUnit:
    """Return AST of the java file."""
    with open(java_file, "r") as inp_file:
        lines = "".join(inp_file.readlines())
    return javalang.parse.parse(lines)


def get_packages(project_dir: Union[str, Path]) -> Set[str]:
    """Return all packages located in the project."""
    ans = set()
    for file in get_java_files(project_dir):
        ans.add(get_ast(file).package.name)
    return ans
