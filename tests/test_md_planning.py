#!/usr/bin/env python

"""Tests for `md_planning` package."""

import os
import pathlib
import pytest
import datetime
import re
import pandas as pd

from click.testing import CliRunner

from md_planning.md_planning import (
    GanttDrawer,
    PertDrawer,
    ProjectReader,
    rename,
    get_task_type,
)

from gantt import Resource, Task

from md_planning import cli

# TODO: (feature) nested milestones and tasks
# TODO: (feature) critical_color implementation
# TODO: (feature) get_critical_path implementation in GanttDrawer (consider refactoring PertDrawer out?)
# TODO: (bugfix) E17FB6 v0.2 error message shows what csv task and what is the offensive entry
# TODO: (refactor) consider remove get_task_type registration for List type

# BUG: if there is not at least one dependency between tasks then python-gantt does NOT create the svg
# TODO: (feature) assert that task names in a multiproject definition are unique for the whole definition file
# TODO: (refactor) data structure and project classes so the Resource class has methods: get_price, get_unit
# TODO: (refactor) data structure and project classes so the Task class has method: get_usage
# TODO: (refactor) data structure and project classes so the Project class has methods: get_unit, get_price, get_usage, get_cost
# TODO: (feature) when user makes task depend on milestone, KeyError is raised but it is difficult to find in which task the error was made
# TODO: (feature) when task depends on milestone, replace milestone dependency with the last critical task in this milestone but do not make this task critical globally in the project

@pytest.fixture
def flat_project():
    project_str = """
# Font:
#     fill: "#000000"
#     stroke: "black"
#     stroke_width: 0
#     font_family: Verdana
Vacations:
    - 2022-09-30
    - 2022-11-01
    - 2022-11-11
Resources:
    Martin:
        price:
            value: 68.75
            unit: workhour
        vacations:
            - 2022-09-15
    Samuel:
        price:
            value: 600
            unit:  workday
Projects:
    -   Name: Test1
        Tasks:
            kickoff:
                type: milestone
                depends_on: brief
            brief:
                type: task
                start: 2022-09-05
                duration: 0.125 # 1 hour
                percent_done: 0
                resources: null
                depends_on: null
            goals:
                type: task
                start: 2022-09-05
                duration: 0.25
                percent_done: 0
                resources: Martin
                depends_on: brief
            Env setup: [2022-09-06, 1, 0, "Martin", "goals"]
"""
    return project_str

@pytest.fixture
def nested_project():
    project_str = """
Font:
    fill: black
    font_family: Verdana
Vacations:
    - 2022-09-30
    - 2022-11-01
    - 2022-11-11
Resources:
    Martin:
        price:
            value: 68.75
            unit: hour
        vacations:
            - 2022-09-15
    Samuel:
        price:
            value: 600
            unit:  day
Projects:
    -   Name: Test1
        Tasks:
            kickoff:
                brief:
                    start: 2022-09-05
                    duration: 0.125 # 1 hour
                    percent_done: 0
                    resources: null
                    depends_on: null
            goals:
                start: 2022-09-05
                duration: 0.25
                percent_done: 0
                resources: Martin
            Env setup: [task, 2022-09-06, 1, 0, "Martin", "kickoff"]
"""
    return project_str

################################################################################
# UTILITY FUNCTIONS
################################################################################

def test_rename_strict():
    with pytest.raises(KeyError):
        _ = dict()
        rename(_, "a", "b")

def test_rename_flex_exists():
    _ = dict(a=1)
    res = rename(_, "a", "b", True)
    assert res == {"b": 1}

def test_rename_flex_not_exists():
    _ = dict()
    res = rename(_, "a", "b", True, 1)
    assert res == {"b": 1}

def test_get_task_type_flat_milestone():
    milestone = dict(type="milestone", depends_on=[])
    assert get_task_type(milestone) == "milestone"

def test_get_task_type_flat_task_dict():
    task = {
        "type": "task",
        "start": "",
        "duration": 1,
        "percent_done": 0,
        "resources": [],
        "depends_on": [],
        "color": None,
    }
    assert get_task_type(task) == "task"

def test_get_task_type_flat_task_list():
    task = ["2022-09-06", 1, 0, "Martin", "kickoff", None]
    assert get_task_type(task) == "task"

@pytest.mark.skip("Not Implemented")
def test_get_task_type_nested_milestone():
    pass

@pytest.mark.skip("Not Implemented")
def test_get_task_type_nested_task_dict():
    pass

@pytest.mark.skip("Not Implemented")
def test_get_task_type_nested_task_list():
    pass

################################################################################
# PROJECTREADER
################################################################################

def test_project_reader_build_flat_project_is_conformant(flat_project):
    p = ProjectReader(flat_project)
    projects, pertcharts = p.build_project()

    assert len(pertcharts) == 1
    assert len(projects["projects"]) == 1
    assert pertcharts == {
        "Test1": {
            "brief": {
                "Tid": "brief",
                "start": 0,
                "duration": 0.125,
                "end": 0,
                "responsible": "CRITICAL",
                "pred": ["START"],
            },
            "goals": {
                "Tid": "goals",
                "start": 0,
                "duration": 0.25,
                "end": 0,
                "responsible": "CRITICAL",
                "pred": ["brief"],
            },
            "Env setup": {
                "Tid": "Env setup",
                "start": 0,
                "duration": 1,
                "end": 0,
                "responsible": "CRITICAL",
                "pred": ["goals"],
            },
        }
    }
    assert projects == {
        # "font": {"fill": "black", "font_family": "Verdana"},
        "font": {},
        "vacations": [
            datetime.date(2022, 9, 30),
            datetime.date(2022, 11, 1),
            datetime.date(2022, 11, 11),
        ],
        "resources": {
            "Martin": {
                "price": {"value": 68.75, "unit": "workhour"},
                "vacations": [datetime.date(2022, 9, 15)],
            },
            "Samuel": {"price": {"value": 600, "unit": "workday"}},
        },
        "projects": {"Test1": None},
        "tasks": {
            "kickoff": {
                "project": "Test1",
                "task": {
                    "name": "kickoff",
                    "start": None,
                    "stop": None,
                    "duration": None,
                    "depends_of": None,
                    "resources": None,
                    "percent_done": 0,
                    "color": None,
                    "fullname": None,
                    "display": True,
                    "state": "",
                },
                "milestone": {
                    "name": "kickoff",
                    "start": None,
                    "depends_of": ["brief"],
                    "color": None,
                    "fullname": None,
                    "display": True,
                },
                "pertchart": {},
                "cpm": {
                    "name": "kickoff",
                    "duration": None,
                    "lag": 0,
                    "depends_of": None,
                },
                "is_milestone": True,
            },
            "brief": {
                "project": "Test1",
                "task": {
                    "name": "brief",
                    "start": datetime.date(2022, 9, 5),
                    "stop": None,
                    "duration": 0.125,
                    "depends_of": [],
                    "resources": [],
                    "percent_done": 0,
                    "color": None,
                    "fullname": None,
                    "display": True,
                    "state": "",
                },
                "milestone": {
                    "name": "brief",
                    "start": None,
                    "depends_of": None,
                    "color": None,
                    "fullname": None,
                    "display": True,
                },
                "pertchart": {
                    "Tid": "brief",
                    "start": 0,
                    "duration": 0.125,
                    "end": 0,
                    "responsible": "CRITICAL",
                    "pred": ["START"],
                },
                "cpm": {"name": "brief", "duration": 0.125, "lag": 0, "depends_of": []},
                "is_milestone": False,
            },
            "goals": {
                "project": "Test1",
                "task": {
                    "name": "goals",
                    "start": datetime.date(2022, 9, 5),
                    "stop": None,
                    "duration": 0.25,
                    "depends_of": ["brief"],
                    "resources": ["1 Martin"],
                    "percent_done": 0,
                    "color": None,
                    "fullname": None,
                    "display": True,
                    "state": "",
                },
                "milestone": {
                    "name": "goals",
                    "start": None,
                    "depends_of": None,
                    "color": None,
                    "fullname": None,
                    "display": True,
                },
                "pertchart": {
                    "Tid": "goals",
                    "start": 0,
                    "duration": 0.25,
                    "end": 0,
                    "responsible": "CRITICAL",
                    "pred": ["brief"],
                },
                "cpm": {
                    "name": "goals",
                    "duration": 0.25,
                    "lag": 0,
                    "depends_of": ["brief"],
                },
                "is_milestone": False,
            },
            "Env setup": {
                "project": "Test1",
                "task": {
                    "name": "Env setup",
                    "start": datetime.date(2022, 9, 6),
                    "stop": None,
                    "duration": 1,
                    "depends_of": ["goals"],
                    "resources": ["1 Martin"],
                    "percent_done": 0,
                    "color": None,
                    "fullname": None,
                    "display": True,
                    "state": "",
                },
                "milestone": {
                    "name": "Env setup",
                    "start": None,
                    "depends_of": None,
                    "color": None,
                    "fullname": None,
                    "display": True,
                },
                "pertchart": {
                    "Tid": "Env setup",
                    "start": 0,
                    "duration": 1,
                    "end": 0,
                    "responsible": "CRITICAL",
                    "pred": ["goals"],
                },
                "cpm": {
                    "name": "Env setup",
                    "duration": 1,
                    "lag": 0,
                    "depends_of": ["goals"],
                },
                "is_milestone": False,
            },
        },
    }

@pytest.mark.skip("Not Implemented")
def test_project_reader_build_nested_project_is_conformant(nested_project):
    p = ProjectReader(nested_project)
    projects, pertcharts = p.build_project()

    assert len(pertcharts) == 1
    assert len(projects["projects"]) == 1
    assert pertcharts == {
        "Test1": [
            {
                "name": "brief",
                "duration": 0.125,
                "lag": 0,
                "depends_on": None,
                "Tid": "brief",
                "start": 0,
                "end": 0,
                "responsible": "CRITICAL",
                "pred": [],
            },
            {
                "name": "goals",
                "duration": 0.25,
                "lag": 0,
                "depends_on": None,
                "Tid": "goals",
                "start": 0,
                "end": 0,
                "responsible": "CRITICAL",
                "pred": ["brief"],
            },
            {
                "name": "Env setup",
                "duration": 1,
                "lag": 0,
                "depends_on": None,
                "Tid": "Env setup",
                "start": 0,
                "end": 0,
                "responsible": "CRITICAL",
                "pred": ["goals"],
            },
        ]
    }
    assert projects == {
        "font": {"fill": "black", "font_family": "Verdana"},
        "vacations": [
            datetime.date(2022, 9, 30),
            datetime.date(2022, 11, 1),
            datetime.date(2022, 11, 11),
        ],
        "resources": {
            "Martin": {
                "price": {"value": 68.75, "unit": "hour"},
                "vacations": [datetime.date(2022, 9, 15)],
            },
            "Samuel": {"price": {"value": 600, "unit": "day"}},
        },
        "projects": {"Test1": None},
        "tasks": {
            "kickoff": {
                "project": "Test1",
                "task": {
                    "name": "kickoff",
                    "start": None,
                    "stop": None,
                    "duration": None,
                    "depends_of": None,
                    "resources": None,
                    "percent_done": 0,
                    "color": None,
                    "fullname": None,
                    "display": True,
                    "state": "",
                },
                "milestone": {
                    "name": "kickoff",
                    "start": None,
                    "depends_of": "brief",
                    "color": None,
                    "fullname": None,
                    "display": True,
                },
                "pertchart": {
                    "name": "kickoff",
                    "duration": None,
                    "lag": 0,
                    "depends_on": None,
                },
                "cpm": {
                    "name": "kickoff",
                    "duration": None,
                    "lag": 0,
                    "depends_of": None,
                },
                "is_milestone": True,
            },
            "brief": {
                "project": "Test1",
                "task": {
                    "name": "brief",
                    "start": datetime.date(2022, 9, 5),
                    "stop": None,
                    "duration": 0.125,
                    "depends_of": [],
                    "resources": [],
                    "percent_done": 0,
                    "color": None,
                    "fullname": None,
                    "display": True,
                    "state": "",
                },
                "milestone": {
                    "name": "brief",
                    "start": None,
                    "depends_of": None,
                    "color": None,
                    "fullname": None,
                    "display": True,
                },
                "pertchart": {
                    "name": "brief",
                    "duration": 0.125,
                    "lag": 0,
                    "depends_on": None,
                    "Tid": "brief",
                    "start": 0,
                    "end": 0,
                    "responsible": "CRITICAL",
                    "pred": [],
                },
                "cpm": {"name": "brief", "duration": 0.125, "lag": 0, "depends_of": []},
                "is_milestone": False,
            },
            "goals": {
                "project": "Test1",
                "task": {
                    "name": "goals",
                    "start": datetime.date(2022, 9, 5),
                    "stop": None,
                    "duration": 0.25,
                    "depends_of": ["brief"],
                    "resources": ["Martin"],
                    "percent_done": 0,
                    "color": None,
                    "fullname": None,
                    "display": True,
                    "state": "",
                },
                "milestone": {
                    "name": "goals",
                    "start": None,
                    "depends_of": None,
                    "color": None,
                    "fullname": None,
                    "display": True,
                },
                "pertchart": {
                    "name": "goals",
                    "duration": 0.25,
                    "lag": 0,
                    "depends_on": None,
                    "Tid": "goals",
                    "start": 0,
                    "end": 0,
                    "responsible": "CRITICAL",
                    "pred": ["brief"],
                },
                "cpm": {
                    "name": "goals",
                    "duration": 0.25,
                    "lag": 0,
                    "depends_of": ["brief"],
                },
                "is_milestone": False,
            },
            "Env setup": {
                "project": "Test1",
                "task": {
                    "name": "Env setup",
                    "start": datetime.date(2022, 9, 6),
                    "stop": None,
                    "duration": 1,
                    "depends_of": ["goals"],
                    "resources": ["Martin"],
                    "percent_done": 0,
                    "color": None,
                    "fullname": None,
                    "display": True,
                    "state": "",
                },
                "milestone": {
                    "name": "Env setup",
                    "start": None,
                    "depends_of": None,
                    "color": None,
                    "fullname": None,
                    "display": True,
                },
                "pertchart": {
                    "name": "Env setup",
                    "duration": 1,
                    "lag": 0,
                    "depends_on": None,
                    "Tid": "Env setup",
                    "start": 0,
                    "end": 0,
                    "responsible": "CRITICAL",
                    "pred": ["goals"],
                },
                "cpm": {
                    "name": "Env setup",
                    "duration": 1,
                    "lag": 0,
                    "depends_of": ["goals"],
                },
                "is_milestone": False,
            },
        },
    }

################################################################################
# PERTDRAWER
################################################################################

def test_pertdrawer_draw_creates_chart_file(flat_project):
    project_def = ProjectReader(flat_project)
    _, pert_def = project_def.build_project()
    pert = PertDrawer(pert_def)
    pert.draw()
    assert pathlib.Path("Test1_pert.pdf").is_file()
    os.unlink("Test1_pert.pdf")
    os.unlink("Test1_pert.gv")

################################################################################
# GANTTDRAWER
################################################################################

def test_gantt_drawer_creates_gantt_svg_output(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    gantt.draw_tasks(project="Test1")
    assert pathlib.Path("Test1.svg").is_file()
    os.unlink("Test1.svg")

def test_gantt_drawer_creates_resource_svg_output(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    gantt.draw_resources(project="Test1")
    assert pathlib.Path("Test1_resources.svg").is_file()
    os.unlink("Test1_resources.svg")

################################################################################
# Resource budgeting feature
################################################################################

def test_resource_has_attribute_price(flat_project):
    # refactoring of the resource schema to change Resource.cost to Resource.price
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)

    assert hasattr(gantt.resources["Martin"], "price")
    assert hasattr(gantt.resources["Samuel"], "price")

def test_gantt_reader_can_define_new_units(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    gantt.define_unit("foo = 1 * hour = ⧘ = wiggly_foo")
    assert "foo" in gantt.registry
    assert "wiggly_foo" in gantt.registry

def test_gantt_reader_can_make_units_alias(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)

    # define abbreviated syntax
    gantt.define_alias("workday = foo2")
    assert "foo2" in gantt.registry
    assert gantt.registry.foo2 == gantt.registry.workday

    # define full syntax
    gantt.define_alias("@alias workday = foo3")
    assert "foo3" in gantt.registry
    assert gantt.registry.foo3 == gantt.registry.workday

def test_project_reader_reads_strips_spaces_from_task_resources():
    # make sure that all resource quantifiers are present as necessary
    project_str = """
Vacations:
    - 2022-09-30
    - 2022-11-01
    - 2022-11-11
Resources:
    Martin:
        price:
            value: 68.75
            unit: hour
        vacations:
            - 2022-09-15
    Samuel:
        price:
            value: 600
            unit:  day
Projects:
    -   Name: Test1
        Tasks:
            kickoff:
                type: milestone
                depends_on: brief
            brief:
                type: task
                start: 2022-09-05
                duration: 0.125 # 1 hour
                percent_done: 0
                resources: 0.5 Martin, 2 Samuel
                depends_on: null
            goals:
                type: task
                start: 2022-09-05
                duration: 0.25
                percent_done: 0
                resources: "Martin "
                depends_on: brief
            Env setup: [2022-09-06, 1, 0, "Martin", "goals"]
"""
    project_def = ProjectReader(project_str)
    project_def, _ = project_def.build_project()

    brief = project_def["tasks"]["brief"]["task"]
    assert brief["resources"] == ["0.5 Martin", "2 Samuel"]

    goals = project_def["tasks"]["goals"]["task"]
    assert goals["resources"] == ["1 Martin"]

def test_gantt_reader_supports_scaled_resources():
    # DONE: gantt.tasks[name].resources must contain a gantt.Resource instance
    # DONE: gantt.data.project[name].tasks[name].resources must contain the scaled string
    project_str = """
Vacations:
    - 2022-09-30
    - 2022-11-01
    - 2022-11-11
Resources:
    Martin:
        price:
            value: 68.75
            unit: hour
        vacations:
            - 2022-09-15
    Samuel:
        price:
            value: 600
            unit:  day
Projects:
    -   Name: Test1
        Tasks:
            kickoff:
                type: milestone
                depends_on: brief
            brief:
                type: task
                start: 2022-09-05
                duration: 0.125 # 1 hour
                percent_done: 0
                resources: 0.5 Martin, 2 Samuel
                depends_on: null
            goals:
                type: task
                start: 2022-09-05
                duration: 0.25
                percent_done: 0
                resources: Martin
                depends_on: brief
            Env setup: [2022-09-06, 1, 0, "Martin", "goals"]
"""
    project = ProjectReader(project_str)
    gantt_def, _ = project.build_project()

    gantt = GanttDrawer(gantt_def)

    # scaled string: digit + resource identifier, eg" "1 Martin", "0.5 Samuel"
    # regex = r"^(\d+\.?\d*)\s+(\w+)$"
    try:
        regex = re.compile(r"^(\d+\.?\d*)\s+(\w+)$")
        assert [
            all(
                [
                    float(regex.match(r).group(1)) and bool(regex.match(r).group(2))
                    for r in t_value["task"]["resources"]
                    if regex.match(r)
                ]
            )
            for t_name, t_value in gantt.data["tasks"].items()
            if not gantt.data["tasks"][t_name]["is_milestone"]
        ]
    except ValueError as exc:
        assert False, f"Could not convert quantifier to number {exc}"
    except KeyError as exc:
        assert False, f"Could not find resource: {exc}"

    assert (
        all(
            [
                all([isinstance(r, Resource) for r in t_value.resources])
                for t_name, t_value in gantt.tasks.items()
                if t_value.__class__.__name__ == "Task"
            ]
        )
        and len(gantt.tasks) > 0
    )  # NOTE: milestone instance isinstance (..., Task) == True so must discriminate by class name

def test_resource_instance_is_monkey_patched_get_unit(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt.resources["Martin"], "get_unit")
    assert hasattr(gantt.resources["Samuel"], "get_unit")
    assert gantt.resources["Martin"].get_unit() == "workhour"
    assert gantt.resources["Samuel"].get_unit() == "workday"

@pytest.mark.skip("later version")
def test_resource_instance_has_category_attribute(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt.resources["Martin"], "category")
    assert hasattr(gantt.resources["Samuel"], "category")
    assert gantt.resources["Martin"].category is None
    assert gantt.resources["Samuel"].category is None

@pytest.mark.skip("later version")
def test_resource_instance_has_subcategory_attribute(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt.resources["Martin"], "subcategory")
    assert hasattr(gantt.resources["Samuel"], "subcategory")
    assert gantt.resources["Martin"].subcategory is None
    assert gantt.resources["Samuel"].subcategory is None

def test_resource_instance_is_monkey_patched_get_price(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt.resources["Martin"], "get_price")
    assert hasattr(gantt.resources["Samuel"], "get_price")
    assert gantt.resources["Martin"].get_price() == 68.75
    assert gantt.resources["Samuel"].get_price() == 600

def test_resource_instance_is_monkey_patched_convert(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt.resources["Martin"], "convert")
    assert hasattr(gantt.resources["Samuel"], "convert")
    assert gantt.resources["Martin"].convert("workday") == 550
    assert gantt.resources["Samuel"].convert("workday") == 600
    assert gantt.resources["Samuel"].convert("workweek") == pytest.approx(3000)

def test_resource_instance_is_monkey_patched_forbid_holidays_for_some_units():
    # if a resource has unit unit/batch then raise valueerror if it defines a holiday
    # if a batch resource does not define a batch_size raise valueerror
    proj1_str = project_str = """
Vacations:
    - 2022-09-30
    - 2022-11-01
    - 2022-11-11
Resources:
    Martin:
        price:
            value: 68.75
            unit: unit
        vacations:
            - 2022-09-15
    Samuel:
        price:
            value: 600
            unit:  workday
Projects:
    -   Name: Test1
        Tasks:
            kickoff:
                type: milestone
                depends_on: brief
            brief:
                type: task
                start: 2022-09-05
                duration: 0.125 # 1 hour
                percent_done: 0
                resources: null
                depends_on: null
            goals:
                type: task
                start: 2022-09-05
                duration: 0.25
                percent_done: 0
                resources: Martin
                depends_on: brief
            Env setup: [2022-09-06, 1, 0, "Martin", "goals"]
"""
    proj1_def = ProjectReader(proj1_str).build_project()[0]
    with pytest.raises(ValueError):
        gantt = GanttDrawer(proj1_def)

    proj2_str = project_str = """
# Font:
#     fill: "#000000"
#     stroke: "black"
#     stroke_width: 0
#     font_family: Verdana
Vacations:
    - 2022-09-30
    - 2022-11-01
    - 2022-11-11
Resources:
    Martin:
        price:
            value: 68.75
            unit: batch
    Samuel:
        price:
            value: 600
            unit:  workday
Projects:
    -   Name: Test1
        Tasks:
            kickoff:
                type: milestone
                depends_on: brief
            brief:
                type: task
                start: 2022-09-05
                duration: 0.125 # 1 hour
                percent_done: 0
                resources: null
                depends_on: null
            goals:
                type: task
                start: 2022-09-05
                duration: 0.25
                percent_done: 0
                resources: Martin
                depends_on: brief
            Env setup: [2022-09-06, 1, 0, "Martin", "goals"]
"""
    proj2_def = ProjectReader(proj2_str).build_project()[0]
    with pytest.raises(ValueError):
        gantt = GanttDrawer(proj2_def)

def test_task_instance_is_monkeypatched_is_using(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt.tasks["goals"], "is_using")
    assert gantt.tasks["goals"].is_using("Martin") == True
    assert gantt.tasks["goals"].is_using("Samuel") == False

def test_task_instance_is_monkeypatched_is_active(flat_project):
    # a task is active on the day when it is running.
    # fractional duration counts for a full day in accounting for activity.
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt.tasks["goals"], "is_active")
    # Notice the date is 2022-09-06 and not 2022-09-05 as defined in the project
    # this is because "goals" task is dependent on "kickoff" task and
    # gantt automatically plans for the depending task 1 day after parent task
    # gantt is not schedule optimization software and the resolution is 1 day
    # we keep these design choices for now.
    # notice the dependency has precedence over the the start/stop date argument
    assert gantt.tasks["goals"].is_active("2022-09-06") == True
    assert gantt.tasks["goals"].is_active("2022-09-07") == False
    assert hasattr(gantt.tasks["Env setup"], "is_active")
    assert gantt.tasks["Env setup"].is_active("2022-09-07") == True
    assert gantt.tasks["Env setup"].is_active("2022-09-08") == False

def test_ganttdrawer_get_unit(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt, "get_unit")
    assert gantt.get_unit("Martin") == "workhour"
    assert gantt.get_unit("Samuel") == "workday"

def test_ganttdrawer_get_price(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt, "get_price")
    assert gantt.get_price("Martin") == 68.75
    assert gantt.get_price("Samuel") == 600

def test_ganttdrawer_get_usage(flat_project):
    # return the quantity that a resource is used in a specified task in a project
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt, "get_usage")
    assert gantt.get_usage( "goals", "Martin") == 1
    assert gantt.get_usage( "goals", "Samuel") == 0

def test_ganttdrawer_is_available(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt, "is_available")

    # wrong date
    with pytest.raises(ValueError):
        gantt.is_available("Martin", "")
    # unavailable date within project range
    assert gantt.is_available("Martin", "2022-09-08") == False
    # available date
    assert gantt.is_available("Martin", "2022-09-05") == True

def test_ganttdrawer_is_using(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt, "is_using")

    # unavailable date within project range
    assert gantt.is_using("goals", "Samuel") == False
    # available date
    assert gantt.is_using("goals", "Martin") == True

def test_ganttdrawer_get_cost(flat_project):
    # gantt.convert(resource) * gantt.get_usage(task, resource) * gantt.is_available(resource, date) * gantt.is_using(resource) * gantt.is_active(task, date)
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt, "get_cost")

    # unavailable date within project range
    assert gantt.get_cost("goals", "Martin", "2022-09-06") == 137.5
    assert gantt.get_cost("goals", "Samuel", "2022-09-06") == 0

def test_ganttdrawer_budget_flat_def(flat_project):
    project_def = ProjectReader(flat_project)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    assert hasattr(gantt, "budget")

    # unavailable date within project range

    check = pd.DataFrame([
        ['Test1', 'goals', 'Martin', '', '', datetime.date(2022, 9, 6), 137.5],
        ['Test1', 'Env setup', 'Martin', '', '', datetime.date(2022, 9, 7), 550.0]
    ], columns = ['project', 'task', 'resource', 'category', 'subcategory', 'date', 'amount'])

    assert gantt.budget().equals(check)

################################################################################
# \BUGFIXES
################################################################################

def test_patch_bug_C50565():
    """BUGFIX: C50565 a project without any task dependency does not produce project outputs"""
    project_str = """
Vacations:
    - 2022-09-30
Resources:
    Martin:
        price:
            value: 68.75
            unit: hour
        vacations:
            - 2022-09-15
    Julie:
        price:
            value: 80
            unit: hour
        vacations:
            - 2022-09-15
Projects:
    -   Name: test_project_1
        Tasks:
            brief:
                type: task
                start: 2022-09-05
                duration: 0.125
                percent_done: 0
                resources: null
                depends_on: null
            test:
                type: task
                start: 2022-09-06
                duration: 0.25
                percent_done: 0
                resources: Martin,Julie
                depends_on: brief
"""

    gantt_def, _ = ProjectReader(project_str).build_project()

    # pert = PertDrawer(pert_def)
    # pert.draw()

    gantt = GanttDrawer(gantt_def)
    gantt.draw_tasks(project="test_project_1")
    assert pathlib.Path("test_project_1.svg").is_file()
    os.unlink("test_project_1.svg")

def test_patch_bug_E17FB6():
    """BUGFIX: E17FB6 wrong csv task definition prevents project creation"""
    project_str = """
Vacations: #general
    - 2022-09-30
Resources:
    Martin:
        price:
            value: 68.75
            unit: hour
        vacations:
            - 2022-09-15
    Julie:
        price:
            value: 80
            unit: hour
        vacations:
            - 2022-09-15
Projects:
    -   Name: test_project_2
        Tasks:
            kickoff:
                type: milestone
                depends_on: brief
            brief:
                type: task
                start: 2022-09-05
                duration: 0.125
                percent_done: 0
                resources: []
                depends_on: []
            # order: ["start", "duration", "percent_done", "resources", "depends_on", "color"]
            Env setup: [2022-09-06, 1, 0, "Martin", "brief"]
"""

    gantt_def, _ = ProjectReader(project_str).build_project()

    # pert = PertDrawer(pert_def)
    # pert.draw()

    gantt = GanttDrawer(gantt_def)
    gantt.draw_tasks(project="test_project_2")
    assert pathlib.Path("test_project_2.svg").is_file()
    os.unlink("test_project_2.svg")

def test_patch_bug_A14E36():
    """
    \BUGFIX: A14E36 pertdrawer returns error when renaming the pert drawings

    sys.stdout shows message: "The file /Users/martinteller/Documents/l1nxit/Documentation/PERT.gv.pdf does not exist."

    - unable to recreate the bug from source code
    - insert breakpoint() inside the source code to attach to the running process launched from markdown-preview-enhanced: unable to reproduce the bug from running subprocess
    - try condisitonal move pathlib.Path(...).is_file() --(true)--> shutil.move(...) UNSUCCESSFUL

    status: PENDING
    """
    project_str = """
Vacations: #general
    - 2022-09-30
Resources:
    Martin:
        price:
            value: 68.75
            unit: hour
        vacations: #for a resource
            - 2022-09-15
    Julie:
        price:
            value: 80
            unit: hour
        vacations: #for a resource
            - 2022-09-15
Projects:
    -   Name: test_project_3
        Tasks:
            kickoff:
                type: milestone
                depends_on: brief
            brief:
                type: task
                start: 2022-09-05
                duration: 0.125 # 1 hour
                percent_done: 0
                resources: null
                depends_on: null
            # order: ["start", "duration", "percent_done", "resources", "depends_on", "color"]
            Env setup: [2022-09-06, 1, 0, "Martin", "brief"]
"""

    _, pert_def = ProjectReader(project_str).build_project()

    pert = PertDrawer(pert_def)
    pert.draw()
    assert pathlib.Path("test_project_3_pert.pdf").is_file()
    os.unlink("test_project_3_pert.gv")
    os.unlink("test_project_3_pert.pdf")

def test_patch_bug_0C501D():
    """
    \BUGFIX: 0C501D pertdrawer returns pert graphviz drawing string to stdout and gets reflected in the hidden output of the project definition

    - try suppressing the output in a contextlib function

    manual test: SUCCESS

    Status: CLOSED
    """
    pass

################################################################################
# CLI
################################################################################

@pytest.mark.skip("Not Implemented")
def test_command_line_interface():
    """Test the CLI."""
    runner = CliRunner()
    result = runner.invoke(cli.main)
    assert result.exit_code == 0
    assert "md_planning.cli.main" in result.output
    help_result = runner.invoke(cli.main, ["--help"])
    assert help_result.exit_code == 0
    assert "--help  Show this message and exit." in help_result.output