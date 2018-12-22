import os
import git
import shutil
from pathlib import Path
from typing import Tuple, Generator

from . utils import get_random_string


class RemoteRepoAdapter:
    def iter_commits(self) -> Generator[str, None, None]: ...
    def is_commit_valid(self, hexsha: str) -> bool: ...
    def has_commit(self, hexsha: str) -> bool: ...
    def download(self, dst: Path): ...

class RemoteRepoGroupAdapter:
    readonly: bool
    def iter_repos(self) -> Generator[RemoteRepoAdapter, None, None]: ...
    def upload_repo(self, repo: git.Repo): ...
    def remove_repo(self, repo: RemoteRepoAdapter): ...


class FileRepoAdapter(RemoteRepoAdapter):
    path: Path
    repo: git.Repo

    def __init__(self, path: Path):
        self.path = path
        self.repo = git.Repo(self.path)

    def iter_commits(self):
        for tag in self.repo.tags:
            name = str(tag.name)
            if len(name) == 40:
                yield name

    def has_commit(self, hexsha):
        return hexsha in self.repo.tags

    def is_commit_valid(self, hexsha):
        commit = self.repo.tags[hexsha]
        return "invalid" not in self.repo.git.notes("show", commit.hexsha)

    def download(self, dst: Path):
        new_repo = git.Repo.clone_from(str(self.path), str(dst))
        new_repo.git.checkout("empty")
        return new_repo

class FolderRepoGroupAdapter(RemoteRepoGroupAdapter):
    path: Path

    def __init__(self, path: Path):
        self.path = path
        self.readonly = False

    def iter_repos(self):
        for name in os.listdir(self.path):
            repo_path = self.path / name
            if repo_path.is_dir():
                repo = FileRepoAdapter(repo_path)
                yield repo


    def upload_repo(self, repo: git.Repo):
        name = Path(repo.git_dir).parent.name
        dst_path = self.path / name
        if dst_path.exists():
            name += "_" + get_random_string(5)
            dst_path = self.path / name

        git.Repo.clone_from(str(repo.git_dir), str(dst_path), bare=True)

    def remove_repo(self, repo: FileRepoAdapter):
        shutil.rmtree(repo.path)
