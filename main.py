import datetime
import os

from detection.definitions import env_file, projects_dir, debug, offline
from detection.utils import get_self_project_root
from detection.compare import print_path, create_excel
from detection.project_type_decison import determine_type_of_project
from detection.parallelization import (
    parallel_compare_projects,
    parallel_clone_projects,
    parallel_initialize_projects,
)

from pathlib import Path

if __name__ == "__main__":
    projects_dir_path = Path(projects_dir)
    if not projects_dir_path.exists():
        projects_dir_path = Path(get_self_project_root() / projects_dir)
        if not projects_dir_path.exists():
            os.mkdir(projects_dir_path)
    not_founds = []
    if not offline:
        env_file_path = Path(get_self_project_root() / env_file)
        if not env_file_path.exists():
            raise EnvironmentError(
                f"Could not find configured '{env_file}' environment file. See definitions.py."
            )
        print("Cloning from GitLab...")
        start = datetime.datetime.now()
        not_founds = parallel_clone_projects(env_file_path, projects_dir_path)
        print(f"Cloning from GitLab took {datetime.datetime.now() - start}")

    after_cloning = datetime.datetime.now()
    projects = parallel_initialize_projects(projects_dir_path)
    after_parsing = datetime.datetime.now()
    print(f"Parsing took {after_parsing - after_cloning}.")
    reports = parallel_compare_projects(projects)
    after_comparison = datetime.datetime.now()
    print(f"Comparing took {after_comparison - after_parsing}.")
    print(f"Total comparisons: {len(reports)}")

    if debug:
        for report in reports:
            print(
                f"Comparing projects: '{report.first.path}' and '{report.second.path}'"
            )
            print(print_path(report))
    empty_projects = [p.name for p in filter(lambda x: True if not determine_type_of_project(x) else False, projects_dir_path.iterdir())]
    python_reports = list(filter(lambda x: True if x.first.project_type == "Python" else False, reports))
    java_reports = list(filter(lambda x: True if x.first.project_type == "Java" else False, reports))
    create_excel(java_reports, python_reports, empty_projects, not_founds)
    print(f"Creating Excel took {datetime.datetime.now() - after_comparison}.")
