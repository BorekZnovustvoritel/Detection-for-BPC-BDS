import multiprocessing
import multiprocessing as mp
from detection.abstract_scan import Report, AbstractProject
from detection.project_type_decison import create_project
from typing import List, Dict
from detection.definitions import number_of_unused_cores, project_regex
import requests
import pathlib
from dotenv import load_dotenv
from subprocess import DEVNULL, run
import os
import re
from threading import Thread


def _generate_comparisons(projects, templates):
    for template_pr in templates:
        for project in projects:
            yield template_pr, project
    for idx, project in enumerate(projects[:-1]):
        for other_project in projects[idx + 1:]:
            yield project, other_project


def _compare_wrapper(first_project, other_project):
    return first_project.compare(other_project)


def _project_list_to_dict(projects: List[AbstractProject]) -> Dict[str, List[AbstractProject]]:
    projects_by_type = dict()
    for project in projects:
        if project.project_type not in projects_by_type.keys():
            projects_by_type.update({project.project_type: [project]})
        elif project.size() > 0:
            projects_by_type[project.project_type].append(project)
    return projects_by_type


def parallel_compare_projects(projects: List[AbstractProject]) -> List[Report]:
    """Compare list of project to produce a list of pairwise comparison results."""
    reports = []
    projects_by_types = _project_list_to_dict(projects)
    with mp.Pool(mp.cpu_count() - number_of_unused_cores) as pool:
        for project_type in projects_by_types.keys():
            templates = [p for p in projects_by_types[project_type] if p.is_template]
            actual_projects = [p for p in projects_by_types[project_type] if not p.is_template]
            chunk_size = len(actual_projects) // (multiprocessing.cpu_count() - number_of_unused_cores)
            if chunk_size == 0:
                chunk_size = 1
            iterable_of_tuples = list(_generate_comparisons(actual_projects, templates))
            reports.extend(pool.starmap(_compare_wrapper, iterable_of_tuples, chunksize=chunk_size))
    return reports


def _single_clone(token: str, group_json, project_json, projects_dir: pathlib.Path):
    """Function used as a target of multiprocessing. Better do not touch this one."""
    url = f"https://git:{token}@gitlab.com/{project_json['path_with_namespace']}.git"
    dir_name = f"{group_json['path']}-{project_json['path']}"
    out = run(
        ["git", "-C", f"{projects_dir.absolute()}", "clone", url, dir_name],
        stderr=DEVNULL,
    )
    if out.returncode:
        repo_dir = projects_dir / dir_name
        run(["git", "-C", f"{repo_dir.absolute()}", "pull"])


def parallel_clone_projects(env_file: pathlib.Path, clone_dir: pathlib.Path) -> List[str]:
    """Clone projects from GitLab group specified in the `.env` file.
    Returns list of groups where no suitable project was found."""
    load_dotenv(env_file)

    token = os.getenv("TOKEN")
    group_id = os.getenv("BDS_PROJECTS_SUBGROUP_YEAR_ID")

    if not token or not group_id:
        raise EnvironmentError(".env file is not set up correctly.")

    git_return_val = run(["git", "--version"])
    if git_return_val.returncode != 0:
        raise EnvironmentError("Git is not installed on this system!")

    if not isinstance(clone_dir, pathlib.Path):
        clone_dir = pathlib.Path(clone_dir)
    threads = []
    not_found_projects_in = []
    page = 1
    subgroups_json = requests.get(
            f"https://gitlab.com/api/v4/groups/{group_id}/subgroups?page={page}",
            headers={"PRIVATE-TOKEN": token},
        ).json()
    while subgroups_json:
        for group_json in subgroups_json:
            projects_found = 0
            for project_json in requests.get(
                f"https://gitlab.com/api/v4/groups/{group_json['id']}/projects",
                headers={"PRIVATE-TOKEN": token},
            ).json():
                if re.match(project_regex, project_json["name"], flags=re.IGNORECASE) is not None:
                    thread = Thread(
                        target=_single_clone,
                        args=(token, group_json, project_json, clone_dir),
                    )
                    threads.append(thread)
                    thread.start()
                    projects_found += 1
            if projects_found != 1:
                not_found_projects_in.append(group_json['path'])
        page += 1
        subgroups_json = requests.get(
            f"https://gitlab.com/api/v4/groups/{group_id}/subgroups?page={page}",
            headers={"PRIVATE-TOKEN": token},
        ).json()
    for thread in threads:
        thread.join()
    return not_found_projects_in


def parallel_initialize_projects(projects_dir: pathlib.Path, *, template=False) -> List[AbstractProject]:
    """Loads projects from files to memory, creates a list of `Project` objects.
    Parameter `projects_dir` is the directory from which the projects shall be loaded."""
    if isinstance(projects_dir, str):
        projects_dir = pathlib.Path(projects_dir)
    if not projects_dir.is_dir():
        raise EnvironmentError("Project directory could not be found!")
    arg_list = [(d, template) for d in projects_dir.iterdir()]
    chunk_size = len(arg_list) // (mp.cpu_count() - number_of_unused_cores)
    if chunk_size == 0:
        chunk_size = 1
    with mp.Pool(mp.cpu_count() - number_of_unused_cores) as pool:
        projects = pool.starmap(create_project, arg_list, chunksize=chunk_size)
    projects = [p for p in projects if p]
    return projects
