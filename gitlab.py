import os
import requests
import pathlib
from dotenv import load_dotenv


def clone_projects(env_file: pathlib.Path, clone_dir: pathlib.Path):
    # os.path.realpath(pathlib.Path(__file__).parent)

    load_dotenv(env_file)

    token = os.getenv("TOKEN")
    group_id = os.getenv("BDS_PROJECTS_SUBGROUP_YEAR_ID")

    if not token or not group_id:
        raise EnvironmentError(".env file is not set up correctly.")

    git_return_val = os.system("git --version")
    if git_return_val != 0:
        raise EnvironmentError("Git is not installed on this system!")

    for group_json in requests.get(
        f"https://gitlab.com/api/v4/groups/{group_id}/subgroups",
        headers={"PRIVATE-TOKEN": token},
    ).json():
        for project_json in requests.get(
            f"https://gitlab.com/api/v4/groups/{group_json['id']}/projects",
            headers={"PRIVATE-TOKEN": token},
        ).json():
            if "3" in project_json["name"]:
                os.system(
                    f"git clone https://git:{token}@gitlab.com/{project_json['path_with_namespace']}.git "
                    f"{clone_dir}/{group_json['path']}-{project_json['path']}"
                )
