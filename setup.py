#!/usr/bin/env python

"""The setup script."""

from setuptools import setup, find_packages

with open("README.rst") as readme_file:
    readme = readme_file.read()

with open("HISTORY.rst") as history_file:
    history = history_file.read()

requirements = [
    "Click>=7.0",
    "pyyaml==6.0",
    "python-gantt==0.6.0",
    "python-gantt-csv==0.4.0",
    "pertchart==0.5.1",
    "criticalpath==0.1.5",
    "networkx==2.8.4",
    "pint==0.19.2",
    "pandas==1.4.3",
    "tabulate==0.8.10",
    "matplotlib==3.6.0",
]

test_requirements = [
    "pytest>=3",
]

setup(
    author="Martin Teller",
    author_email="martintellerpro@gmail.com",
    python_requires=">=3.7",
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Natural Language :: English",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
    ],
    description="package to define, visualize with gantt and budget "
    "projects using yaml syntax. ",
    entry_points={
        "console_scripts": [
            "md_planning=md_planning.cli:main",
        ],
    },
    install_requires=requirements,
    license="MIT license",
    long_description=readme + "\n\n" + history,
    include_package_data=True,
    keywords="md_planning project gantt PERT CPM budgeting budget visualization",
    name="md_planning",
    packages=find_packages(include=["md_planning", "md_planning.*"]),
    test_suite="tests",
    tests_require=test_requirements,
    url="https://github.com/mtllr/md_planning",
    version='0.5.0',
    zip_safe=False,
    project_urls={
        "Homepage": "https://github.com/mtllr/md_planning",
        "Documentation": "https://md-planning.readthedocs.io",
        "Buy me a coffee": "https://www.buymeacoffee.com/mtllr",
    },
)
