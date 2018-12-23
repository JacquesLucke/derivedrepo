import os
import git
import json
import shutil
import typing as t

from pathlib import Path

from . utils import (
    ensure_dir_exists,
    clear_working_dir,
    copy_to_working_dir,
)

class WorkTree:
    path: Path
    repo: git.Repo

    def __init__(self, path: Path):
        if path.exists():
            raise Exception("directory exists already:", path)

        os.makedirs(path)
        self.path = path
        self.repo = git.Repo.init(path)

    def commit_state(self,
            source: Path,
            message: str, author: str, date: str,
            tags: t.Set[str], custom_notes: t.Dict[str, t.Any]):
        clear_working_dir(self.repo)
        copy_to_working_dir(source, self.repo)
        self._commit_current(message, author, date, tags, custom_notes)

    def commit_no_change(self,
            message: str, author: str, date: str,
            tags: t.Set[str], custom_notes: t.Dict[str, t.Any]):
        self._commit_current(message, author, date, tags, custom_notes)

    def _commit_current(self,
            message: str, author: str, date: str,
            tags: t.Set[str], custom_notes: t.Dict[str, t.Any]):
        self.repo.git.add(".")
        self.repo.git.commit(
            "--allow-empty",
            m=message,
            author=author,
            date=date)

        for tag in tags:
            self.repo.git.tag(tag)
        self.repo.git.notes("add", "-m", json.dumps(custom_notes))

    def finalize(self, dst: Path):
        repo = git.Repo.clone_from(str(self.path), str(dst), bare=True)
        shutil.rmtree(self.path)
        return repo