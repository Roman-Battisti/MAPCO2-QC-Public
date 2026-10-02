======================
Overview of Components
======================

-----------
xco2-nc2csv
-----------
``xco2-nc2csv`` converts a processed MAPCO2 netCDF file into a CSV file suitable for consumption by Excel.  Note that this can only be **processed** MAPCO2 netCDF files, not the raw netCDF files, as those may contain 2D variables.

::

    $ xco2-nc2csv --help
    usage: xco2-nc2csv [-h] input_ncfile output_csv

    Convert an xCO2 netCDF file to CSV.

    positional arguments:
      input_ncfile  Input netCDF file
      output_csv    Output CSV file

    optional arguments:
      -h, --help    show this help message and exit


