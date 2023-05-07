import datetime, time
import multiprocessing as mp
from typing import List, Dict, Iterable, Union
import requests
import pathlib
from subprocess import run, STDOUT
import re
from threading import Thread

from detection.abstract_scan import Report, AbstractProject
from detection.project_type_decison import create_project
from detection.definitions import number_of_tries_to_clone


def _generate_comparisons(projects, template_projs, fast_scan, queue):
    for template_pr in template_projs:
        for project in projects:
            yield template_pr, project, fast_scan, queue
    for idx, project in enumerate(projects[:-1]):
        for other_project in projects[idx + 1 :]:
            yield project, other_project, fast_scan, queue


def __compare_wrapper(args_tuple):
    first_project, other_project, fast_scan, queue = args_tuple
    queue.put(1)
    return first_project.compare(other_project, fast_scan)


def _project_list_to_dict(
    projects: List[AbstractProject],
) -> Dict[str, List[AbstractProject]]:
    projects_by_type = dict()
    for project in projects:
        if project.project_type not in projects_by_type.keys():
            projects_by_type.update({project.project_type: [project]})
        elif project.size() > 0:
            projects_by_type[project.project_type].append(project)
    return projects_by_type


def _print_progress(final_num: int, queue: mp.Queue):
    begin_time = datetime.datetime.now()
    list_len = queue.qsize()
    while list_len != final_num:
        if list_len != 0:
            print(
                f"\rRemaining time: {(final_num - list_len) * ((datetime.datetime.now() - begin_time) / list_len)}",
                end="",
            )
        time.sleep(2)
        list_len = queue.qsize()


def parallel_compare_projects(
    projects: List[AbstractProject],
    *,
    cpu_count: int = mp.cpu_count() - 1,
    fast_scan: bool,
) -> List[Report]:
    """Compare list of project to produce a list of pairwise comparison results."""
    reports = []
    projects_by_types = _project_list_to_dict(projects)
    total_comparisons_needed = 0
    for proj_type in projects_by_types:
        no_of_templates = len(
            list(
                filter(
                    lambda x: True if x.is_template else False,
                    projects_by_types[proj_type],
                )
            )
        )
        no_of_projects = len(
            list(
                filter(
                    lambda x: True if not x.is_template else False,
                    projects_by_types[proj_type],
                )
            )
        )
        total_comparisons_needed += no_of_projects * no_of_templates
        total_comparisons_needed += (no_of_projects * (no_of_projects - 1)) // 2
    manager = mp.Manager()
    queue = manager.Queue()
    timer = mp.Process(target=_print_progress, args=(total_comparisons_needed, queue))
    timer.start()
    with mp.Pool(cpu_count) as pool:
        for project_type in projects_by_types.keys():
            template_projs = [
                p for p in projects_by_types[project_type] if p.is_template
            ]
            actual_projects = [
                p for p in projects_by_types[project_type] if not p.is_template
            ]
            chunk_size = len(actual_projects) // cpu_count
            if chunk_size == 0:
                chunk_size = 1
            iterable_of_tuples = list(
                _generate_comparisons(actual_projects, template_projs, fast_scan, queue)
            )
            reports.extend(
                pool.imap(__compare_wrapper, iterable_of_tuples, chunksize=chunk_size)
            )
    timer.join()
    print()
    return reports


def __single_clone(dir_name: str, url: str, projects_dir: pathlib.Path):
    """Helper function. This is not supposed to be a part of the API."""
    out = run(
        ["git", "-C", f"{projects_dir.absolute()}", "clone", url, dir_name],
        stderr=STDOUT,
    )
    return out


def __single_update(repo_dir):
    """Helper function. This is not supposed to be a part of the API."""
    out = run(["git", "-C", f"{repo_dir.absolute()}", "pull"], stderr=STDOUT)
    return out


def _single_clone_or_update(dir_name: str, url: str, projects_dir: pathlib.Path):
    """Function used as a target of multiprocessing. Better do not touch this one."""
    repo_dir = projects_dir / dir_name
    out = None
    if number_of_tries_to_clone < 1:
        raise ValueError(f"Invalid number of clone tries: {number_of_tries_to_clone}.")
    if repo_dir.exists():
        print(f"INFO: Updating {dir_name}...")
        for _ in range(number_of_tries_to_clone):
            out = __single_update(repo_dir)
            if not out.returncode:
                break
            time.sleep(1)
    else:
        print(f"INFO: Cloning: {dir_name}...")
        for _ in range(number_of_tries_to_clone):
            out = __single_clone(dir_name, url, projects_dir)
            if not out.returncode:
                break
            time.sleep(1)
    if out.returncode:
        print(
            f"""!!!

ERROR: Troubles appeared while cloning project {dir_name}. Perhaps token is needed in the URL? Or rate limiting?

!!!"""
        )


def parallel_clone_projects(
    group_id, token, clone_dir: pathlib.Path, regex_str: str
) -> List[str]:
    """Clone projects from GitLab group specified in the `.env` file.
    Returns list of groups where no suitable project was found."""

    if not group_id:
        raise EnvironmentError("Group ID must be specified.")

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
                if (
                    re.match(regex_str, project_json["name"], flags=re.IGNORECASE)
                    is not None
                ):
                    url = f"https://git:{token}@gitlab.com/{project_json['path_with_namespace']}.git"
                    dir_name = f"{group_json['path']}-{project_json['path']}"
                    thread = Thread(
                        target=_single_clone_or_update,
                        args=(dir_name, url, clone_dir),
                    )
                    threads.append(thread)
                    thread.start()
                    projects_found += 1
            if projects_found != 1:
                not_found_projects_in.append(group_json["path"])
        page += 1
        subgroups_json = requests.get(
            f"https://gitlab.com/api/v4/groups/{group_id}/subgroups?page={page}",
            headers={"PRIVATE-TOKEN": token},
        ).json()
    for thread in threads:
        thread.join()
    return not_found_projects_in


def parallel_clone_projects_from_url(
    urls: Union[Iterable[str], Dict[str, str]], clone_dir: pathlib.Path
):
    threads = []
    for url in urls:
        proj_name = ""
        if isinstance(urls, dict):
            proj_name = urls[url]
        if not proj_name:
            proj_name = url.rsplit("/", 1)[1].replace(".git", "")
        thread = Thread(
            target=_single_clone_or_update,
            args=(proj_name, url, pathlib.Path(clone_dir)),
        )
        threads.append(thread)
        thread.start()
    for thread in threads:
        thread.join()


def parallel_initialize_projects(
    projects_dir: pathlib.Path,
    *,
    template=False,
    skip_names: Iterable[str] = (),
    cpu_count: int = mp.cpu_count() - 1,
) -> List[AbstractProject]:
    """Loads projects from files to memory, creates a list of `Project` objects.
    Parameter `projects_dir` is the directory from which the projects shall be loaded."""
    if isinstance(projects_dir, str):
        projects_dir = pathlib.Path(projects_dir)
    if not projects_dir.is_dir():
        raise EnvironmentError("Project directory could not be found!")
    arg_list = [
        (d, template) for d in projects_dir.iterdir() if d.name not in skip_names
    ]
    chunk_size = len(arg_list) // cpu_count
    if chunk_size == 0:
        chunk_size = 1
    with mp.Pool(cpu_count) as pool:
        projects = pool.starmap(create_project, arg_list, chunksize=chunk_size)
    projects = [p for p in projects if p]
    return projects
