import os

from pathlib import Path

from . remotes import (
    FolderRepoGroupAdapter,
)

from . utils import (
    read_json_from_file,
    write_json_to_file
)

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
