from typing import Optional, Union, Type
from pathlib import Path

from detection.abstract_scan import AbstractProject
from detection.py_scan import PythonProject
from detection.java_scan import JavaProject

file_type_dict = {".java": JavaProject, ".py": PythonProject}


def determine_type_of_project(project_dir: Union[str, Path]) -> Optional[Type]:
    if not isinstance(project_dir, Path):
        project_dir = Path(project_dir)
    answers = dict()
    for extension in file_type_dict.keys():
        num_of_files = len(list(project_dir.glob(f"**/*{extension}")))
        if num_of_files > 0:
            answers.update({extension: num_of_files})
    if not answers:
        return
    return file_type_dict[max(answers, key=lambda x: answers[x])]


def create_project(directory: Union[str, Path]) -> Optional[AbstractProject]:
    proj_type = determine_type_of_project(directory)
    if proj_type:
        return proj_type(directory)
