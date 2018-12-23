import os
import git
import shutil
from pathlib import Path
import typing as t

from . utils import (
    clear_directory,
    ensure_dir_exists,
)

class LocalSet:
    path: Path
    repo: git.Repo

    def __init__(self, path: Path):
        self.path = path
        self.repo = git.Repo(self.path)
        assert self.repo.bare

    def get_name(self):
        return self.path.name

    def has_commit(self, hexsha):
        return hexsha in self.repo.tags

    def checkout(self, hexsha, dst: Path):
        real_hexsha = self.repo.tags[hexsha].commit.hexsha

        ensure_dir_exists(dst)
        clear_directory(dst)
        temp_repo = self.repo.clone(dst, bare=False)
        temp_repo.git.checkout(real_hexsha)
        shutil.rmtree(dst / ".git")

    def iter_commits(self):
        yield from (tag.name for tag in self.repo.tags)

class RemoteSet:
    def get_name(self) -> str: ...
    def get_identifier(self) -> str: ...
    def has_commit(self, hexsha) -> bool: ...
    def download(self, dst: Path) -> LocalSet: ...
    def iter_commits(self) -> t.Generator[str, None, None]: ...

class RemoteSetCollection:
    def get_identifier(self) -> str: ...
    def iter_sets(self) -> t.Generator[RemoteSet, None, None]: ...
    def iter_sets_with_commit(self, hexsha: str) -> t.Generator[RemoteSet, None, None]: ...

class RemoteFolderSet(RemoteSet):
    path: Path
    repo: git.Repo

    def __init__(self, path: Path):
        self.path = path
        self.repo = git.Repo(self.path)

    def get_identifier(self):
        return str(self.path)

    def get_name(self):
        return self.path.name

    def has_commit(self, hexsha):
        return hexsha in self.repo.tags

    def iter_commits(self):
        yield from (tag.name for tag in self.repo.tags)

    def download(self, dst: Path):
        if dst.exists():
            raise Exception("Cannot download, the path exists already: " + dst)
        os.makedirs(dst)
        self.repo.clone(str(dst), bare=True)
        return LocalSet(dst)

class RemoteFolderSetCollection(RemoteSetCollection):
    path: Path

    def __init__(self, path: Path):
        self.path = path
        self.readonly = False

    def get_identifier(self):
        return str(self.path)

    def iter_sets_with_commit(self, hexsha):
        for remote_set in self.iter_sets():
            if remote_set.has_commit(hexsha):
                yield remote_set

    def iter_sets(self):
        for name in os.listdir(self.path):
            repo_path = self.path / name
            if repo_path.is_dir():
                try: yield RemoteFolderSet(repo_path)
                except: pass
