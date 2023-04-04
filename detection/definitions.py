import javalang
import ast
from javalang import tree
from datetime import datetime
from multiprocessing import cpu_count

type_translation_dict = {
    "short": "Double",
    "Short": "Double",
    "int": "Double",
    "Integer": "Double",
    "long": "Double",
    "Long": "Double",
    "float": "Double",
    "Float": "Double",
    "boolean": "Boolean",
    "char": "String",
    "Character": "String",
    "ArrayList": "List",
    "LinkedList": "List",
    "HashSet": "Set",
    "TreeSet": "Set",
    "HashMap": "Map",
    "TreeMap": "Map",
    "FloatProperty": "DoubleProperty",
    "IntegerProperty": "DoubleProperty",
    "LongProperty": "DoubleProperty",
}
node_translation_dict = {
    javalang.tree.WhileStatement: javalang.tree.ForStatement,
    javalang.tree.SwitchStatementCase: javalang.tree.IfStatement,
    ast.AsyncFunctionDef: ast.FunctionDef,
    ast.Await: ast.Call,
}
projects_dir = "projects"
templates_dir = "templates"
env_file = ".env"
project_regex = r".*proj.*3"
cpu_count = cpu_count() - 1
default_output_file_name = (
    f"bds-similarity-check-{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
)
