import datetime
import os

from detection.definitions import (
    env_file,
    projects_dir,
    templates_dir,
    templates,
    debug,
    offline,
    include_templates,
    project_regex,
    fast_scan,
    cpu_count,
    three_color,
)
from detection.utils import get_self_project_root
from detection.compare import print_path, create_excel
from detection.project_type_decison import determine_type_of_project
from detection.parallelization import (
    parallel_compare_projects,
    parallel_clone_projects,
    parallel_initialize_projects,
    parallel_clone_templates_from_url,
)

from pathlib import Path


def main():
    projects_dir_path = Path(projects_dir)
    if not projects_dir_path.exists():
        projects_dir_path = Path(get_self_project_root() / projects_dir)
        if not projects_dir_path.exists():
            os.mkdir(projects_dir_path)
    if include_templates:
        templates_dir_path = Path(templates_dir)
        if not templates_dir_path.exists():
            templates_dir_path = Path(get_self_project_root() / templates_dir)
            if not templates_dir_path.exists():
                os.mkdir(templates_dir_path)
    not_founds = []
    if not offline:
        env_file_path = Path(get_self_project_root() / env_file)
        if not env_file_path.exists():
            raise EnvironmentError(
                f"Could not find configured '{env_file}' environment file. See definitions.py."
            )
        print("Cloning from GitLab...")
        start = datetime.datetime.now()
        not_founds = parallel_clone_projects(
            env_file_path, projects_dir_path, project_regex
        )
        parallel_clone_templates_from_url(templates, templates_dir)
        print(f"Cloning from GitLab took {datetime.datetime.now() - start}")

    after_cloning = datetime.datetime.now()
    projects = parallel_initialize_projects(projects_dir_path, cpu_count=cpu_count)
    if include_templates:
        project_names = set(p.name for p in projects)
        projects.extend(
            parallel_initialize_projects(
                templates_dir_path,
                template=True,
                skip_names=project_names,
                cpu_count=cpu_count,
            )
        )
    after_parsing = datetime.datetime.now()
    print(f"Parsing took {after_parsing - after_cloning}.")
    print("Comparing...")
    reports = parallel_compare_projects(
        projects, fast_scan=fast_scan, cpu_count=cpu_count
    )
    after_comparison = datetime.datetime.now()
    print(f"Comparing took {after_comparison - after_parsing}.")
    print(f"Total comparisons: {len(reports)}")

    if debug:
        for report in reports:
            print(
                f"Comparing projects: '{report.first.path}' and '{report.second.path}'"
            )
            print(print_path(report))
    empty_projects = [
        p.name
        for p in filter(
            lambda x: True if not determine_type_of_project(x) else False,
            projects_dir_path.iterdir(),
        )
    ]
    create_excel(reports, empty_projects, not_founds, three_color=three_color)
    print(f"Creating Excel took {datetime.datetime.now() - after_comparison}.")


if __name__ == "__main__":
    main()
