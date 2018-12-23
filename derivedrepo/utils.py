import os
import git
import json
import random
import shutil
import string
from pathlib import Path

def clear_working_dir(repo: git.Repo):
    working_dir = Path(repo.working_dir)
    clear_directory(working_dir, {".git"})

def copy_working_dir(repo: git.Repo, dst: Path):
    working_dir = Path(repo.working_dir)
    copy_dir_content(working_dir, dst, {".git"})

def copy_to_working_dir(src: Path, repo: git.Repo):
    working_dir = Path(repo.working_dir)
    copy_dir_content(src, working_dir)

def clear_directory(dir_path: Path, excludes = set()):
    if not dir_path.exists():
        return
    for name in os.listdir(dir_path):
        if name in excludes:
            continue
        path = dir_path / name
        if path.is_file():
            os.remove(path)
        elif path.is_dir():
            shutil.rmtree(path)

def copy_dir_content(src: Path, dst: Path, excludes = set()):
    for name in os.listdir(src):
        if name in excludes:
            continue
        src_path = src / name
        dst_path = dst / name
        if src_path.is_file():
            shutil.copy2(src_path, dst_path)
        elif src_path.is_dir():
            shutil.copytree(src_path, dst_path, symlinks=True)

def write_json_to_file(path, data):
    write_text_file(path, json.dumps(data, indent=4))

def read_json_from_file(path):
    return json.loads(read_text_file(path))

def read_text_file(path):
    with open(path, "rt") as fs:
        return fs.read()

def write_text_file(path, text):
    with open(path, "wt") as fs:
        fs.write(text)

def exec_file(path):
    code = read_text_file(path)
    values = dict()
    exec(code, values, values)
    return values

def get_random_string(length):
    return "".join(random.choices(string.ascii_lowercase, k=length))

def make_path_absolute_if_relative(path: Path, default_root: Path):
    if path.is_absolute():
        return path
    else:
        return default_root / path

def ensure_dir_exists(path: Path):
    assert path.is_dir()
    if not path.exists():
        os.makedirs(path)