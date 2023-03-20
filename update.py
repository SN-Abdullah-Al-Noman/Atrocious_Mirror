from logging import FileHandler, StreamHandler, INFO, basicConfig, error as log_error, info as log_info
from os import path as ospath, environ, remove as osremove
from subprocess import run as srun, call as scall
from pkg_resources import working_set
from requests import get as rget

if ospath.exists('log.txt'):
    with open('log.txt', 'r+') as f:
        f.truncate(0)

basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[FileHandler('log.txt'), StreamHandler()],
                    level=INFO)

UPSTREAM_REPO = 'https://github.com/SN-Abdullah-Al-Noman/SN_WZML'
UPSTREAM_BRANCH = 'master'

if UPSTREAM_REPO is not None:
    if ospath.exists('.git'):
        srun(["rm", "-rf", ".git"])

    update = srun([f"git init -q \
                     && git config --global user.email doc.adhikari@gmail.com \
                     && git config --global user.name WZML \
                     && git add . \
                     && git commit -sm update -q \
                     && git remote add origin {UPSTREAM_REPO} \
                     && git fetch origin -q \
                     && git reset --hard origin/{UPSTREAM_BRANCH} -q"], shell=True)

    UPSTREAM_REPO_URL = (UPSTREAM_REPO[:8] if UPSTREAM_REPO[:8] and UPSTREAM_REPO[:8].endswith('/') else UPSTREAM_REPO[:7]) + UPSTREAM_REPO.split('@')[1] if '@github.com' in UPSTREAM_REPO else UPSTREAM_REPO    
    if update.returncode == 0:
        log_info(f'Successfully updated with latest commit from {UPSTREAM_REPO_URL}')
    else:
        log_error(f'Something went wrong while updating, check {UPSTREAM_REPO_URL} if valid or not!')
