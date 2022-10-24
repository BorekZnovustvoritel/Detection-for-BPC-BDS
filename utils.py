from pathlib import Path
from typing import List, Union, Set

import javalang
from javalang import tree


def get_self_project_root() -> Path:
    return Path(__file__).parent


def get_java_files(project_dir: Union[str, Path]) -> List[Path]:
    return list(project_dir.glob("**/*.java"))


def get_user_project_root(project_dir: Union[str, Path]) -> Path:
    root_paths = list(project_dir.glob("**/src/main/java"))
    if len(root_paths) > 2:
        raise FileExistsError(f"Found too many project roots: {root_paths}")
    return root_paths[0]


def get_ast(java_file: Union[str, Path]) -> javalang.tree.CompilationUnit:
    with open(java_file, 'r') as inp_file:
        lines = ''.join(inp_file.readlines())
    return javalang.parse.parse(lines)


def get_packages(project_dir: Union[str, Path]) -> Set[str]:
    ans = set()
    for file in get_java_files(project_dir):
        ans.add(get_ast(file).package.name)
    return ans
