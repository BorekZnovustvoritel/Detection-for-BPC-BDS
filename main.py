import datetime
import os

from detection.definitions import env_file, projects_dir, debug
from detection.utils import get_self_project_root
from detection.compare import print_path, create_excel
from detection.parallelization import (
    parallel_compare_projects,
    parallel_clone_projects,
    parallel_initialize_projects,
)

from pathlib import Path

if __name__ == "__main__":
    env_file_path = Path(get_self_project_root() / env_file)
    if not env_file_path.exists():
        raise EnvironmentError(
            f"Could not find configured '{env_file}' environment file. See definitions.py."
        )

    projects_dir_path = Path(projects_dir)
    if not projects_dir_path.exists():
        projects_dir_path = Path(get_self_project_root() / projects_dir)
        if not projects_dir_path.exists():
            os.mkdir(projects_dir_path)

    print("Cloning from GitLab...")
    start = datetime.datetime.now()
    parallel_clone_projects(env_file_path, projects_dir_path)
    after_cloning = datetime.datetime.now()
    print(f"Cloning from GitLab took {after_cloning - start}")
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

    create_excel(reports)
    print(f"Creating Excel took {datetime.datetime.now() - after_comparison}.")
