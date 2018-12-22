import os
import git
import json
import shutil
import string
import random
import itertools
import functools
import traceback

from os import PathLike
from pathlib import Path
from typing import List, Union, Optional, Callable, Tuple

from . utils import (
    clear_directory,
    clear_working_dir,
    copy_working_dir,
    copy_to_working_dir,
    get_random_string,
    write_json_to_file,
    read_json_from_file,
)


DeriveFunction = Callable[[Path], Union[PathLike, None]]

def restore_source_repo(function):
    @functools.wraps(function)
    def wrapper(self, *args, **kwargs):
        commit_before = self.source_repo.head.commit.hexsha
        self.source_repo.git.stash("push", "--keep-index")
        try:
            return function(self, *args, **kwargs)
        finally:
            self.source_repo.git.checkout(commit_before)
    return wrapper

class DerivedGitRepo:
    source_path: Path
    source_repo: git.Repo
    local_dir: Path
    remote_config: "RemoteConfig"
    derive: DeriveFunction
    checkout_dir: Path
    local_repos_dir: Path

    def __init__(self,
            source_path: PathLike,
            local_dir: PathLike,
            remote_config_path: PathLike,
            derive: DeriveFunction,
            *,
            checkout_dir: Optional[PathLike] = None):
        self.source_path = Path(source_path)
        self.local_dir = Path(local_dir)
        self.remote_config = RemoteConfig.from_path(remote_config_path)

        self.source_repo = git.Repo(self.source_path)
        self.derive = derive

        self.local_repos_dir = self.local_dir / "repos"

        if checkout_dir is None:
            self.checkout_dir = self.local_dir / "checkout"
        else:
            self.checkout_dir = Path(checkout_dir)

    @restore_source_repo
    def add_single(self, hexsha):
        commits = [self.source_repo.commit(hexsha)]
        self._add_derived_commits(commits)

    @restore_source_repo
    def add_last_n(self, branch, amount):
        commits = list(itertools.islice(self.source_repo.iter_commits(branch), amount))
        commits = list(reversed(commits))
        self._add_derived_commits(commits)

    def checkout(self, hexsha):
        for repo in self._iter_local_repos_with_commit(hexsha):
            self._ensure_checkout_dir()
            commit = repo.tags[hexsha].commit
            clear_directory(self.checkout_dir)
            repo.git.checkout(commit.hexsha)
            copy_working_dir(repo, self.checkout_dir)
            repo.git.checkout("empty")
            break
        else:
            raise Exception("cannot find commit")

    def add_remote_directory(self, path: PathLike):
        path = Path(path)
        self.remote_config.add_remote_directory(path)

    def _iter_local_repos_with_commit(self, hexsha):
        for repo in self._iter_local_repos():
            if hexsha in repo.tags:
                yield repo

    def _get_any_local_repo(self):
        for repo in self._iter_local_repos():
            return repo
        else:
            return self._new_local_repo()

    def _new_local_repo(self):
        name = get_random_string(10)
        path = self.local_repos_dir / name
        os.makedirs(path)
        repo = git.Repo.init(path)
        repo.git.commit("-m", "initial commit", "--allow-empty")
        repo.git.tag("empty")
        return repo

    def _get_local_repos(self):
        return list(self._iter_local_repos())

    def _iter_local_repos(self):
        self._ensure_local_dir()
        for name in os.listdir(self.local_repos_dir):
            path = self.local_repos_dir / name
            if path.is_dir():
                try: yield git.Repo(path)
                except: pass

    def _add_derived_commits(self, src_commits):
        dst_repo = self._get_any_local_repo()
        self._add_derived_commits_to_repo(dst_repo, src_commits)

    def _add_derived_commits_to_repo(self, dst_repo, src_commits):
        dst_repo.git.checkout("master")

        for src_commit in src_commits:
            if src_commit.hexsha in dst_repo.tags:
                continue
            self._insert_derived_commit(dst_repo, src_commit)

        dst_repo.git.checkout("empty")

    def _insert_derived_commit(self, dst_repo, src_commit):
        self.source_repo.git.checkout(src_commit.hexsha)

        try:
            output_dir = self.derive(self.source_path)
        except:
            traceback.print_exc()
            output_dir = None

        author = f"{src_commit.author.name} <{src_commit.author.email}>"
        date = str(src_commit.authored_date)

        if output_dir is None:
            dst_repo.git.commit("--allow-empty", m=src_commit.message, author=author, date=date)
            dst_repo.git.tag(src_commit.hexsha)
            dst_repo.git.notes(m="invalid")
        else:
            output_dir = Path(output_dir)
            clear_working_dir(dst_repo)
            copy_to_working_dir(output_dir, dst_repo)
            dst_repo.git.add(".")
            dst_repo.git.commit("--allow-empty", m=src_commit.message, author=author, date=date)
            dst_repo.git.tag(src_commit.hexsha)

    def _ensure_local_dir(self):
        if not self.local_dir.exists():
            os.makedirs(self.local_dir)

    def _ensure_checkout_dir(self):
        if not self.checkout_dir.exists():
            os.makedirs(self.checkout_dir)


class RemoteConfig:
    path: Path

    @classmethod
    def from_path(cls, path: PathLike):
        self = RemoteConfig()
        self.path = Path(path)
        return self

    @property
    def remote_directories(self):
        data = self._load()
        return tuple(data["remoteFolders"])

    def add_remote_directory(self, path: Path):
        data = self._load()
        if str(path) not in data["remoteFolders"]:
            data["remoteFolders"].append(str(path))
            self._save(data)

    def _load(self):
        self._ensure_file_exists()
        data = read_json_from_file(self.path)
        data["remoteFolders"] = data.get("remoteFolders", [])
        return data

    def _save(self, data):
        if not self.path.parent.exists():
            os.makedirs(self.path.parent)
        write_json_to_file(self.path, data)

    def _ensure_file_exists(self):
        if not self.path.parent.exists():
            os.makedirs(self.path.parent)
        if not self.path.exists():
            write_json_to_file(self.path, {})
