import os
import sys
import time
import click
import datetime
import itertools
from pathlib import Path
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
    def log_check_commit_to_derive(self, commit):
        print("Check commit:", commit)

    def log_commit_already_derived(self, commit):
        print("  Already derived.")

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
def set_list():
    drepo = get_drepo()
    for repo in drepo._iter_local_repos():
        print(repo)

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
def set_new_latest_days(days, branch, name):
    drepo = get_drepo()
    src_repo = drepo.get_source_repo()

    stop = time.time() - datetime.timedelta(days=days).total_seconds()
    commits = []

    for commit in src_repo.iter_commits(branch):
        if commit.committed_datetime.timestamp() < stop:
            break
        commits.append(commit)

    drepo.new_set(name, list(reversed(commits)), NewSetLogger())

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
    clear_directory(drepo.local_repos_dir)
    clear_directory(drepo.worktrees_dir)

@cli.command()
def status():
    drepo = get_drepo()
    drepo.dump_status()

def get_drepo() -> DerivedGitRepo:
    return DerivedGitRepo(os.getcwd())

if __name__ == "__main__":
    cli()