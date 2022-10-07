from __future__ import annotations

import pathlib

import javalang
import javalang.tree
import pprint
from typing import List, Union, Set
import re

import definitions

pp = pprint.PrettyPrinter(indent=4)


# class JavaField:
#     def __init__(self, java_field: javalang.tree.FieldDeclaration):
#         #print(f"Field input type: {type(java_field)}")
#         self.java_field = java_field
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"
#
#
# class JavaMethodInvocation:
#     def __init__(self, java_method_invocation: javalang.tree.MethodInvocation):
#         self.java_method_invocation: javalang.tree.MethodInvocation = java_method_invocation
#         self.arguments: List[javalang.tree.Expression] = java_method_invocation.arguments   # TODO: use my types
#         self.method_name = java_method_invocation.member
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"
#
#
# class JavaLocalVariable(JavaVariable):
#     def __init__(self, java_variable: javalang.tree.VariableDeclarator):
#         super().__init__(java_variable)
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"
#
#
# class JavaAssignment:
#     def __init__(self, java_assignment: javalang.tree.Assignment):
#         self.java_assignment: javalang.tree.Assignment = java_assignment
#         self.variable_name: str = java_assignment.expressionl.member
#         self.value: javalang.tree.Expression = java_assignment.value    # TODO: use my types
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"
#
#
# class JavaExpression:
#     def __init__(self, java_statement: javalang.tree.StatementExpression):
#         self.java_statement: javalang.tree.StatementExpression = java_statement
#
#     def __repr__(self):
#         return f"< {self.__class__.__name__}: {self.__dict__}>"


class JavaMethod:
    def __init__(self, java_method: javalang.tree.MethodDeclaration, java_class: JavaClass):
        # print(f"Method input type: {type(java_method)}")
        # self.java_method: javalang.tree.MethodDeclaration = java_method
        self.java_class: JavaClass = java_class
        # self.body_blocks: list[javalang.tree.Expression] = []
        # self.local_variables: list[JavaVariable] = []
        self.return_type: JavaType = JavaType(getattr(java_method.return_type, "name", None), java_class)
        self.arguments: List[JavaVariable] = []
        for parameter in java_method.parameters:
            argument = JavaVariable(parameter)
            argument.type = JavaType(parameter.type.name, java_class)
            argument.modifiers = parameter.modifiers
            self.arguments.append(argument)
        self.arguments.sort(key=lambda x: getattr(x.type, 'type_name', None))
        self.name: str = java_method.name
        # self.assignments: list = [] #TODO
        # self.method_invocations: list = [] #TODO
        # for statement in java_method.body:
        #     if isinstance(statement, javalang.tree.TryStatement):
        #         self.body_blocks.extend(statement.block)
        #     else:
        #         self.body_blocks.append(statement)
        # for body_block in self.body_blocks:
        #     if isinstance(body_block, javalang.tree.LocalVariableDeclaration):
        #         self.local_variables.append(body_block)
        #     elif isinstance(body_block, javalang.tree.StatementExpression):
        #         if isinstance(body_block.expression, javalang.tree.Assignment):
        #             self.assignments.append(body_block.expression)
        #         elif isinstance(body_block.expression, javalang.tree.MethodInvocation):
        #             self.method_invocations.append(body_block.expression)
        #     else:
        #         pp.pprint(f"{type(body_block)} {body_block.__dict__}")
        #         raise ValueError(f"Unknown Body_block type: {type(body_block)}")

    def __repr__(self):
        return f"< {self.__class__.__name__}: {self.__dict__}>"

    def compare(self, other: JavaMethod) -> int:
        score = 0
        for argument in self.arguments:
            for other_argument in other.arguments:
                score += argument.compare(other_argument)
        score //= (len(self.arguments) * len(other.arguments))
        score //= 2
        score += self.return_type.compare(other.return_type) // 2
        print(f"Comparing methods: {self.name}, {other.name}. Score: {score}")
        return score


class JavaClass:
    def __init__(self, java_class: javalang.tree.ClassDeclaration, java_file: JavaFile):
        # print(f"Class input type: {type(java_class)}")
        # pp.pprint(java_class.__dict__)
        # self.java_class: javalang.tree.ClassDeclaration = java_class
        self.java_file: JavaFile = java_file
        self.name: str = java_class.name
        # self.fields = []
        self.methods: List[JavaMethod] = []
        self.variables: List[JavaVariable] = []
        for field in java_class.fields:
            # self.fields.append(JavaField(field))
            for declarator in field.declarators:
                if isinstance(declarator, javalang.tree.VariableDeclarator):
                    variable = JavaVariable(declarator)
                    variable.type = JavaType(field.type.name, self)
                    variable.modifiers = field.modifiers
                    self.variables.append(variable)
        self.variables.sort(key=lambda x: getattr(x.type, 'type_name', None))
        for method in java_class.methods:
            self.methods.append(JavaMethod(method, self))

    def __repr__(self):
        return f"< {self.__class__.__name__}: {self.__dict__}>"

    def compare(self, other: JavaClass) -> int:
        """Returns value between 0 and 100 based on the likelihood of plagiarism."""
        score = 0
        for method in self.methods:
            for other_method in other.methods:
                score += method.compare(other_method)
        score //= (len(self.methods) * len(other.methods))
        score //= 2
        temp_score = 0
        for variable in self.variables:
            for other_variable in other.variables:
                temp_score += variable.compare(other_variable)
        temp_score //= len(self.variables * len(other.variables))
        temp_score //= 2
        return score + temp_score


class JavaFile:
    def __init__(self, path: Union[str, pathlib.Path], project: Project):
        with open(path, 'r') as inp_file:
            lines = ''.join(inp_file.readlines())
        compilation_unit = javalang.parse.parse(lines)
        self.project: Project = project
        self.path: pathlib.Path = pathlib.Path(path) if not isinstance(path, pathlib.Path) else path
        self.package: str = compilation_unit.package.name
        self.imports: List[str] = [i.path for i in compilation_unit.imports]
        self.import_types: List[str] = [i.split('.')[-1] for i in self.imports]
        self.classes: List[JavaClass] = [JavaClass(body, self) for body in compilation_unit.types]

    def __repr__(self):
        return f"< {self.__class__.__name__}: {self.__dict__}>"

    def compare(self, other: JavaFile) -> int:
        """Returns value between 0 and 100 based on the likelihood of plagiarism."""
        score = 0
        for cl in self.classes:
            for other_cl in other.classes:
                score += cl.compare(other_cl)
        score //= (len(self.classes) * len(other.classes))
        return score


class Project:
    def __init__(self, path: str):
        self.path: pathlib.Path = pathlib.Path(path)
        if not self.path.exists():
            raise ValueError(f"Given path does not exist: {path}")
        root_paths = [d for d in self.path.glob("**/src/main/java")]
        if len(root_paths) > 2:
            raise FileExistsError(f"Found too many project roots: {root_paths}")
        self.root_path = root_paths[0]
        self.packages: Set[str] = set()
        self.java_files: List[JavaFile] = []
        java_files = [f for f in self.root_path.glob("**/*.java")]
        for java_file in java_files:
            self.packages.add((str(java_file.parent).replace(str(self.root_path) + '/', '')).replace('/', '.'))
        for java_file in java_files:
            self.java_files.append(JavaFile(java_file, self))

    def __repr__(self):
        return f"< {self.__class__.__name__}: {self.__dict__}>"


class JavaType:
    def __init__(self, type_name: str, java_class: JavaClass):
        self.java_class: JavaClass = java_class
        self.is_user_defined: bool = False
        self.type_name: str = type_name
        if not type_name:
            return
        self.compatible_format: str = definitions.translation_dict.get(self.type_name)
        for imp in self.java_class.java_file.imports:
            if re.match(f"^.*{self.type_name}$", imp) is not None:
                package = imp.replace(f".{type_name}", '')
                if package in self.java_class.java_file.project.packages:
                    self.is_user_defined = True
                else:
                    self.is_user_defined = False
                break
        if self.type_name == self.java_class.name:
            self.is_user_defined = True

    def __repr__(self):
        return f"< {self.__class__.__name__}: {self.__dict__}>"

    def compare(self, other: JavaType) -> int:
        score = 0
        if self.type_name == other.type_name:
            score = 100
        elif self.compatible_format == other.type_name or self.type_name == other.compatible_format:
            score = 75
        elif self.compatible_format is not None and self.compatible_format == other.compatible_format:
            score = 50
        print(f"Comparing types: {self.type_name, other.type_name}, score: {score}")
        return score


class JavaVariable:
    def __init__(self, java_variable: javalang.tree.VariableDeclarator):
        # print(f"Variable input type: {type(java_variable)}")
        # pp.pprint(java_variable.__dict__)
        # self.java_variable: javalang.tree.VariableDeclarator = java_variable
        self.name: str = java_variable.name
        self.type: JavaType = None
        self.modifiers: set = None

    def __repr__(self):
        return f"< {self.__class__.__name__}: {self.__dict__}>"

    def compare(self, other: JavaVariable) -> int:
        score = 0
        for modifier in self.modifiers:
            if modifier in other.modifiers:
                score += 50 // len(self.modifiers)
        score += self.type.compare(other.type)
        if self.name == other.name:
            score += 50
        return score // 2


project = Project("/home/lmayo/Dokumenty/baklazanka/java_test/Projekt_BDS_3/")
files = [f for f in project.root_path.glob("**/App*.java")]
project_files = [f for f in filter(lambda x: True if x.path in files else False, project.java_files)]
print([f.path for f in project_files])
print(project_files[0].compare(project_files[1]))

# java_file = JavaFile("/home/lmayo/Dokumenty/baklazanka/java_test/Projekt_BDS_3/src/main/java/org/but/feec/projekt_bds_3/App.java")
# for c in java_file.classes:
#     pp.pprint(c.__dict__)
#


# with open("/home/lmayo/Dokumenty/baklazanka/java_test/Projekt_BDS_3/src/main/java/org/but/feec/projekt_bds_3/App.java", "r") as f:
#     lines = f.readlines()
# tree = javalang.parse.parse(''.join(lines))

# #pp.pprint(tree.types[0])
# pp.pprint(tree.imports)
# # pp.pprint(str(tree.types[0]))
# print(type(tree.package.name))#.package.__dict__)
# for body in tree.types:
#     java_class = JavaClass(body, None)
#     # pp.pprint(type(body))
#
# for i in java_class.methods[1].body_blocks:
#     pp.pprint(str(type(i)) + str(i.__dict__))
