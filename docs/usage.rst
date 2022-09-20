=====
Usage
=====

To use md-planning in a project::

    import md_planning

    project_str = """
    # this is a yaml comment
    # i can actually get the yaml contents from an external file
    #
    # Global holidays (for everyone)
    Vacations:
        - 2022-09-30
        - 2022-11-01
        - 2022-11-11
    Resources:
        # a resource named "Martin" with price 50€/hour and one personal
        # holiday on 15th Sept 2022
        Martin:
            price:
                value: 50
                unit: workhour
            vacations:
                - 2022-09-15
        # Another resource named "Samuel" with a price of 600€ per workday
        # A workday is defined globally as 8 hours
        Samuel:
            price:
                value: 600
                unit:  workday
    Projects:
        # the first project in a multiproject definition with name "Test1"
        -   Name: Test1
            # Tasks definitions include tasks and milestones
            # this is a "flat" project definition
            Tasks:
                # a milestone named "kickoff"
                kickoff:
                    type: milestone
                    depends_on: brief
                # a task named "brief"
                brief:
                    type: task
                    start: 2022-09-05
                    duration: 0.125 # 1 hour
                    percent_done: 0
                    resources: null
                    depends_on: null # is root task
                # a task named "goals" with PERT estimation
                goals:
                    type: task
                    start: 2022-09-05
                    percent_done: 0
                    resources: Martin
                    depends_on: brief
                    best: 0.125 # 1 hour
                    optimal: 0.25 # 2 hours
                    worst: 0.5 # 4 hours
                # a quick task definition in list format, the schema is:
                # [start-date, duration [opt], percent_done,
                # resources ["str,..."], depends_on, best [opt],
                # optimal [opt], worst[opt]]
                Env setup: [2022-09-06, 1, 0, "Martin", "goals"]
    """

Critical Path
-------------

You can draw the PERT diagram and extract the critical path with::

    project_def = ProjectReader(project_str)
    _, pert_def = project_def.build_project()
    pert = PertDrawer(pert_def)
    pert.draw()
    # output "project_pert.pdf"

Gantt
-----

You can draw the gantt view with ::

    project_def = ProjectReader(project_str)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    gantt.draw_tasks(project="Test1")
    # outputs "Test1.svg"

You can draw the resource use with::

    project_def = ProjectReader(project_str)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    gantt.draw_resources(project="Test1")
    # output "Test1_resource.svg"

Budgeting
---------

Resource use
^^^^^^^^^^^^

The amount of a resource used in a task can be changed by *scaling* that resource::
    project_str = """
    ...
    Tasks:
        - My Project:
            ...
            Tasks:
                - task1:
                    resources: 2 resource1, 0.5 resource2, resource3
    """

A little like the description of a recipe, with 4 eggs, 2 l of milk... The above syntax enables defining how much or many of a resource is used in the specified task. This is what enables making a budget estimate for a task when combined with the resource price.

Make Your Project Budgeting
^^^^^^^^^^^^^^^^^^^^^^^^^^^

The GanttDrawer class has a `.budget` method that outputs a `pandas.DataFrame` instance that registers the date, resource name, task name, amount spent on a daily basis for the whold duration of the project.

make a budget per task like so::

    project_def = ProjectReader(project_str)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    gantt.draw_tasks(project="Test1")
    budget = gantt.budget()
    budget.drop(["category", "subcategory"], axis=1).groupby("task").agg(sum).to_markdown("my_project_budget.md")

it is possible to view the data by "task", "resource" and "date" by changing the tag in the groupby method.

Units
-----

Units are used to define resource prices::

    resource = """
    ...
    Resources:
        - PersonResource:
            price:
                value: 100
                unit: workday
            vacations:
                - 2022-12-25
        - UnitResource:
            price:
                value: 100
                unit: unit
            # no vacations
        - BatchResource:
            price:
                value: 100
                unit: batch
                batch_size: 100
            # no vacations
    ...
    """

Special Units
^^^^^^^^^^^^^

All units functionalities are supported by the `pint` library.

We introduced some extra time and dimensionless units to help with resource budgeting.

1. Time units:

   - `workhour` = 1 hour
   - `workday` = 8 workhours
   - `workweek` = 5 workdays
   - `workmonth` = 4.33 workweeks
   - `workquarter` = 3 workmonths

Time units are used for material, people and services that cost on a time basis. For instance, a truck rental, rent in general, time based consulting fees, a monthly subscription, ...

For grammatical correctness all time units can be pluralized. (workhour -> workhours, ...)

2. Discrete units:

   - `unit` = used for material resources or services that are used up at the end of the task and that come in simple units, eg: one time consulting fees, one shot service, a perishable resource (cream, ...) ...
   - `batch` = used for materials acquired in packs or multiple units, eg: box of 5000 nails, ... Resources that have unit `batch` must define an extra keyword: `batch_size`. For that matter, "unit" is just a batch with `batch_size` = 1.


Changing Global Unit Values
^^^^^^^^^^^^^^^^^^^^^^^^^^^

You might be in a country where a workday is 7.32 hours or 10 hours so you might want to adjust the global values of the work*** units. To do this you can proceed as follows::

    project_def = ProjectReader(project_str)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    gantt.define_unit("workday = 7.32 * workhours")

To use units in your own language you can do::

    project_def = ProjectReader(project_str)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    gantt.define_alias("workday = journée")

Customizing Units
^^^^^^^^^^^^^^^^^

make your own units::

    project_def = ProjectReader(project_str)
    project_def, _ = project_def.build_project()
    gantt = GanttDrawer(project_def)
    gantt.define_unit("my_custom =  42 * meters")

Common Errors
-------------

Some errors don't show up very well in the stack trace so please make sure you got the following points down:

Missing Task Type
^^^^^^^^^^^^^^^^^

There are two task types: "milestone" and "task"

Currently (v0.1.0) the task type is identified either one of the above strings.
If it is missing, an error will be raised.

An entry in the short list format (without a task type) is de-facto a task.

Missing Spaces In The Mappings
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

in yaml format, `key:value` and `key: value` is not the same thing. If you forget the space, yaml cannot separate the key from value and will likely generate an error.


Task List Format Mix Up
^^^^^^^^^^^^^^^^^^^^^^^

The optional values can just be omitted eg: [2022-09-15, ,...] but the **order** in which the values are put is strict. So percent_done will necessarily come **after** duration.

nb: the order is [start-date, duration [opt], percent_done, resources ["str,..."], depends_on, best [opt], optimal [opt], worst[opt]]