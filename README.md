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
- Fill in the `.env` file to find all necessary projects on GitLab

## Running the script
- On Linux: `source venv/bin/activate`, on Windows `venv\\Scripts\\activate`
- `python3 main.py`
