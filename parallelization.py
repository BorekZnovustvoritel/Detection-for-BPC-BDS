import multiprocessing as mp
from scan import Project, Report
from typing import List
from definitions import number_of_unused_cores


def parallel_compare_projects(projects: List[Project]) -> List[Report]:
    reports = []
    with mp.Pool(mp.cpu_count() - number_of_unused_cores) as pool:
        for index, project in enumerate(projects[:-1]):
            reports.extend(pool.map(project.compare, projects[index + 1:]))
    return reports


def parallel_clone_projects():
    pass


def parallel_initialize_projects() -> List[Project]:
    pass
