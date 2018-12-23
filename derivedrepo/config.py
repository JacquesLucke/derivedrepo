import os
import typing as t
from pathlib import Path

from . sets import (
    RemoteFolderSetCollection,
)

from . utils import (
    read_json_from_file,
    write_json_to_file
)

class ConfigFile:
    path: Path

    def __init__(self, path: Path):
        self.path = path

    def iter_remote_set_collections(self) -> t.Generator[RemoteFolderSetCollection, None, None]:
        data = self._load()
        for directory in data["remoteFolderSetCollections"]:
            yield RemoteFolderSetCollection(Path(directory))

    def add_remote_folder_set_collection(self, directory: Path):
        data = self._load()
        if str(directory) not in data["remoteFolderSetCollections"]:
            data["remoteFolderSetCollections"].append(str(directory))
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
        data["remoteFolderSetCollections"] = data.get("remoteFolderSetCollections", [])
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
