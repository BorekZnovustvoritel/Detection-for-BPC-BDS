import datetime
import os

from detection.definitions import (
    env_file as default_env,
    projects_dir as default_projects_dir,
    templates_dir as default_templates_dir,
    project_regex as default_regex,
    default_output_file_name,
    cpu_count as default_cpu_count,
)
from detection.compare import print_path, create_excel
from detection.project_type_decison import determine_type_of_project
from detection.parallelization import (
    parallel_compare_projects,
    parallel_clone_projects,
    parallel_initialize_projects,
    parallel_clone_projects_from_url,
)
from detection.utils import parse_projects_file

from pathlib import Path
import argparse
from dotenv import load_dotenv


def main(args: argparse.Namespace):
    projects_dir_path = Path(args.projects_directory)
    if not projects_dir_path.exists():
        os.mkdir(projects_dir_path)
    templates_dir_path = Path(args.templates_directory)
    if not templates_dir_path.exists():
        os.mkdir(templates_dir_path)

    not_founds = []
    start = datetime.datetime.now()
    if not args.offline:
        print("INFO: Cloning from Git repositories...")
        load_dotenv(Path(args.env))

        token = os.getenv("TOKEN")
        group_id = os.getenv("BDS_PROJECTS_SUBGROUP_YEAR_ID")
        if args.token:
            token = args.token
        if args.group_id:
            not_founds = parallel_clone_projects(
                args.group_id, token, projects_dir_path, args.project_name_regex
            )
        elif group_id:
            not_founds = parallel_clone_projects(
                group_id, token, projects_dir_path, args.project_name_regex
            )
        else:
            print("INFO: GitLab cloning not set.")
    if args.projects_file:
        try:
            projects = parse_projects_file(args.projects_file)
            parallel_clone_projects_from_url(projects, projects_dir_path)
        except Exception:
            print(f"ERROR: Could not read file {args.projects_file}.")
    if args.templates_file:
        try:
            templates = parse_projects_file(args.templates_file)
            parallel_clone_projects_from_url(templates, templates_dir_path)
        except Exception:
            print(f"ERROR: Could not read file {args.templates_file}.")
    print(f"INFO: Cloning from Git repositories took {datetime.datetime.now() - start}")

    after_cloning = datetime.datetime.now()
    if args.clone_only:
        print("INFO: Only cloning requested, stopping the program.")
        return
    print("INFO: Loading projects to memory...")
    projects = parallel_initialize_projects(projects_dir_path, cpu_count=args.cpu)
    project_names = set(p.name for p in projects)
    projects.extend(
        parallel_initialize_projects(
            templates_dir_path,
            template=True,
            skip_names=project_names,
            cpu_count=args.cpu,
        )
    )
    after_parsing = datetime.datetime.now()
    print(f"INFO: Parsing took {after_parsing - after_cloning}.")
    print("INFO: Comparing...")
    reports = parallel_compare_projects(
        projects, fast_scan=args.fast, cpu_count=args.cpu
    )
    after_comparison = datetime.datetime.now()
    print(f"INFO: Comparing took {after_comparison - after_parsing}.")
    print(f"INFO: Total comparisons: {len(reports)}")

    if args.debug:
        for report in reports:
            print(
                f"DEBUG: Comparing projects: '{report.first.name}' and '{report.second.name}'"
            )
            print(print_path(report))
    empty_projects = [
        p.name
        for p in filter(
            lambda x: True if not determine_type_of_project(x) else False,
            projects_dir_path.iterdir(),
        )
    ]

    if reports:
        print("INFO: Creating Excel...")
        create_excel(
            reports,
            empty_projects,
            not_founds,
            args.out,
            three_color=args.legacy_color,
            show_weight=args.weight,
        )
        print(
            f"INFO: Creating Excel took {datetime.datetime.now() - after_comparison}."
        )
    else:
        print("WARNING: Nothing was compared.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Similarity check for Java and Python."
    )
    parser.add_argument(
        "-o",
        "--out",
        default=default_output_file_name,
        help=f"Output xlsx file name. Defaults to '{default_output_file_name}'.",
    )
    parser.add_argument(
        "-e",
        "--env",
        default=default_env,
        help="Specify different path to .env file containing GitLab details.",
    )
    parser.add_argument(
        "-p",
        "--projects-file",
        help="Point to a file containing a list of urls to projects hosted on Git. The format is <url> <name>, one project per row.",
    )
    parser.add_argument(
        "-t",
        "--templates-file",
        help="Point to a file containing a list of urls to templates hosted on Git. The format is <url> <name>, one project per row.",
    )
    parser.add_argument(
        "--token", help="GitLab access token for access to GitLab groups."
    )
    parser.add_argument(
        "-g", "--group-id", help="GitLab group ID which contains students' subgroups."
    )
    parser.add_argument(
        "-off",
        "--offline",
        action="store_true",
        default=False,
        help="Force offline mode even if env file is found.",
    )
    parser.add_argument(
        "-co",
        "--clone-only",
        action="store_true",
        default=False,
        help="Stop the program after the cloning commands are finished.",
    )
    parser.add_argument(
        "-w",
        "--weight",
        action="store_true",
        default=False,
        help="Show weight (confidence) of the match in the comparison output detail.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        default=False,
        help="This will produce a lot of output. Use with caution.",
    )
    parser.add_argument(
        "-f",
        "--fast",
        action="store_true",
        default=False,
        help="Run faster at the cost of lower accuracy. Non-similar projects are affected the most.",
    )
    parser.add_argument(
        "--cpu",
        type=int,
        default=default_cpu_count,
        help=f"Number of CPU cores. Defaults to {default_cpu_count} (Number of cores - 1).",
    )
    parser.add_argument(
        "-pd",
        "--projects-directory",
        default=default_projects_dir,
        help=f"Specify directory where projects should be cloned and/or processed. Defaults to {default_projects_dir}",
    )
    parser.add_argument(
        "-td",
        "--templates-directory",
        default=default_templates_dir,
        help=f"Specify directory where templates should be cloned and/or processed. Defaults to {default_templates_dir}",
    )
    parser.add_argument(
        "-lc",
        "--legacy-color",
        action="store_true",
        default=False,
        help="Make the output only 3 colors. Smoother, but less precise visualisation.",
    )
    parser.add_argument(
        "-re",
        "--project-name-regex",
        default=default_regex,
        help=f" Case insensitive regex specifying names to search for on GitLab. Defaults to '{default_regex}'.",
    )

    main(parser.parse_args())
