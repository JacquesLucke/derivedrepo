import os
import git
import json
import time
import shutil
import string
import random
import textwrap
import datetime
import itertools
import functools
import traceback

from os import PathLike
from pathlib import Path
from typing import Any, List, Union, Optional, Callable, Tuple, Mapping, Sequence

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
    write_text_file,
    exec_file,
    make_path_absolute_if_relative,
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

    derive_path: Path
    derive: DeriveFunction

    @classmethod
    def init(self, source_path: PathLike, local_dir: PathLike):
        if any(name for name in os.listdir(local_dir) if not name.startswith(".")):
            raise Exception("the directory is not empty")

        local_dir = Path(local_dir)
        config = ConfigFile(local_dir / "config.json")
        config.set_source_path(source_path)
        config.set_derive_path("derive.py")
        write_text_file(make_path_absolute_if_relative(config.get_derive_path(), local_dir), derive_file_template)
        return DerivedGitRepo(local_dir)

    def __init__(self, local_dir: PathLike):
        self.local_dir = Path(local_dir)
        self.local_repos_dir = self.local_dir / "repos"
        self.default_checkout_dir = self.local_dir / "checkout"
        self.generate_path = self.local_dir / "generate.py"

        config_path = self.local_dir / "config.json"
        if not config_path.exists():
            raise Exception("directory has no config.json")
        self.config = ConfigFile(config_path)

        self.source_path = self.config.get_source_path()
        self.source_repo = git.Repo(self.source_path)

        self.derive = None

    def _ensure_derive_function(self):
        if self.derive is None:
            values = exec_file(self.config.get_derive_path())
            self.derive = values["derive"]

    def get_source_repo(self):
        return self.source_repo

    @restore_source_repo
    def insert(self, commits: Union[str, Sequence[str]]):
        if isinstance(commits, str):
            commits = [commits]
        final_commits = []
        for commit in commits:
            if isinstance(commit, str):
                commit = self.source_repo.commit(commit)
            elif isinstance(commit, git.Commit):
                pass
            else:
                raise TypeError("expected commit or commit identifier")
            final_commits.append(commit)
        self._add_derived_commits(final_commits)

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

    def dump_status(self):
        print("Derived Repository in", self.local_dir)
        print("  Source:", self.source_path)
        print("  Local Repositories:")
        for repo in self._iter_local_repos():
            print(f"    {Path(repo.working_dir).name}")
        print("  Remote Groups:")
        for group in self.config.iter_remote_repo_groups():
            print("    Group at", group.path)

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
        self._ensure_derive_function()

        self.source_repo.git.checkout(src_commit.hexsha)

        custom_notes = dict()
        try:
            output_dir = self.derive(self.source_path, custom_notes)
        except:
            traceback.print_exc()
            output_dir = None

        if output_dir is None:
            note = {"valid" : False, "data" : custom_notes}
        else:
            note = {"valid" : True, "data" : custom_notes}
            output_dir = Path(output_dir)
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

    def set_source_path(self, path: Path):
        data = self._load()
        data["sourcePath"] = str(path)
        self._save(data)

    def get_source_path(self):
        return Path(self._load()["sourcePath"])

    def set_derive_path(self, path: Path):
        data = self._load()
        data["derivePath"] = str(path)
        self._save(data)

    def get_derive_path(self):
        return Path(self._load()["derivePath"])

    def _load(self):
        self._ensure_file_exists()
        data = read_json_from_file(self.path)
        data["fileRepoGroups"] = data.get("fileRepoGroups", [])
        data["sourcePath"] = data.get("sourcePath", None)
        data["derivePath"] = data.get("derivePath", None)
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


derive_file_template = textwrap.dedent('''\
    def derive(source):
        return None, dict()''')