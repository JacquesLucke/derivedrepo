import os
import git
import json
import time
import shutil
import string
import random
import datetime
import itertools
import functools
import traceback

from os import PathLike
from pathlib import Path
from typing import Any, List, Union, Optional, Callable, Tuple, Mapping

from . remotes import (
    RemoteRepoAdapter,
    FolderRepoGroupAdapter,
)

from . utils import (
    clear_directory,
    clear_working_dir,
    copy_working_dir,
    copy_to_working_dir,
    get_random_string,
    write_json_to_file,
    read_json_from_file,
)


DeriveFunction = Callable[[Path], Union[Tuple[PathLike, Mapping[str, Any]], None]]

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
    default_checkout_dir: Path
    local_repos_dir: Path
    config: "ConfigFile"

    derive: DeriveFunction

    def __init__(self,
            source_path: PathLike,
            local_dir: PathLike,
            derive: DeriveFunction):
        self.source_path = Path(source_path)
        self.source_repo = git.Repo(self.source_path)
        self.derive = derive

        self.local_dir = Path(local_dir)
        self.local_repos_dir = self.local_dir / "repos"
        self.default_checkout_dir = self.local_dir / "checkout"
        self.config = ConfigFile(self.local_dir / "config.json")

    @restore_source_repo
    def add_single(self, hexsha):
        commits = [self.source_repo.commit(hexsha)]
        self._add_derived_commits(commits)

    @restore_source_repo
    def add_last_n(self, branch, amount):
        commits = list(itertools.islice(self.source_repo.iter_commits(branch), amount))
        commits = list(reversed(commits))
        self._add_derived_commits(commits)

    @restore_source_repo
    def add_last_days(self, branch, days):
        stop = time.time() - datetime.timedelta(days=days).total_seconds()

        commits = []
        for commit in self.source_repo.iter_commits(branch):
            commit: git.Commit
            if commit.committed_datetime.timestamp() > stop:
                commits.append(commit)

        commits = list(reversed(commits))
        self._add_derived_commits(commits)

    def checkout(self, hexsha, directory: Optional[PathLike] = None) -> Path:
        if directory is None:
            directory = self.default_checkout_dir
        directory = Path(directory)

        repo = self._get_any_local_repo_with_commit(hexsha)
        if repo is None:
            remote_repo = self._get_any_remote_repo_with_commit(hexsha)
            if remote_repo is None:
                raise Exception("cannot find commit")
            self._ensure_local_repos_dir()
            repo = remote_repo.download(self.local_repos_dir / get_random_string(8))

        if not directory.exists():
            os.makedirs(directory)
        commit = repo.tags[hexsha].commit
        clear_directory(directory)
        repo.git.checkout(commit.hexsha)
        copy_working_dir(repo, directory)
        repo.git.checkout("empty")
        return directory

    def add_remote_file_repo_group(self, path: PathLike):
        self.config.add_remote_file_repo_group(Path(path))

    def upload_all(self):
        group = self._get_any_writeable_remote_repo_group()
        if group is None:
            raise Exception("cannot find writeable remote")

        for repo in self._iter_local_repos():
            group.upload_repo(repo)

    def _get_any_writeable_remote_repo_group(self) -> Optional[RemoteRepoAdapter]:
        for group in self.config.iter_remote_repo_groups():
            if not group.readonly:
                return group
        return None

    def _get_any_local_repo_with_commit(self, hexsha) -> Optional[git.Repo]:
        for repo in self._iter_local_repos_with_commit(hexsha):
            return repo
        return None

    def _get_any_remote_repo_with_commit(self, hexsha) -> Optional[RemoteRepoAdapter]:
        for repo in self._iter_remote_repos_with_commit(hexsha):
            return repo
        return None

    def _iter_remote_repos_with_commit(self, hexsha):
        for repo in self.config.iter_remote_repos():
            print(repo)
            print(repo.has_commit(hexsha))
            if repo.has_commit(hexsha):
                yield repo

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
        self._ensure_local_repos_dir()
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
            output = self.derive(self.source_path)
        except:
            traceback.print_exc()
            output = None

        if output is None:
            note = {"valid" : False}
        else:
            note = {"valid" : True, "data" : output[1]}
            output_dir = Path(output[0])
            clear_working_dir(dst_repo)
            copy_to_working_dir(output_dir, dst_repo)
            dst_repo.git.add(".")

        dst_repo.git.commit(
            "--allow-empty",
            m=src_commit.message,
            author=f"{src_commit.author.name} <{src_commit.author.email}>",
            date=str(src_commit.authored_date))

        dst_repo.git.tag(src_commit.hexsha)
        dst_repo.git.notes("add", "-m", json.dumps(note))

    def _ensure_local_dir(self):
        if not self.local_dir.exists():
            os.makedirs(self.local_dir)

    def _ensure_local_repos_dir(self):
        if not self.local_repos_dir.exists():
            os.makedirs(self.local_repos_dir)


class ConfigFile:
    path: Path

    def __init__(self, path: Path):
        self.path = path

    def iter_remote_repos(self):
        for group in self.iter_remote_repo_groups():
            yield from group.iter_repos()

    def iter_remote_repo_groups(self):
        data = self._load()
        for directory in data["fileRepoGroups"]:
            yield FolderRepoGroupAdapter(Path(directory))

    def add_remote_file_repo_group(self, directory: Path):
        data = self._load()
        if str(directory) not in data["fileRepoGroups"]:
            data["fileRepoGroups"].append(str(directory))
            self._save(data)

    def _load(self):
        self._ensure_file_exists()
        data = read_json_from_file(self.path)
        data["fileRepoGroups"] = data.get("fileRepoGroups", [])
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
