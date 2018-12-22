import os
import click
from pathlib import Path
from derivedrepo import DerivedGitRepo

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

@cli.command()
def checkout():
    print("do checkout")

if __name__ == "__main__":
    cli()