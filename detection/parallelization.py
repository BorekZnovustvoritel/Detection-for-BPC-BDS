import multiprocessing as mp
from detection.scan import Project, Report
from typing import List
from detection.definitions import number_of_unused_cores, project_regex
import requests
import pathlib
from dotenv import load_dotenv
from subprocess import DEVNULL, run
import os
import re
from threading import Thread


def parallel_compare_projects(projects: List[Project]) -> List[Report]:
    """Compare list of project to produce a list of pairwise comparison results."""
    reports = []
    with mp.Pool(mp.cpu_count() - number_of_unused_cores) as pool:
        for index, project in enumerate(projects[:-1]):
            reports.extend(pool.map(project.compare, projects[index + 1 :]))
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


def parallel_clone_projects(env_file: pathlib.Path, clone_dir: pathlib.Path):
    """Clone projects from GitLab group specified in the `.env` file."""
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
    for group_json in requests.get(
        f"https://gitlab.com/api/v4/groups/{group_id}/subgroups",
        headers={"PRIVATE-TOKEN": token},
    ).json():
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
    for thread in threads:
        thread.join()


def parallel_initialize_projects(projects_dir: pathlib.Path) -> List[Project]:
    """Loads projects from files to memory, creates a list of `Project` objects.
    Parameter `projects_dir` is the directory from which the projects shall be loaded."""
    if isinstance(projects_dir, str):
        projects_dir = pathlib.Path(projects_dir)
    if not projects_dir.is_dir():
        raise EnvironmentError("Project directory could not be found!")
    with mp.Pool(mp.cpu_count() - number_of_unused_cores) as pool:
        projects = pool.map(Project, projects_dir.iterdir())
    return projects
