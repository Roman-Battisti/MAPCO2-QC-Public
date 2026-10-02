============================
Overview of Older Components
============================

These are older command line utilites that are no longer really needed in the jupyterhub era.

--------------------
xco2-convert-to-nc
--------------------
``xco2-convert-to-nc`` converts a raw MAPCO2 text file into several
netCDF files, one for each LICOR pump mode, one for the SBE16 data
stream (if it exists) and the MET data stream (if it exists).
Other than converting to the netCDF format, no processing of any kind
is done.

Even though the MET data stream sections lie outside of the SBE16
sections, the MET data is merged with the SBE16 data before writing
to file.

Due to the complexity of the MAPCO2 text file, the module responsible
for this conversion is by far the largest and most complex.

::

    $ xco2-convert-to-nc --help
    usage: xco2-convert-to-nc [-h] [--verbosity {critical,error,warning,info,debug}] input output

    positional arguments:
      input                 Input file
      output                Output netCDF directory

    optional arguments:
      -h, --help            show this help message and exit
      --verbosity {critical,error,warning,info,debug}
                            Logging level


-------------
xco2-reduce
-------------

``xco2-reduce`` takes the raw netCDF measurements/arrays and reduces
them to 1D variables.

The data reduction step is the only other place outside the QC module
where any QC flags are computed (for missing data).

::

    $ xco2-reduce -h
    usage: xco2-reduce [-h] [--reduce-method {mean,median}] [--verbosity {critical,error,warning,info,debug}] input output
    
    positional arguments:
      input                 Source directory of raw netCDF files
      output                Destination directory for reduced netCDF files
    
    optional arguments:
      -h, --help            show this help message and exit
      --reduce-method {mean,median}
                            Data reduction method, default is mean
      --verbosity {critical,error,warning,info,debug}
                            Logging level


---------
xco2-calc
---------

``xco2-calc`` runs algorithms to recover the ``xCO2_dry``,
``post_xCO2_wet``, and ``post_xCO2_dry`` parameters.

::

    $ xco2-calc -h
    usage: xco2-calc [-h] [--verbosity {critical,error,warning,info,debug}] input

    positional arguments:
      input                 Source directory of reduced netCDF files, we write back to these files.

    optional arguments:
      -h, --help            show this help message and exit
      --verbosity {critical,error,warning,info,debug}
                            Logging level


--------------
xco2-qc
--------------
``xco2-qc`` applies QC measures against various parameters.

::

  $ xco2-qc --help
  usage: xco2-qc [-h] [--verbosity {critical,error,warning,info,debug}] [--initial-span-cal INITIAL_SPAN_CAL]
                 [--air-diff-range AIR_DIFF_RANGE AIR_DIFF_RANGE] [--equil-diff-range EQUIL_DIFF_RANGE EQUIL_DIFF_RANGE]
                 [--span-diff-range SPAN_DIFF_RANGE SPAN_DIFF_RANGE] [--ppm-zero-range PPM_ZERO_RANGE PPM_ZERO_RANGE]
                 [--ppm-span-cal-range PPM_SPAN_CAL_RANGE PPM_SPAN_CAL_RANGE] [--max-air-xco2-std MAX_AIR_XCO2_STD]
                 [--max-equil-xco2-std MAX_EQUIL_XCO2_STD] [--max-pressoff-diff MAX_PRESSOFF_DIFF]
                 [--max-rh-std MAX_RH_STD] [--max-rh-temp-std MAX_RH_TEMP_STD] [--xco2-trend-std XCO2_TREND_STD]
                 [--num-points-eachside NUM_POINTS_EACHSIDE] [--spike-detection {yes,no}]
                 input
  
  positional arguments:
    input                 Source directory of netCDF files
  
  optional arguments:
    -h, --help            show this help message and exit
    --verbosity {critical,error,warning,info,debug}
                          Logging level
    --initial-span-cal INITIAL_SPAN_CAL
                          Initial Span Calibration (corresponds to 'initial_span_cal' in the configuration file
    --air-diff-range AIR_DIFF_RANGE AIR_DIFF_RANGE
                          Range of pressure difference between APON and APOFF
    --equil-diff-range EQUIL_DIFF_RANGE EQUIL_DIFF_RANGE
                          Range of pressure difference between EPON and EPOFF
    --span-diff-range SPAN_DIFF_RANGE SPAN_DIFF_RANGE
                          Range of pressure difference between SPON and SPOFF
    --ppm-zero-range PPM_ZERO_RANGE PPM_ZERO_RANGE
                          PPM Range of ZPON/ZPOSTCAL xco2 range around zero
    --ppm-span-cal-range PPM_SPAN_CAL_RANGE PPM_SPAN_CAL_RANGE
                          PPM Range of SPOFF xco2 range around the span calibration value
    --max-air-xco2-std MAX_AIR_XCO2_STD
                          Maximum allowed value for APOFF xCO2 standard deviation
    --max-equil-xco2-std MAX_EQUIL_XCO2_STD
                          Maximum allowed value for EPOFF xCO2 standard deviation
    --max-pressoff-diff MAX_PRESSOFF_DIFF
                          Maximum allowed value for pressure differences between APOFF, EPOFF, and SPOFF.
    --max-rh-std MAX_RH_STD
                          Maximum allowed value for RH standard deviation
    --max-rh-temp-std MAX_RH_TEMP_STD
                          Maximum allowed value for RH TEMP standard deviation
    --xco2-trend-std XCO2_TREND_STD
                          Maximum trend STD allowed value for APOFF/EPOFF xCO2
    --num-points-eachside NUM_POINTS_EACHSIDE
                          1/2 window size for trend STD calculation
    --spike-detection {yes,no}
                          Run spike detection, default is yes


-----------------------
xco2-merge
-----------------------
``xco2-merge`` merges together the final netCDF file from the disparate sources.

::

  $ xco2-merge -h
  usage: xco2-merge [-h] [--verbosity {critical,error,warning,info,debug}] input output
  
  Command line utility for merging the SPOFF, EPOFF, and APOFF variables into a single netCDF file.
  
  positional arguments:
    input                 Source directory of intermediate netCDF files
    output                Merge netCDF file
  
  optional arguments:
    -h, --help            show this help message and exit
    --verbosity {critical,error,warning,info,debug}
                          Logging level


----------------
xco2-adjustments
----------------

::

  $ xco2-adjustments -h
  usage: xco2-adjustments [-h] [--pressure-correction PRESSURE_CORRECTION] [--mbl-xco2-correction MBL_XCO2_CORRECTION]
                          [--verbosity {critical,error,warning,info,debug}]
                          input output
  
  Command line utility for adjusting the final netCDF file for any LICOR pressure correction or MBL xCO2 offset.
  
  positional arguments:
    input                 Source directory of intermediate netCDF files
    output                Merge netCDF file
  
  optional arguments:
    -h, --help            show this help message and exit
    --pressure-correction PRESSURE_CORRECTION
                          Licor pressure correction
    --mbl-xco2-correction MBL_XCO2_CORRECTION
                          Marine Boundary Layer correction
    --verbosity {critical,error,warning,info,debug}
                          Logging level

---------------------------------
xco2-apply-metadata-conventions
---------------------------------
``xco2-apply-metadata-conventions`` applies CF, ACDD,
and OceanSITES metadata conventions to the final netCDF product file.

::

  $ xco2-apply-metadata-conventions -h
  usage: xco2-apply-metadata-conventions [-h] [--verbosity {critical,error,warning,info,debug}] input
  
  positional arguments:
    input                 Source directory of final netCDF files
  
  optional arguments:
    -h, --help            show this help message and exit
    --verbosity {critical,error,warning,info,debug}
                          Logging level

-------------
xco2-socat-qc
-------------

::

  $ xco2-socat-qc --help
  usage: xco2-socat-qc [-h] [--verbosity {critical,error,warning,info,debug}] ncfile

  Utility for converting QC bit masks into SOCAT QC.

  positional arguments:
    ncfile                Merged netCDF file

  optional arguments:
    -h, --help            show this help message and exit
    --verbosity {critical,error,warning,info,debug}
                        Logging level

--------------                          
xco2-gen-socat
--------------                          

::

  $ xco2-gen-socat -h
  usage: xco2-gen-socat [-h] [--verbosity {critical,error,warning,info,debug}] ncfile xmlfile csvfile
  
  positional arguments:
    ncfile                Merge netCDF file
    xmlfile               Output SOCAT XML file
    csvfile               Output SOCAT CVS file
  
  optional arguments:
    -h, --help            show this help message and exit
    --verbosity {critical,error,warning,info,debug}
                          Logging level

---------
xco2-trim
---------

::

  $ xco2-trim --help
  usage: xco2-trim [-h] [--start START] [--stop STOP] [--verbosity {critical,error,warning,info,debug}]
                   input_ncfile output_ncfile
  
  Trim points outside of a designated start and stop. If start and/or stop are not given, then the first and/or last
  points in the time series are used in their stead.
  
  positional arguments:
    input_ncfile          Input merge netCDF file
    output_ncfile         Output trimmed netCDF file
  
  optional arguments:
    -h, --help            show this help message and exit
    --start START         Start date
    --stop STOP           Stop date
    --verbosity {critical,error,warning,info,debug}
                          Logging level
