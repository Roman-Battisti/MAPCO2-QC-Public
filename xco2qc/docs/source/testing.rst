======================
Running the Test Suite
======================

You can run the test suite by changing folders to MAPCO2-QC and executing
the following ::

  $ pytest

Using the pytest-xdist plugin can greatly speed up the tests.  If you
have 4 cores available, then ::

  $ pytest -n 4

An even better way to run the test suite would be to have pytest stop
as soon as any error is encountered, i.e. ::

  $ pytest -n 4 -x

The standard library also provides a way of running the tests ::

  $ python -m unittest discover

This method is no faster than running pytest on a single core, though,
and it will echo a number of warnings originating from within 3rd party
libraries that pytest would suppress.
