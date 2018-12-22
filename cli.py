import os
import time
import click
import datetime
import itertools
from pathlib import Path
from derivedrepo import DerivedGitRepo
from derivedrepo.utils import clear_directory

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

@cli.group()
def derive():
    pass

@derive.command(name="current")
def derive_current():
    drepo = get_drepo()
    src_repo = drepo.get_source_repo()
    drepo.insert(src_repo.head.commit.hexsha)

@derive.command(name="commit")
@click.argument("id")
def derive_commit(id):
    drepo = get_drepo()
    drepo.insert(id)

@derive.group(name="last")
def derive_last():
    pass

@derive_last.command(name="commits")
@click.option("--amount", default=0)
@click.option("--branch", default="master")
def derive_last_commits(amount, branch):
    drepo = get_drepo()
    src_repo = drepo.get_source_repo()
    commits = list(itertools.islice(src_repo.iter_commits(branch), amount))
    drepo.insert(list(reversed(commits)))

@derive_last.command(name="days")
@click.option("--amount", default=0)
@click.option("--branch", default="master")
def derive_last_days(amount, branch):
    drepo = get_drepo()
    src_repo = drepo.get_source_repo()

    stop = time.time() - datetime.timedelta(days=amount).total_seconds()
    commits = []

    for commit in src_repo.iter_commits(branch):
        if commit.committed_datetime.timestamp() > stop:
            commits.append(commit)

    drepo.insert(list(reversed(commits)))

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

@cli.command()
def status():
    drepo = get_drepo()
    drepo.dump_status()

def get_drepo() -> DerivedGitRepo:
    return DerivedGitRepo(os.getcwd())

if __name__ == "__main__":
    cli()