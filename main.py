import datetime

import definitions
from gitlab import clone_projects
from definitions import env_file, projects_dir
from utils import get_self_project_root
from scan import Project
from compare import print_path, create_excel
from parallelization import parallel_compare_projects

from pathlib import Path

if __name__ == "__main__":

    env_file_path = Path(env_file)
    if not env_file_path.exists():
        env_file_path = Path(get_self_project_root() / env_file)
        if not env_file_path.exists():
            raise EnvironmentError(f"Could not find configured '{env_file}' environment file. See definitions.py.")

    projects_dir_path = Path(projects_dir)
    if not projects_dir_path.exists():
        projects_dir_path = Path(get_self_project_root() / projects_dir)
        if not projects_dir_path.exists():
            raise NotADirectoryError(f"Could not find '{projects_dir}' projects directory. See definitions.py.")

    # clone_projects(env_file_path, projects_dir_path)

    start = datetime.datetime.now()
    projects = []
    for project_path in projects_dir_path.iterdir():
        projects.append(Project(project_path))

    after_parsing = datetime.datetime.now()
    print(f"Parsing took {after_parsing - start}.")

    reports = parallel_compare_projects(projects)
    after_comparison = datetime.datetime.now()
    print(f"Comparing took {after_comparison - after_parsing}.")
    print(f"Total comparisons: {len(reports)}")

    if definitions.debug:
        for report in reports:
            print(f"Comparing projects: '{report.first.path}' and '{report.second.path}'")
            print(print_path(report))

    create_excel(reports)
    print(f"Creating Excel took {datetime.datetime.now() - after_comparison}.")

