# Plagiarism detection tool for FEEC BUT
This tool is designed for the needs of subject BPC-BDS on FEEC BUT.

## Installation

### Prerequisites
- `python3` (Can be checked with `python3 --version`)
- `pip` (Should be part of `python`, can be checked with `pip --version`)
- `venv` (Should be part of `python`, can be checked with `python3 -m venv --help`)
- `git` (Can be checked with `git --version`. On Windows install the `git-cli` application.)

### Setting things up
- `python3 -m venv venv` (`python3` command line utility may be called `py` on Windows)
- On Linux: `source venv/bin/activate`, on Windows `venv\\Scripts\\activate`
- `pip install -r dependencies.txt`
- **Optional:** Fill in the `.env` file to find all necessary projects on GitLab (for online use only)

### Offline use
- Create directory `projects` in this directory.
- **Optional:** create directory `templates` in this directory if you want to use templates.
- Check if in `detection/definitions.py` the options are set to `offline = True` and `include_templates = True` or `False`.
- Paste all student's projects to the `projects` directory, name these directories like you want them to be presented in the result (e.g. rename `project 1` to `name-surname-id`)
- **Optional:** Paste all templates (projects from previous years or teacher's work) to the `templates` directory, also name them accordingly.
- **DO NOT CREATE DUPLICATE DIRECTORY NAMES IN `templates` AND IN `projects`!** If you do, the duplicate-named templates will be skipped.

## Running the script
- On Linux: `source venv/bin/activate`, on Windows `venv\\Scripts\\activate`
- `python3 main.py`
