===========
md-planning
===========


.. image:: https://img.shields.io/pypi/v/md_planning.svg
        :target: https://pypi.python.org/pypi/md_planning

.. image:: https://img.shields.io/travis/mtllr/md_planning.svg
        :target: https://travis-ci.com/mtllr/md_planning

.. image:: https://readthedocs.org/projects/md-planning/badge/?version=latest
        :target: https://md-planning.readthedocs.io/en/latest/?version=latest
        :alt: Documentation Status


package to define, visualize with gantt and budget projects using yaml syntax.

The tasks in the projects can contain *uncertainties* in which case the pert beta estimate is used to define the expected duration of the task.

A user should be able to integrate with extensions like markdown-preview-enhanced for automated report creation.

sources:

- https://pypi.org/project/python-gantt-csv/
- https://pypi.org/project/python-gantt/
- https://github.com/nofaralfasi/PERT-CPM-graph
- https://github.com/andrewdieken/pert_estimator

* Free software: MIT license
* Documentation: https://md-planning.readthedocs.io.


Features
--------

* define a project with yaml syntax
* draw project task PERT diagram
* get project task critical path
* draw project resource usage diagram
* draw project gantt diagram on daily, weekly, monthly and quarterly basis
* make a budget estimate from tasks' resource use
* support for nested tasks (nested milestones/yaml syntax)

Credits
-------

This package was created with Cookiecutter_ and the `audreyr/cookiecutter-pypackage`_ project template.

.. _Cookiecutter: https://github.com/audreyr/cookiecutter
.. _`audreyr/cookiecutter-pypackage`: https://github.com/audreyr/cookiecutter-pypackage
