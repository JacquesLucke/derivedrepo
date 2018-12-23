import os
import sys
import git
import time
import click
import datetime
import itertools
from pathlib import Path
from collections import defaultdict
from derivedrepo import DerivedGitRepo, Logger
from derivedrepo.utils import clear_directory

def safe_cli():
    try: cli()
    except Exception as e:
        click.echo("Error: " + str(e), err=True)
        sys.exit(1)

@click.group()
def cli():
    pass


@cli.command()
@click.argument('source', type=click.Path(exists=True, dir_okay=True, file_okay=False))
def init(source):
    source = Path(source).resolve()
    try:
        DerivedGitRepo.init(source, os.getcwd())
        print("Done.")
        print("Customize the derive.py file.")
    except Exception as e:
        print("Could not initialize:", str(e))

class NewSetLogger(Logger):
    def log_derive_start(self, commit):
        print("  Derive Start:", commit)

    def log_derive_finished(self, commit, output_dir, notes):
        print("  Finished. Output at", output_dir)
        print("  Notes:", notes)

    def log_derive_failed(self, commit, notes):
        print("  Failed.")
        print("  Notes:", notes)

    def log_derivative_stored(self, commit):
        print("  Stored.")


@cli.group(name="set")
def set_():
    pass

@set_.command(name="list")
@click.option("--local", is_flag=True)
@click.option("--remote", is_flag=True)
def set_list(local, remote):
    if not (local or remote):
        click.echo("Choose --local and/or --remote option")
        return

    drepo = get_drepo()
    if local:
        for local_set in drepo.get_local_sets():
            print(f"Local: {local_set.get_name()}")
    if remote:
        for remote_set in drepo.get_remote_sets():
            print(f"Remote: {remote_set.get_identifier()}")


@set_.group(name="new")
def set_new():
    pass

@set_new.command(name="id")
@click.argument("commit_id")
@click.option("--name", default="Test Set")
def set_new_id(commit_id, name):
    drepo = get_drepo()
    drepo.new_set(name, commit_id, NewSetLogger())

@set_new.group(name="latest")
def set_new_latest():
    pass

@set_new_latest.command(name="days")
@click.argument("days", type=click.IntRange(0))
@click.option("--branch", required=True)
@click.option("--name", required=True)
@click.option("--split", type=click.Choice(["", "days"]), default="")
def set_new_latest_days(days, branch, name, split):
    drepo = get_drepo()
    src_repo = drepo.get_source_repo()

    stop = time.time() - datetime.timedelta(days=days).total_seconds()
    all_commits = []

    for commit in src_repo.iter_commits(branch):
        if commit.committed_datetime.timestamp() < stop:
            break
        all_commits.append(commit)

    all_commits = list(reversed(all_commits))

    if split == "":
        drepo.new_set(name, all_commits, NewSetLogger())
    elif split == "days":
        commits_per_days = defaultdict(list)
        for commit in all_commits:
            date = str(commit.committed_datetime.date())
            commits_per_days[date].append(commit)
        for date, commits in commits_per_days.items():
            drepo.new_set(name + date, commits, NewSetLogger())

@set_new_latest.command(name="commits")
@click.argument("amount", type=click.IntRange(0))
@click.option("--branch", required=True)
@click.option("--name", required=True)
def set_new_latest_commits(amount, branch, name):
    drepo = get_drepo()
    src_repo = drepo.get_source_repo()
    commits = list(itertools.islice(src_repo.iter_commits(branch), amount))
    drepo.new_set(name, list(reversed(commits)), NewSetLogger())


@cli.command()
@click.argument("id")
def checkout(id):
    drepo = get_drepo()
    src_repo = drepo.get_source_repo()
    commit = src_repo.commit(id)
    drepo.checkout(commit.hexsha)

def abort_if_false(ctx, param, value):
    if not value:
        ctx.abort()

@cli.group()
def clear():
    pass

@clear.command(name="all")
@click.option(
        '--yes', is_flag=True,
        callback=abort_if_false,
        expose_value=False,
        prompt="Are you sure that all folders in the cwd should be removed?")
def clear_all():
    get_drepo()
    clear_directory(Path(os.getcwd()))
    print("Directory cleared.")

@clear.command(name="local")
@click.option(
        '--yes', is_flag=True,
        callback=abort_if_false,
        expose_value=False,
        prompt="Are you sure that all generated data should be removed?")
def clear_local():
    drepo = get_drepo()
    clear_directory(drepo.default_checkout_dir)
    clear_directory(drepo.local_sets_dir)
    clear_directory(drepo.worktrees_dir)

@cli.command()
@click.option("--commits", is_flag=True, help="Show all commits and their titles.")
def status(commits):
    drepo = get_drepo()
    drepo.dump_status(show_commits=commits)

@cli.group()
def remote():
    pass

@remote.command(name="add")
@click.argument("path")
def remote_add(path):
    drepo = get_drepo()
    drepo.add_remote(path)

@remote.command(name="list")
def remote_list():
    drepo = get_drepo()
    for set_collection in drepo.get_remote_set_collections():
        print(set_collection.get_identifier())

@remote.command(name="rm")
@click.argument("path")
def remote_rm(path):
    drepo = get_drepo()
    drepo.remove_remote(path)

def get_drepo() -> DerivedGitRepo:
    return DerivedGitRepo(os.getcwd())

if __name__ == "__main__":
    cli()