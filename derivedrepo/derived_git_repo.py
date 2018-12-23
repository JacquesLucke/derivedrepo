import os
import git
import json
import shutil
import textwrap
import functools
import traceback

from os import PathLike
from pathlib import Path
from typing import Any, List, Union, Optional, Callable, Tuple, Mapping, Sequence

from . config import ConfigFile
from . logger import Logger
from . worktree import WorkTree
from . sets import LocalSet

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
    ensure_dir_exists,
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
    local_sets_dir: Path
    worktrees_dir: Path
    config: ConfigFile

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
        self.local_sets_dir = self.local_dir / "sets"
        self.default_checkout_dir = self.local_dir / "checkout"
        self.worktrees_dir = self.local_dir / "worktrees"

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
    def new_set(self, name: str, commits, logger=Logger()):
        if isinstance(commits, (str, git.Commit)):
            commits = [commits]

        final_commits = []
        for commit in commits:
            if isinstance(commit, str):
                commit = self.source_repo.commit(commit)
            elif isinstance(commit, git.Commit):
                if commit.repo != self.source_repo:
                    raise Exception("commit is not in correct repo")
            else:
                raise TypeError("expected commit or commit identifier")
            final_commits.append(commit)

        self._new_set(name, final_commits, logger)

    def checkout(self, hexsha, directory: Optional[PathLike] = None) -> Path:
        local_set = self._try_get_any_set_with_commit(hexsha)
        if local_set is None:
            raise Exception("cannot find a derived version of that commit")

        checkout_dir = self.default_checkout_dir if directory is None else Path(directory)
        local_set.checkout(hexsha, checkout_dir)

    def add_remote(self, path: PathLike):
        self.config.add_remote(Path(path))

    def remove_remote(self, path: PathLike):
        self.config.remove_remote(Path(path))

    def dump_status(self, *, show_commits=True):
        print("Derived Repository in", self.local_dir)
        print("  Source:", self.source_path)
        print("  Local Sets:")
        for local_set in self._iter_local_sets():
            commits = [self.source_repo.commit(hexsha) for hexsha in local_set.iter_commits()]
            print(f"    {local_set.get_name()}: {len(commits)} commits")
            if show_commits:
                for commit in commits:
                    print(f"      {commit.hexsha[:7]} - {commit.message.strip()}")
        print("  Remote Set Collections:")
        for set_collection in self.config.iter_remote_set_collections():
            remote_sets = list(set_collection.iter_sets())
            print(f"    Set Collection: {set_collection.get_identifier()}")
            for remote_set in remote_sets:
                commits = [self.source_repo.commit(hexsha) for hexsha in remote_set.iter_commits()]
                print(f"      {remote_set.get_name()}: {len(commits)} commits")
                if show_commits:
                    for commit in commits:
                        print(f"       {commit.hexsha[:7]} - {commit.message.strip()}")


    # Set Discovery
    ##########################################

    def _try_get_any_set_with_commit(self, hexsha, check_remotes = True):
        local_set = self._get_any_local_set_with_commit(hexsha)
        if local_set is not None:
            return local_set

        if check_remotes:
            remote_set = self._get_any_remote_set_with_commit(hexsha)
            if remote_set is not None:
                local_set = remote_set.download(self.local_sets_dir / remote_set.get_name())
                return local_set

        return None

    # Local Sets
    # -----------------------------

    def get_local_sets(self):
        return list(self._iter_local_sets())

    def _get_any_local_set_with_commit(self, hexsha):
        for local_set in self._iter_local_sets_with_commit(hexsha):
            return local_set
        return None

    def _iter_local_sets_with_commit(self, hexsha):
        for local_set in self._iter_local_sets():
            if local_set.has_commit(hexsha):
                yield local_set

    def _iter_local_sets(self):
        self._ensure_local_sets_dir()
        for name in os.listdir(self.local_sets_dir):
            path = self.local_sets_dir / name
            if path.is_dir():
                yield LocalSet(path)


    # Remote Sets
    # ------------------------------

    def get_remote_sets(self):
        return list(self._iter_remote_sets())

    def _get_any_remote_set_with_commit(self, hexsha):
        for remote_set in self._iter_remote_sets_with_commit(hexsha):
            return remote_set
        return None

    def _iter_remote_sets_with_commit(self, hexsha):
        for remote_collection in self.config.iter_remote_set_collections():
            for remote_set in remote_collection.iter_sets_with_commit(hexsha):
                yield remote_set

    def _iter_remote_sets(self):
        for remote_collection in self.config.iter_remote_set_collections():
            yield from remote_collection.iter_sets()


    # Remote Collections
    # ------------------------------

    def get_remote_set_collections(self):
        return list(self.config.iter_remote_set_collections())


    # Set generation
    ########################################

    def _new_set(self, name, src_commits, logger):
        worktree_dir = self.worktrees_dir / name
        final_dir = self.local_sets_dir / name
        if final_dir.exists():
            raise Exception("Set exists already")

        worktree = WorkTree(worktree_dir)

        for src_commit in src_commits:
            self._insert_derived_commit(worktree, src_commit, logger)

        worktree.finalize(final_dir)

    def _insert_derived_commit(self, worktree, src_commit, logger):
        self._ensure_derive_function()

        logger.log_checkout(src_commit)
        self.source_repo.git.checkout(src_commit.hexsha)

        custom_notes = dict()
        try:
            logger.log_derive_start(src_commit)
            output_dir = self.derive(self.source_path, custom_notes)
        except:
            traceback.print_exc()
            output_dir = None

        message = src_commit.summary
        author = f"{src_commit.author.name} <{src_commit.author.email}>"
        date = str(src_commit.committed_date)
        tags = {src_commit.hexsha}

        if output_dir is None:
            logger.log_derive_failed(src_commit, custom_notes)
            note = {"valid" : False, "data" : custom_notes}
            worktree.commit_no_change(message, author, date, tags, note)
        else:
            logger.log_derive_finished(src_commit, output_dir, custom_notes)
            note = {"valid" : True, "data" : custom_notes}
            output_dir = Path(output_dir)
            worktree.commit_state(output_dir, message, author, date, tags, note)

        logger.log_derivative_stored(src_commit)


    # Utils
    #########################################

    def _ensure_local_dir(self):
        ensure_dir_exists(self.local_dir)

    def _ensure_local_sets_dir(self):
        ensure_dir_exists(self.local_sets_dir)


derive_file_template = textwrap.dedent('''\
    def derive(source):
        return None, dict()''')