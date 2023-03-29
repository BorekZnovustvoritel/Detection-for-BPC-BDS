import javalang
import ast
from javalang import tree
from datetime import datetime

translation_dict = {
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
}
projects_dir = "projects"
templates_dir = "templates"
env_file = ".env"
project_regex = r".*proj.*3"
number_of_unused_cores = 1
print_whole_tree = True
debug = False
offline = True
thorough_scan = True
include_templates = True
three_color = False
output_file_name = (
    f"bds-similarity-check-{datetime.now().strftime('%Y-%m-%d_%H-%M')}.xlsx"
)
templates = {
    "BDS-JavaFX-Training": "https://gitlab.com/but-courses/bpc-bds/seminar-projects/bds-javafx-training.git"
}
