import multiprocessing as mp
from scan import Project, Report
from typing import List
from definitions import number_of_unused_cores
import requests
import pathlib
from dotenv import load_dotenv
from subprocess import DEVNULL, run
import os
from threading import Thread


def parallel_compare_projects(projects: List[Project]) -> List[Report]:
    reports = []
    with mp.Pool(mp.cpu_count() - number_of_unused_cores) as pool:
        for index, project in enumerate(projects[:-1]):
            reports.extend(pool.map(project.compare, projects[index + 1:]))
    return reports


def _single_clone(token: str, group_json, project_json, projects_dir: pathlib.Path):
    url = f"https://git:{token}@gitlab.com/{project_json['path_with_namespace']}.git"
    run(["git", "-C", f"{projects_dir.absolute()}", "clone", url, f"{group_json['path']}-{project_json['path']}"],
        stderr=DEVNULL)


def parallel_clone_projects(env_file: pathlib.Path, clone_dir: pathlib.Path):
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
            if "3" in project_json["name"]:
                thread = Thread(target=_single_clone, args=(token, group_json, project_json, clone_dir))
                threads.append(thread)
                thread.start()
    for thread in threads:
        thread.join()


def parallel_initialize_projects() -> List[Project]:
    pass
