import ast
from pathlib import Path
from typing import List, Union, Set, Type, Dict

import javalang
from javalang import tree


def get_self_project_root() -> Path:
    """Returns path to the root location where the detection program is located. Needed for configuration purposes."""
    return Path(__file__).parent.parent


def get_java_files(project_dir: Union[str, Path]) -> List[Path]:
    """Return all files that contain the `.java` extension."""
    return [f for f in list(project_dir.glob("**/*.java")) if f.name != "module-info.java"]


def get_python_files(project_dir: Union[str, Path]) -> List[Path]:
    return [f for f in list(project_dir.glob("**/*.py")) if f.name != "__init__.py" and f.name != "__pycache__"]


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
    except javalang.parser.JavaSyntaxError:
        print(f"{java_file} contains syntax error")


def get_python_ast(python_file: Union[str, Path]) -> ast.Module:
    with open(python_file, "r") as inp_file:
        lines = "".join(inp_file.readlines())
    try:
        return ast.parse(lines)
    except SyntaxError:
        print(f"{python_file} contains syntax error")


def get_packages(project_dir: Union[str, Path]) -> Set[str]:
    """Return all packages located in the project."""
    ans = set()
    for file in get_java_files(project_dir):
        compilation_unit = get_java_ast(file)
        if compilation_unit and compilation_unit.package:
            ans.add(compilation_unit.package.name)
    return ans


def tree_to_dict(node, realm: Type) -> dict[Type, int]:
    ans: Dict[Type, int] = {}
    node_type = type(node)
    if node_type in ans.keys():
        ans.update({node_type: ans.get(node_type) + 1})
    else:
        ans.update({node_type: 1})
    for attribute in [a for a in dir(node) if not a.startswith('_')]:
        child = getattr(node, attribute, None)
        if not isinstance(child, realm):
            continue
        child_dict = tree_to_dict(child, realm)
        for key in child_dict:
            if key in ans.keys():
                ans.update({key: ans[key] + child_dict[key]})
            else:
                ans.update({key: child_dict[key]})
    return ans


def search_for_types(
    statement, block_types: Set[Type], realm: Type
) -> Dict[Type, List]:
    """Go through AST and fetch subtrees rooted in specified node types.
    Parameter `statement` represents AST, `block_types` is set of searched node types.
    Returns dictionary structured as so: `{NodeType1: [subtree1, subtree2, ...], NodeType2: [...]}`"""
    ans = {}
    if not isinstance(statement, realm):
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
        if isinstance(child, realm):
            dict_to_add = search_for_types(child, block_types, realm)
            for key in dict_to_add:
                if key in ans.keys():
                    ans.update({key: ans[key] + dict_to_add[key]})
                else:
                    ans.update({key: dict_to_add[key]})
    return ans
