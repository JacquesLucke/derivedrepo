import os
import git
import json

from os import PathLike
from typing import List, Union, Optional, Callable
from pathlib import Path

DeriveFunction = Callable[[Path], Path]

class DerivedGitRepo:
    source_path: Path
    source_repo: git.Repo
    local_path: Path
    remote_config: "RemoteConfig"
    derive: DeriveFunction

    @classmethod
    def new(cls,
            source_path: PathLike,
            local_path: PathLike,
            remote_config_path: PathLike,
            derive: DeriveFunction):
        self = DerivedGitRepo()
        self.source_path = Path(source_path)
        self.local_path = Path(local_path)
        self.remote_config = RemoteConfig.from_path(remote_config_path)

        self.source_repo = git.Repo(self.source_path)
        self.derive = derive

        if not self.local_path.is_dir():
            raise Exception("local path has to be a directory")

    def insert_commit(self, hexsha):
        self._ensure_local_path()

        self.source_repo.git.stash()
        self.source_repo.git.stash("apply")

    def _ensure_local_path(self):
        if not self.local_path.exists():
            os.makedirs(self.local_path)

class RemoteConfig:
    path: Path

    @classmethod
    def from_path(cls, path: PathLike):
        self = RemoteConfig()
        self.path = Path(path)
        return self

    @property
    def remote_paths(self):
        data = self._load()
        return data["paths"]

    def _load(self):
        self._ensure_file_exists()
        return read_json_from_file(self.path)

    def _ensure_file_exists(self):
        if not self.path.exists():
            os.makedirs(self.path.parent)
            write_json_to_file(self.path, {})


def write_json_to_file(path, data):
    with open(path, "wt") as fs:
        fs.write(json.dumps(data, indent=4))

def read_json_from_file(path):
    with open(path, "rt") as fs:
        return json.loads(fs.read())