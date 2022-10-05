"""md_planning main module."""
from datetime import date, datetime, timedelta
import pathlib
import re
import shutil
from typing import Any, Tuple, Union, Dict, List
from functools import singledispatch
from copy import deepcopy
import networkx as nx
from gantt import Resource, Task, Project, Milestone
import gantt
from criticalpath import Node
import yaml
from dateutil.parser import parse as parsedate, ParserError
import pertchart
import pint
import pandas as pd
from math import ceil

from contextlib import contextmanager, redirect_stderr, redirect_stdout
from os import devnull

# import debugpy
# debugpy.listen(5678)
# debugpy.wait_for_client()
# debugpy.breakpoint()

##### Work Units #####

# tailored pint unit registry (overridable) for project management
UREG = pint.UnitRegistry()
# unit = ""  #dimensionless unit to define things that come as units
UREG.define("unit = [dimensionless] = _ = u")
# batch = "" #dimensionless unit to define things that come in a group of units
UREG.define("@alias unit = batch = b")

UREG.define("workhour = 1 * hour = _ = wh = workhours")
assert "workhour" in UREG
assert "wh" in UREG

UREG.define(
    "workday = 8 * workhour = _ = wd = workdays"
)  # average number of working hours during the day
assert "workday" in UREG
assert "wd" in UREG

UREG.define(
    "workweek = 5 workday = _ = ww = workweeks"
)  # average number of working days during a week
assert "workweek" in UREG
assert "ww" in UREG

UREG.define(
    "workmonth = 4.33 workweek = _ = wm = workmonths"
)  # average number of working weeks in a month
assert "workmonth" in UREG
assert "wm" in UREG

UREG.define("workquarter = 3 * workmonth = _ = wq = workquarters")
assert "workquarter" in UREG
assert "wq" in UREG

# UREG.define("holiday = 6 * workweek = _ = holidays")
# assert "holiday" in UREG

# UREG.define("workyear = 52 * workweek; offset: -1 * holiday = _  = wy = workyears")
# assert "workyear" in UREG
# assert "wy" in UREG


@contextmanager
def suppress_stdout_stderr():
    """suppress_stdout_stderr is a context manager that redirects stdout and stderr to devnull."""
    with open(devnull, "w") as fnull:
        with redirect_stderr(fnull) as err, redirect_stdout(fnull) as out:
            yield (err, out)


################################################################################
# Patching Resource class
################################################################################
def _resource_get_registry(self) -> pint.UnitRegistry:
    return UREG


Resource.get_registry = _resource_get_registry


def _resource_get_unit(self):
    return self.price["unit"]


Resource.get_unit = _resource_get_unit


def _resource_get_price(self):
    return float(self.price["value"])


Resource.get_price = _resource_get_price


def _resource_convert(
    self, unit: str = "workday", number_of_days: Union[int, float, None] = None
) -> float:
    """
    convert finds the price of a resource as it is used on a daily basis.

    convert brings all resource, whichever unit, to a per day price for the creation of a budget for a project

    :param unit: the granularity of the analysis, defaults to "workday"
    :type unit: str, optional
    :param number_of_days: the total length of the associated task when the price of the resource is independant from time, defaults to None
    :type number_of_days: Union[int, float, None], optional
    :return: the price in the user's currency unit
    :rtype: float
    """
    Q_ = self.get_registry()

    if self.get_unit() == "unit":
        quantity = Q_(f"{self.get_price()} / {number_of_days} / workday")
    elif self.get_unit() == "batch":
        quantity = Q_(
            f"{self.get_price()} / {self.price['batch_size']} / {number_of_days} / workday"
        )
    else:
        quantity = Q_(f" {self.get_price()} / {self.get_unit()}")

    return quantity.to(f"1 / {unit}").m


Resource.convert = _resource_convert


################################################################################
# Patching the Task class
################################################################################


def _is_using(self, resource: str) -> bool:
    return resource in [r.name for r in self.resources]


Task.is_using = _is_using


def _is_active(self, date: Union[str, datetime.date]) -> bool:
    d = date
    if isinstance(d, str):
        try:
            d = parsedate(date).date()
        except ParserError:
            raise ValueError(f"Unrecognised Date: {date}")
    return self.start_date() <= d <= self.end_date()


Task.is_active = _is_active
################################################################################
# Utility functions
################################################################################


def _normalize_resources(task: dict) -> dict:
    res = deepcopy(task)
    if "resources" in res and isinstance(res["resources"], str):
        if "," in res["resources"]:  # type: ignore
            res["resources"] = list(map(lambda s: s.strip(), res["resources"].split(",")))
        else:
            res["resources"] = [res["resources"].strip()]

        regex = re.compile(r"^(\d+\.?\d*)\s+(\w+)$")
        for ind, resource in enumerate(res["resources"]):
            if regex.match(resource) is None:
                res["resources"][ind] = f"1 {resource}"

    if "resources" in res and res["resources"] is None:
        res["resources"] = []

    return res


def _normalize_duration(task: dict) -> dict:
    res = deepcopy(task)
    if res.get("duration") is None:  # then best, optimal and worst are defined
        res["duration"] = round(
            (res["best"] + 4 * res["optimal"] + res["worst"]) / 6, 3
        )
    else:  # no variability in the duration
        res["best"] = res["optimal"] = res["worst"] = res["duration"]
    return res


def _normalize_depends_on(task: dict) -> dict:
    # make sure parent tasks are in the form of List[str]
    res = deepcopy(task)
    if "depends_on" in res:
        if isinstance(res["depends_on"], str):
            if "," in res["depends_on"]:
                res["depends_on"] = list(
                    map(lambda s: s.strip(), res["depends_on"].split(","))
                )
            else:
                res["depends_on"] = [res["depends_on"].strip()]
        elif res["depends_on"] is None:
            res["depends_on"] = []
        else:
            pass
    return res


def _normalize_list_task(task: Union[list, dict]) -> dict:
    if isinstance(task, list):
        keys = {
            "start": None,
            "duration": None,
            "percent_done": 0,
            "resources": [],
            "depends_on": [],
            "color": None,
            "best": None,
            "optimal": None,
            "worst": None,
        }
        res = {"type": "task"}
        for ind, (k, default) in enumerate(keys.items()):
            try:
                res[k] = task[ind]
            except IndexError:
                res[k] = default
        return res
    elif isinstance(task, dict):
        return task
    else:
        raise ValueError(f"Unknown task definition {task}")


@singledispatch
def normalize_task(task: Any):
    """
    normalize_task changes a list defined task to a dict defined task.

    :param task: task defined as a list
    :type task: list
    :raises NotImplementedError: if the task type is not a recognised format
    """
    raise NotImplementedError


@normalize_task.register(dict)
def _(task: dict):
    return task


@normalize_task.register(list)
def _(task: list):
    keys = {
        "start": None,
        "duration": None,
        "percent_done": 0,
        "resources": [],
        "depends_on": [],
        "color": None,
        "best": None,
        "optimal": None,
        "worst": None,
        "is_milestone": False,
    }
    res = {}
    for ind, (k, default) in enumerate(keys.items()):
        try:
            res[k] = task[ind]
        except IndexError:
            res[k] = default
    return res


@singledispatch
def get_duration(task: Any):
    """
    get_duration makes the duration of a task primarily from the estimated task durations and if not available, the actual duration data.

    :param task: the task definition
    :type task: Union[dict, list]
    :raises NotImplementedType: types other than dict and list will raise error
    """
    raise NotImplementedError


@get_duration.register(dict)
def _(task: dict):
    if all(
        [
            task.get("best") is not None,
            task.get("optimal") is not None,
            task.get("worst") is not None,
        ]
    ):  # \BUGFIX 406D86
        return round((task["best"] + 4 * task["optimal"] + task["worst"]) / 6, 3)
    else:
        try:
            return round(task["duration"], 3)
        except KeyError:
            raise ValueError(
                "Task must define either ('best', 'optimal', 'worst') or 'duration'."
            )


@get_duration.register(list)
def _(task: list):
    # {
    #     "start": None,
    #     "duration": None,
    #     "percent_done": 0,
    #     "resources": [],
    #     "depends_on": [],
    #     "color": None,
    #     "best": None,
    #     "optimal": None,
    #     "worst": None,
    # }
    if len(task) == 9:
        return round((task[6] + 4 * task[7] + task[8]) / 6, 3)
    else:
        return round(task[1], 3)


@singledispatch
def _get_resources(res: Any):
    """
    _get_resources helper function that returns resources in a project compatible format.

    :param res: resource
    :type res: Union[str, list, None]
    :raises NotImplementedError: if the data is not in a recognised format
    :return: the list of resources used by the task
    :rtype: List[str]
    """
    if res is None:
        return []
    raise NotImplementedError


@_get_resources.register(str)
def _(res: str):
    if "," in res:
        return [r.strip() for r in res.split(",")]
    else:
        return [res.strip()]


@_get_resources.register(list)
def _(res: list):
    return res


@singledispatch
def get_resources(task: Any):
    """
    get_resources is a helper function that returns the resources used in a task in a project compatible format.

    Works on dict defined tasks and list defined tasks.

    :param task: the task description
    :type task: Union[dict, list]
    :raises NotImplementedError: if the task format is not recognised.
    :return: list of resource names
    :rtype: List[str]
    """
    raise NotImplementedError


@get_resources.register(dict)
def _(task: dict):
    return _get_resources(task["resources"])


@get_resources.register(list)
def _(task: list):
    return _get_resources(task[3])


@singledispatch
def _get_dependencies(deps: Any):
    if deps is None:
        return []
    raise NotImplementedError


@_get_dependencies.register(str)
def _(deps: str):
    if "," in deps:
        return list(map(lambda s: s.strip(), deps.split(",")))
    else:
        return [deps]


@_get_dependencies.register(list)
def _(deps: list):
    return deps


@singledispatch
def get_dependencies(task: Any):
    """
    get_dependencies get the dependencies from a task definition.

    Works on dict and list defined tasks

    :param task: the task definition
    :type task: Union[dict, list]
    :raises NotImplementedError: if the task definition is not recognised
    """
    raise NotImplementedError


@get_dependencies.register(dict)
def _(task: dict):
    return _get_dependencies(task["depends_on"])


@get_dependencies.register(list)
def _(task: list):
    return _get_dependencies(task[4])


def rename(
    dict_in: dict,
    key_from: str,
    key_to: str,
    flexible: bool = False,
    flex_val: Any = None,
) -> dict:
    """
    Forgiving function to rename keys in a dictionary.

    :dict_in:: the input dictionary
    :key_from:: the key to change
    :key_to:: the key to rename to
    :flexible:: raise error if key_from does not exist dict_in else assign None to key_to
    """
    if not flexible and key_from not in dict_in:
        raise KeyError(f"{key_from} not in input dictionary")
    data = deepcopy(dict_in)
    data[key_to] = data.get(key_from, flex_val)
    if key_from in data:
        del data[key_from]
    return data


@singledispatch
def get_task_type(item: Any) -> Union[str, None]:
    """
    get_task_type returns the name of the task type: milestone or task.

    :param item: item to be examined
    :type item: Any
    :raises NotImplementedError: if the item is different from a dict or list
    :return: the item tag type
    :rtype: str
    """
    return None


@get_task_type.register(dict)
def _(item: Dict):
    # flat list of tasks
    res = item.get("type")
    if res in ["task", "milestone"]:
        return res
    if "percent_done" in item:
        return "task"
    # nested list of milestones and tasks
    return "milestone"


@get_task_type.register(list)
def _(item: List):
    return "task"


def is_nested(tasks: dict) -> bool:
    """
    is_nested recognizes the project format to determine if the tasks definition is in the flat or the nested format.

    if any task is a milestone and contains another task then is_nested==True

    :param tasks: full project task definition
    :type tasks: dict
    :return: is it a nested definition T/F
    :rtype: bool

    :BUGFIX: E17FB6 and  39651C
    """
    for task in tasks.values():
        if get_task_type(task) == "task":
            continue
        else:  # is milestone
            for value in task.values():
                if get_task_type(value) in ["task", "milestone"]:
                    return True
    return False


def _walk(path, child):
    if isinstance(child, dict):
        if get_task_type(child) == "task":
            child["is_milestone"] = False
            yield [tuple(path), child]
        else:
            for key, value in child.items():
                if get_task_type(value) == "milestone":
                    yield [tuple(path + [key]), {"is_milestone": True}]
                yield from _walk(path + [key], value)
    else:
        yield [tuple(path), child]


def walk_project_tasks(tasks: dict):
    """
    walk_project returns normalized tasks in a nested or flat project configuration

    :param tasks: project tasks
    :type tasks: dict
    :return: list of task_name, task_definition
    :rtype: List[Tuple(str, dict)]
    """
    if is_nested(tasks):
        res = [(pth, normalize_task(tsk)) for (pth, tsk) in list(_walk([], tasks))]

        milestones = list(
            sorted(
                filter(
                    lambda i: not isinstance(i[1], list) and i[1]["is_milestone"], res
                ),
                key=lambda m: len(m[0]),
                reverse=True,
            )
        )
        # milestone_ids = [i[0][-1] for i in milestones]

        _tasks = list(
            sorted(
                filter(
                    lambda i: isinstance(i[1], list) or not i[1]["is_milestone"], res
                ),
                key=lambda m: len(m[0]),
                reverse=True,
            )
        )

        # replace all milestones depends_on that depend on a milestone or a group of tasks
        for milestone in milestones:
            milestone_path_len = len(milestone[0])
            # project = Node(milestone[0][-1])
            subtasks = list(
                filter(
                    lambda task: len(task[0]) == milestone_path_len + 1
                    and task[0][-2] == milestone[0][-1],
                    res,
                )
            )

            # for subtask in subtasks:  # 1 level below milestone and subtask of milestone
            #     try:
            #         if subtask[1]["is_milestone"]:
            #             dep_names = get_dependencies(subtask[1])
            #             for dep in dep_names:
            #                 _t = list(filter(lambda t: t[0][-1]==dep, _tasks))[0]
            #                 project.add(
            #                     Node(dep, duration=get_duration(subtask[1]), lag=0)
            #                 )
            #         else:
            #             project.add(
            #                 Node(
            #                     subtask[0][-1],
            #                     duration=get_duration(subtask[1]),
            #                     lag=0,
            #                 )
            #             )
            #     except Exception as err:
            #         raise ValueError(f"Definition error at {subtask[0][-1]}") from err

            # add dependencies
            # for subtask in subtasks:
            #     if (deps:=get_dependencies(subtask[1])):
            #         updated_deps = []

            #         for dep in deps: # not dependency but parent really...
            #             # update milestone dependency to last node in critical path
            #             if dep in milestone_ids:
            #                 updated_deps.append(get_dependencies(list(filter(lambda m: m[0][-1] == dep, milestones))[0][1])[0]) # there is only one last task on critical path
            #             else:
            #                 updated_deps.append(dep)

            #         # filter updated_deps to tasks strictly within descendants of the current milestone
            #         # subtasks_names = [s[0][-1] for s in subtasks]
            #         # updated_deps = [d for d in updated_deps if d in subtasks_names]

            #         # build project links
            #         for _d in updated_deps:
            #             try:
            #                 project.link(_d, subtask[0][-1])
            #             except Exception as err:
            #                 # raise ValueError(f"Cannot link {subtask[0][-1]} and {_d}") from err
            #                 node = Node(
            #                     _d,
            #                     duration=0,
            #                     lag=0,
            #                 )
            #                 project.add(node)
            #                 project.link(_d, subtask[0][-1])

            # project.update_all()
            # critical_path = list(map(lambda i: i.name, project.get_critical_path()))
            # milestone[1]["depends_on"] = [critical_path[0], critical_path[-1]]
            milestone[1]["depends_on"] = [subtask[0][-1] for subtask in subtasks]
            # milestone[1]["duration"] = project.duration
            milestone[1]["duration"] = 0
            # milestone[1]["first_node"] = critical_path[0]
            # milestone[1]["last_node"] = critical_path[-1]

        # # replace all tasks that depend on a milestone to its last node
        # for task in _tasks:
        #     try:
        #         dependencies = get_dependencies(task[1])
        #         # make a temporary result list
        #         dependency_results = []
        #         # for each item in dependencies
        #         for dependency in dependencies:
        #             #if item is a milestone and milestone in task['depends_on']
        #             if dependency in milestone_ids:
        #                 # get the milestone dependency
        #                 _milestone = list(filter(lambda m: m[0][-1]==dependency, milestones))[0]
        #                 # extend temp result list with this milestone's dependencies
        #                 dependency_results.extend(get_dependencies(_milestone[1]))
        #             # else:
        #             else:
        #                 dependency_results.append(dependency)
        #                 #extend the temp result list with the current dependency
        #         task[1]["depends_on"] = dependency_results
        #         # task[1]["depends_on"] = [ get_dependencies(list(filter(lambda _milst: _milst[0][-1]==m,milestones))[0][1]) if m==d else d for d in dependencies for m in milestone_ids]
        #     except Exception as err:
        #         raise ValueError(f"Dependency error at {task[0][-1]}")

        return [(task[0][-1], task[1]) for task in res]
    else:
        return list(tasks.items())


################################################################################
# Project reader class
################################################################################
class ProjectReader:
    """
    Utility for reading raw project data.

    Reads yaml data and returns a representation of the projects
    suitable for a PERT and gantt analysis.
    """

    def __init__(self, projstr: str, critical_color: Union[str, None] = None):
        """
        Read and setup project data.

        :projstr:: string representation of the project in yaml syntax
        :critical_color:: string/name/hex representation of the color for the tasks on the critical path
        """

        self.projstr = projstr
        self.data = yaml.safe_load(projstr)
        self.font = self.data.get("Font", {})
        self.vacations = self.data.get("Vacations", [])
        self.resources = self.data.get("Resources", {})
        self.projects = {}
        self.tasks = {}
        self.pertcharts = {}

        for project in self.data.get("Projects", []):  # type: ignore
            proj_name = project.get("Name")
            if not proj_name:
                raise ValueError("Missing project name")
            self.projects[proj_name] = None
            tasks: dict = project.get("Tasks")

            for name, task in walk_project_tasks(tasks):

                ##### SETUP #####

                payload = {
                    "project": proj_name,
                    "task": {
                        "name": name,
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
                        "name": name,
                        "start": None,
                        "depends_of": None,
                        "color": None,
                        "fullname": None,
                        "display": True,
                    },
                    "pertchart": {},
                    "cpm": {
                        "name": name,
                        "duration": None,
                        "lag": 0,
                        "depends_of": None,
                    },
                    "is_milestone": False,
                }

                ##### TRANSFORM #####

                task = _normalize_list_task(task)

                if (
                    task.get("is_milestone", False)
                    or task.get("type", "task") == "task"
                ):
                    try:
                        task = _normalize_duration(task)
                    except (TypeError, KeyError) as err:
                        raise ValueError(
                            f"Definition error for duration or estimates in task named {name}"
                        ) from err
                else:
                    task["duration"] = 0

                task = _normalize_depends_on(task)

                task = _normalize_resources(task)

                ##### UPDATE #####

                ##### CPM #####
                payload["cpm"]["name"] = name
                payload["cpm"]["duration"] = task["duration"]
                payload["cpm"]["lag"] = 0
                payload["cpm"]["depends_of"] = task.get("depends_on", None)

                ##### PERTCHART #####
                payload["pertchart"]["Tid"] = name
                payload["pertchart"]["start"] = 0
                payload["pertchart"]["duration"] = task["duration"]
                payload["pertchart"]["end"] = 0
                payload["pertchart"]["responsible"] = ""
                payload["pertchart"]["pred"] = task.get("depends_on", ["START"])
                if not payload["pertchart"]["pred"]:
                    payload["pertchart"]["pred"] = ["START"]

                ##### TASK #####
                for k in payload["task"]:
                    if k != "depends_on":
                        payload["task"][k] = task.get(k, payload["task"][k])
                payload["task"]["depends_of"] = task.get("depends_on", None)

                ##### MILESTONE #####
                if (
                    task.get("is_milestone", False)
                    or task.get("type", "task") == "milestone"
                ):
                    payload["is_milestone"] = True

                    for k in payload["milestone"]:
                        if k != "depends_on":
                            payload["milestone"][k] = task.get(
                                k, payload["milestone"][k]
                            )
                    payload["milestone"]["depends_of"] = task.get("depends_on", [])

                self.tasks[name] = payload

            ##### State: Ready for post-processing #####

            # CPM for PertChart
            critical_path = self._get_critical_path(
                {
                    k: t["cpm"]
                    for (k, t) in self.tasks.items()
                    if t["project"] == proj_name
                }
            )

            for task_name in critical_path:
                self.tasks[task_name]["pertchart"]["responsible"] = "CRITICAL"
                if self.tasks[task_name]["task"]["color"] is None:
                    self.tasks[task_name]["task"]["color"] = critical_color

    def _get_critical_path(self, cpm_data: dict) -> tuple:
        """
        _get_critical_path returns tuple of task (node) names on the critical path.

        :param cpm_data: cpm data as provided by the initialization
        :type cpm_data: dict
        :return: tuple of task names
        :rtype: tuple
        """
        proj = Node("project")
        tmp = {}
        for k, values in cpm_data.items():  # add nodes
            # cpm_data[k]["node"] = Node(
            tmp.setdefault(k, {})["node"] = Node(
                values["name"], duration=values["duration"], lag=values["lag"]
            )
            proj.add(tmp[k]["node"])

        for k, values in cpm_data.items():  # add links
            for link in values["depends_of"]:
                # if k and link and tmp:
                proj.link(tmp[link]["node"], tmp[k]["node"])

        proj.update_all()

        return tuple(map(str, proj.get_critical_path()))  # type: ignore

    def build_project(self) -> tuple:
        """
        build_project returns a tuple with  gantt project data and pertchart data.

        :return: pos 0 gantt data, pos 1 pert chart data
        :rtype: tuple
        """
        project_data = {
            "font": self.font,
            "vacations": self.vacations,
            "resources": self.resources,
            "projects": self.projects,
            "tasks": self.tasks,
        }

        pertchart_data = {
            k: {
                t["pertchart"]["Tid"]: t["pertchart"]
                for t in self.tasks.values()
                if t["project"] == k
            }
            for k in self.projects
        }

        return (project_data, pertchart_data)


################################################################################
# Pert drawer class
################################################################################
class PertDrawer:
    """
    PertParser takes a python dictionary in and extracts the pert data.

    from it in order to assess project CPM.

    It also cleans project data of PERT estimates in order to provide
    the proper durations for a gantt representation.
    """

    def __init__(self, tasks: dict):
        """
        Class initialization.

        :param tasks: pert compatible tasks definitions
        :type tasks: dict
        """
        self.tasks: dict = tasks

    def draw(
        self, project: Union[str, None] = None, out: Union[str, None] = None
    ) -> None:
        """
        draw Draws the network of tasks in self.tasks.

        :param project: name of the project otherwise all projects tasks will be analysed together, defaults to None
        :type project: Union[str, None], optional
        :param out: prefix name of the files to output, will default to the name of the project to output "project_pert.pdf" and "project_pert.gv" (graphviz file)
        :type out: Union[str, None], optional
        """
        if project is None:
            _projects = [k for k in self.tasks]
        else:
            # XXX: this is not of the same type as the definition above...
            _projects = [project]

        pert = pertchart.PertChart()

        for proj in _projects:
            calculated = pert.calculate_values(self.tasks[proj])

            # see bugfix 0C501D
            with suppress_stdout_stderr():
                pert.create_pert_chart(calculated)

            # see bugfix A14E36
            if pathlib.Path("PERT.gv.pdf").is_file():
                shutil.move(
                    "PERT.gv.pdf", f"{out}_pert.pdf" if out else f"{proj}_pert.pdf"
                )
            if pathlib.Path("PERT.gv").is_file():
                shutil.move("PERT.gv", f"{out}_pert.gv" if out else f"{proj}_pert.gv")

    # XXX: (refactor) not evidently useful usecase
    def get_critical_path(self, project: str):
        """
        get_critical_path returns the critical path of tasks in a specific project.

        :param project: name of the project
        :type project: str
        :raises NotImplementedError: _description_
        """
        raise NotImplementedError


################################################################################
# Gantt drawer class
################################################################################
class GanttDrawer:
    """
    Gantt project representation from a yaml file definition.

    see tests for project definition structure and class usage

    """

    def __init__(self, data):
        """
        Class initialization.

        :param data: definition of the project as output by ProjectReader class
        :type data: dict
        """
        self.registry = UREG
        self.data = data
        self.projects: Dict[str, Project] = {}
        self.resources: Dict[str, Resource] = {}
        self.vacations = []
        self.tasks: Dict[str, Task] = {}
        # self._register_font_attribute() #svgwrite issue
        self._register_projects()
        self._register_resources()
        self._register_vacations()
        self._register_tasks()

    def _register_font_attribute(self):
        """_register_font_attributes changes the default presentation settings."""
        # BUG: for whatever reason, the gantt API does not seem to work there...
        gantt.define_font_attributes(self.data["font"])

    def _register_projects(self) -> None:
        """_register_projects adds all projects and monkey patches class api."""
        self.projects = {k: Project(k) for k in self.data["projects"]}

    def _register_resources(self) -> None:
        """_register_resources adds and monkey patches class api."""
        self.resources = {}

        for resource in self.data["resources"]:
            try:
                res = Resource(resource)
                res.price = self.data["resources"][resource].get(
                    "price", {"value": 0, "unit": "unit"}
                )

                if res.price["unit"] == "batch":
                    if "batch_size" not in res.price:
                        raise ValueError(
                            f"Error in Resource {res.name}: batch resource definition missing key 'batch_size'"
                        )
                if (
                    vacations := self.data["resources"][resource].get("vacations")
                ) is not None:
                    res.add_vacations(*vacations)

                if res.price["unit"] in ["unit", "batch"] and res.vacations:
                    raise ValueError(
                        f"Resource:{res.name} cannot have unit/batch unit type and holidays at the same time"
                    )
            except Exception as err:
                raise ValueError(f"Definition error in {resource}") from err

            self.resources[resource] = res

    def _register_vacations(self) -> None:
        """_register_vacations adds vacations at a multiproject level."""
        if (vacations := self.data.get("vacations")) is not None:
            for _v in vacations:
                gantt.add_vacations(_v)

    def _register_tasks(self) -> None:
        """
        _register_tasks creates the network of tasks to register for the projects.

        get_tasks starts with the root task then iterates over all the left
        over tasks in search of the dependant tasks. Task names must be
        unique so it is safe to refer to them verbatim.
        """
        tasks = [
            {
                "project": t["project"],
                "task_name": t["is_milestone"]
                and t["milestone"]["name"]
                or t["task"]["name"],
                "task": t["milestone"] if t["is_milestone"] else t["task"],
                "is_milestone": t["is_milestone"],
                "depends_of": t["is_milestone"]
                and t["milestone"]["depends_of"]
                or t["task"]["depends_of"],
            }
            for t in self.data["tasks"].values()
        ]

        for proj_name, project in self.projects.items():
            task_registry = {}
            filtered_tasks = list(filter(lambda t: t["project"] == proj_name, tasks))
            linked_tasks = [
                (pred, task["task_name"])
                for task in filtered_tasks
                for pred in task["depends_of"]
            ]

            DG = nx.DiGraph(linked_tasks)

            for _t_name in nx.topological_sort(DG):
                to_register = list(
                    filter(lambda t: t["task_name"] == _t_name, filtered_tasks)
                )[0]
                dependents = [task_registry[name] for name in to_register["depends_of"]]
                resources = [
                    self.resources[res_check]
                    for res in to_register["task"].get("resources", [])
                    for res_check in self.resources
                    if res_check in res
                ]
                if to_register["is_milestone"]:
                    task_registry[_t_name] = Milestone(
                        **{**to_register["task"], "depends_of": dependents}
                    )
                else:
                    task_registry[_t_name] = Task(
                        **{
                            **to_register["task"],
                            "depends_of": dependents,
                            "resources": resources,
                        }
                    )
                project.add_task(task_registry[_t_name])

            self.tasks.update(**task_registry)

    def draw_tasks(
        self,
        project: str,
        filename: Union[str, None] = None,
        today: Union[datetime.date, str, None] = None,  # type: ignore
        start: Union[datetime.date, str, None] = None,  # type: ignore
        end: Union[datetime.date, str, None] = None,  # type: ignore
        scale: Union[str, None] = None,  # type: ignore
    ) -> None:
        """
        draw_tasks creates a svg visualization of the task execution in the project.

        :param project: project name
        :type project: str
        :param filename: file name override. If None, use the project name, defaults to None
        :type filename: Union[str, None], optional
        :param today: today's date for task burn down evaluation, defaults to None
        :type today: Union[datetime.date, str, None], optional
        """
        if filename is None:
            filename = f"{project}.svg"
        if today == "today":
            today = datetime.today().date()
        if isinstance(today, str):
            today = parsedate(today).date()
        if isinstance(start, str):
            start = parsedate(start).date()
        if isinstance(end, str):
            end = parsedate(end).date()

        scales = {
            "d": gantt.DRAW_WITH_DAILY_SCALE,
            "daily": gantt.DRAW_WITH_DAILY_SCALE,
            "w": gantt.DRAW_WITH_WEEKLY_SCALE,
            "weekly": gantt.DRAW_WITH_WEEKLY_SCALE,
            "m": gantt.DRAW_WITH_MONTHLY_SCALE,
            "monthly": gantt.DRAW_WITH_MONTHLY_SCALE,
            "q": gantt.DRAW_WITH_QUATERLY_SCALE,
            "quarterly": gantt.DRAW_WITH_QUATERLY_SCALE,
        }
        if scale is None:
            scale = "d"
        scale: str = scales[scale]

        self.projects[project].make_svg_for_tasks(
            filename=filename, today=today, start=start, end=end, scale=scale
        )

    def draw_resources(
        self,
        project: str,
        filename: Union[str, None] = None,
        today: Union[datetime.date, str, None] = None,  # type: ignore
        start: Union[datetime.date, str, None] = None,  # type: ignore
        end: Union[datetime.date, str, None] = None,  # type: ignore
        resources: Union[List[str], None] = None,  # type: ignore
        one_line_for_tasks: bool = False,
        scale: Union[str, None] = None,  # type: ignore
    ) -> None:
        """
        draw_resources creates a svg visualization of the resource use in the project.

        :param project: name of the project
        :type project: str
        :param filename: file name override. If None use the project name, defaults to None
        :type filename: Union[str, None], optional
        :param today: today's date for resource use WIP evaluation, defaults to None
        :type today: Union[datetime.date, str, None], optional
        :param scale: python_gantt scale enumeration see doc, defaults to None
        :type scale: Union[str, None], optional
        """
        if filename is None:
            filename = f"{project}_resources.svg"
        if today == "today":
            today = datetime.today().date()
        if isinstance(today, str):
            today = parsedate(today).date()
        if isinstance(start, str):
            start = parsedate(start).date()
        if isinstance(end, str):
            end = parsedate(end).date()
        if resources:
            resources: Resource = [self.resources[res] for res in resources]  # type: ignore
        scales = {
            "d": gantt.DRAW_WITH_DAILY_SCALE,
            "daily": gantt.DRAW_WITH_DAILY_SCALE,
            "w": gantt.DRAW_WITH_WEEKLY_SCALE,
            "weekly": gantt.DRAW_WITH_WEEKLY_SCALE,
            "m": gantt.DRAW_WITH_MONTHLY_SCALE,
            "monthly": gantt.DRAW_WITH_MONTHLY_SCALE,
            "q": gantt.DRAW_WITH_QUATERLY_SCALE,
            "quarterly": gantt.DRAW_WITH_QUATERLY_SCALE,
        }
        if scale is None:
            scale = "d"
        scale: str = scales[scale]

        self.projects[project].make_svg_for_resources(
            filename=filename,
            today=today,
            start=start,
            end=end,
            resources=resources,
            one_line_for_tasks=one_line_for_tasks,
            scale=scale,
        )

    def define_unit(self, unit: str) -> None:
        """
        define_unit registers a new pint unit in the instance unit registry.

        :param unit: unit definition (see pint documentation for syntax)
        :type unit: str
        """
        self.registry.define(unit)

    def define_alias(self, alias: str) -> None:
        """
        define_alias makes a new alias for an existing unit.

        useful when using a unit in a multilingual and pluralized context

        :param alias: alias definition, can start with "@alias" (full definition) or not (abbreviated syntax) (see pint documentation for more details)
        :type alias: str
        """
        if alias.strip().startswith("@alias"):
            self.registry.define(alias)
        else:
            self.registry.define(f"@alias {alias}")

    def get_unit(self, resource: str) -> str:
        """
        get_unit helper function for a project object to get a resource's units

        :param project: name of the project
        :type project: str
        :param resource: name of the resource
        :type resource: str
        """
        try:
            return self.resources[resource].get_unit()
        except KeyError:
            raise ValueError(f"Unknown resource {resource}")

    def get_price(self, resource: str) -> float:
        """
        get_price returns the price of the specified resource

        :param resource: name of the resource
        :type resource: str
        :return: the price of the resource
        :rtype: float
        """
        try:
            return self.resources[resource].get_price()
        except KeyError:
            raise ValueError(f"Unknown resource {resource}")

    def get_usage(self, task: str, resource: str) -> float:
        """
        get_usage returns the amount of a specified resource that a task uses.

        :param task: task name
        :type task: str
        :param resource: resource name
        :type resource: str
        :raises ValueError: if the task name is not defined
        :raises ValueError: if the resource name is not defined
        :return: the amount used of specified resource by a task
        :rtype: float
        """
        try:
            resources = self.data["tasks"][task]["task"]["resources"]
        except KeyError:
            raise ValueError(f"Unknown task {task}")

        if resource not in self.resources:
            raise ValueError(f"Unknown resource {resource}")

        for res in resources:
            if res.endswith(resource):
                return float(res.split()[0])

        return 0.0

    def get_bounds(self) -> Tuple[date, date]:
        """
        get_bounds returns the start date and the end date of the whole file definition, all projects taken into consideration.

        :return: start_date, end_date
        :rtype: Tuple[date, date]
        """
        start = None
        stop = None
        for proj in self.projects.values():
            if start is None or start > proj.start_date():
                start = proj.start_date()
            if stop is None or stop < proj.end_date():
                stop = proj.end_date()
        return start, stop

    def is_available(self, resource: str, date: Union[str, datetime.date]) -> bool:
        """
        is_available returns True if a specific resource is available to use on a specified date.

        :param resource: resource name
        :type resource: str
        :param date: date at which availability is assessed
        :type date: Union[str, datetime.date]
        :raises ValueError: _description_
        :return: True/False
        :rtype: bool
        """
        start, stop = self.get_bounds()

        try:
            res = self.resources[resource]
        except KeyError:
            raise ValueError(f"Resource named {resource} not defined")

        d = date
        if isinstance(d, str):
            try:
                d = parsedate(date).date()
            except ParserError:
                raise ValueError(f"Unrecognised Date: {date}")

        if start <= d <= stop:
            return res.is_available(d)

        return False

    def is_using(self, task: str, resource: str) -> bool:
        """
        is_using is a utility function at the project level to determine if the given task is using a specific resource.

        :param task: task name
        :type task: str
        :param resource: resource name
        :type resource: str
        :return: is task ABC using resource XYZ, True/False
        :rtype: bool
        """
        return self.tasks[task].is_using(resource)

    def convert(
        self, resource: str, number_of_days: Union[int, float, None] = None
    ) -> float:
        """
        convert is a utility function at the project level that gets the daily price of a resource with units.

        :param resource: resource name
        :type resource: str
        :param number_of_days: length of the associated task for resources that are time independant, defaults to None
        :type number_of_days: Union[int, float, None], optional
        :return: a price in the user's currency unit
        :rtype: float
        """
        return self.resources[resource].convert(number_of_days=number_of_days)

    def is_active(self, task: str, date: Union[str, datetime.date]) -> bool:
        """
        is_active is a utility function at the project level that gets the activity status of a task in a project at a given date.

        :param task: task name
        :type task: str
        :param date: the date when the activity is considered
        :type date: Union[str, datetime.date]
        :raises ValueError: if the date is not recognised by dateutil.parse
        :return: the task is active: True/False
        :rtype: bool
        """
        d = date
        if isinstance(d, str):
            try:
                d = parsedate(date).date()
            except ParserError:
                raise ValueError(f"Unrecognised Date: {date}")

        return self.tasks[task].is_active(d)

    def duration(self, task: str) -> float:
        """
        duration is a utility function at the project level to retrieve a task duration.

        :param task: task name
        :type task: str
        :return: task duration
        :rtype: float
        """
        return self.tasks[task].duration

    def get_cost(
        self, task: str, resource: str, date: Union[str, datetime.date]
    ) -> float:
        """
        get_cost returns the actual cost of a specific resource in a given task, on a given day.

        :param task: task name
        :type task: str
        :param resource: resource name
        :type resource: str
        :param date: date of consideration
        :type date: Union[str, datetime.date]
        :raises ValueError: if the date format is not recognised by dateutil.parse
        :return: the cost in the user's currency
        :rtype: float
        """
        d = date
        if isinstance(d, str):
            try:
                d = parsedate(date).date()
            except ParserError:
                raise ValueError(f"Unrecognised Date: {date}")

        task_length = (mytask := self.tasks[task]).duration or float(
            mytask.end_date() - mytask.start_date()
        )  # type: ignore

        task_days, task_decimals = (task_length // 1, task_length % 1)

        duration_left = (mytask.start_date() + timedelta(days=task_days)) - d

        if duration_left.days > task_days:  # task not active
            return 0

        time_scaling = 1 if duration_left.days != 0 else task_decimals

        return (
            self.convert(resource, number_of_days=ceil(task_length))
            * time_scaling
            * self.get_usage(task, resource)
            * self.is_available(resource, d)
            * self.is_using(task, resource)
            * self.is_active(task, d)
        )

    def budget(self) -> pd.DataFrame:
        """
        budget records all the planned expenses

        budget records for each day, each task and each resource, the use and associated cost in the project planning.

        :return: pandas.DataFrame with columns ["project", "task", "resource", "category", "subcategory", "date", "amount"]
        :rtype: pd.DataFrame
        """
        columns = [
            "project",
            "task",
            "resource",
            "category",
            "subcategory",
            "date",
            "amount",
        ]
        result = []
        start, stop = self.get_bounds()
        days = (stop - start).days + 1  # the end date is included in the bounds
        for proj_name, project in self.projects.items():
            for task in project.tasks:
                if hasattr(task, "resources"):
                    for resource in task.resources:
                        for ind in range(days):
                            now = start + timedelta(days=ind)
                            if (
                                amount := self.get_cost(task.name, resource.name, now)
                            ) != 0:
                                result.append(
                                    [
                                        proj_name,
                                        task.name,
                                        resource.name,
                                        "",
                                        "",
                                        now,
                                        amount,
                                    ]
                                )
        return pd.DataFrame(result, columns=columns)
