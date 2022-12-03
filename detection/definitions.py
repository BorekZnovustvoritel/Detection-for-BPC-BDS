import javalang
from javalang import tree

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
}
projects_dir = "projects"
env_file = ".env"
project_regex = r"proj.*3"
number_of_unused_cores = 1
print_whole_tree = True
debug = False
offline = False
thorough_scan = True
