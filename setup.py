from setuptools import setup, find_packages

setup(
    name='derivedrepo',
    version='0.1',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'click',
        'gitpython',
    ],
    entry_points={
        'console_scripts': [
            'derivedrepo = cli:safe_cli',
        ]
    },
)