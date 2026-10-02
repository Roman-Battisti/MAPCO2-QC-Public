=============
Quality Flags
=============


------
Common
------

The following quality flags can be found in any quality variable.

+----------------+-----------------+------------------------------------------+
| Mnemonic       | Attribute Value | Attribute Meaning                        |
+================+=================+==========================================+
| GOOD           | 1               | No issues found with this data point.    |
+----------------+-----------------+------------------------------------------+
| MISSING_DATA   | 2               | An observation or set of observations    |
|                |                 | are missing or could not be retrieved.   |
+----------------+-----------------+------------------------------------------+
| OUT_OF_RANGE   | 4               | The data point exceeds the bounds of the |
|                |                 | netCDF variable's valid_range attribute. |
+----------------+-----------------+------------------------------------------+
| SPIKE_DETECTED | 8               | The data point exceeds a threshold for   |
|                |                 | local standard deviation.                |      
+----------------+-----------------+------------------------------------------+

------------
CYCLE HEADER
------------

The span_coefficient variable has one specific mask value.

+-----------------+-----------------+------------------------------------------+
| Mnemonic        | Attribute Value | Attribute Meaning                        |
+=================+=================+==========================================+
| BAD_TEMPERATURE | 512             | The temperature associated with the      |
|                 |                 | updated span coefficient was not         |
|                 |                 | good.                                    |
+-----------------+-----------------+------------------------------------------+

-----
Licor
-----

* xco2_wet (SPOFF and SPOSTCAL only)

+-------------------+-----------------+------------------------------------------+
| Mnemonic          | Attribute Value | Attribute Meaning                        |
+===================+=================+==========================================+
| OUT_OF_SPAN_RANGE | 131072          | Whether or not xCO2 was within a         |
|                   |                 | specific range of the initial span       |
|                   |                 | value.                                   |
+-------------------+-----------------+------------------------------------------+

-----
Merge
-----

o2_ratio
========

+-----------------+-----------------+------------------------------------------+
| Mnemonic        | Attribute Value | Attribute Meaning                        |
+=================+=================+==========================================+
| BAD_APOFF_O2    | 512             | The O2 values taken from the APOFF       |
|                 |                 | netCDF file had questionable QC.         |
+-----------------+-----------------+------------------------------------------+
| BAD_EPOFF_O2    | 1024            | The O2 values taken from the EPOFF       |
|                 |                 | netCDF file had questionable QC.         |
+-----------------+-----------------+------------------------------------------+

xco2
====

* xco2_sw_wet_qc (merge)
* xco2_sw_dry_qc (merge)
* xco2_air_wet_qc (merge)
* xco2_air_dry_qc (merge)

+-------------------+-----------------+------------------------------------------+
| Mnemonic          | Attribute Value | Attribute Meaning                        |
+===================+=================+==========================================+
| OUT_OF_SPAN_RANGE | 131072          | Whether or not xCO2 was within a         |
|                   |                 | specific range of the initial span       |
|                   |                 | value.                                   |
+-------------------+-----------------+------------------------------------------+
| BAD_GPS           | 128             | Whether or not the GPS datasets were     |
|                   |                 | good.                                    |
+-------------------+-----------------+------------------------------------------+
| BAD_SSTC          | 256             | Whether or not the MET salinity and SST  |
|                   |                 | datasets were good.                      |
+-------------------+-----------------+------------------------------------------+

.. _SAMI_quality_flags:

----
SAMI
----

+-----------------------------+-----------------+------------------------------+
| Mnemonic                    | Attribute Value | Attribute Meaning            |
+=============================+=================+==============================+
| BAD_SSTC                    | 256             | Whether or not the MET       |
|                             |                 | salinity and SST datasets    |
|                             |                 | were good.                   |
+-----------------------------+-----------------+------------------------------+
| EXTERNAL_SAMI_OUTLIER       | 512             | pH error is large            | 
+-----------------------------+-----------------+------------------------------+
| EXTERNAL_SAMI_PUMP          | 1024            | pump problem                 |
+-----------------------------+-----------------+------------------------------+
| EXTERNAL_SAMI_SATURATION    | 2048            | saturation problem           |
+-----------------------------+-----------------+------------------------------+
| EXTERNAL_SAMI_BLANK         | 4096            | blanks problem               |
+-----------------------------+-----------------+------------------------------+
| INVALID_434_578_MEASUREMENT | 8192            | invalid inputs               |
+-----------------------------+-----------------+------------------------------+
| TOO_FEW_MEASUREMENTS        | 16384           | there were not enough data   |
|                             |                 | points to perform a          |
|                             |                 | regression                   |
+-----------------------------+-----------------+------------------------------+

-----
SBE16
-----

There is one quality flag that is specific to the SBE16 variables ntu_nighttime and chl_nighttime.  

+------------+-----------------+----------------------------------+
| Mnemonic   | Attribute Value | Attribute Meaning                |
+============+=================+==================================+
| DAYTIME    | 512             | A measurement took place during  |
|            |                 | the day.                         |
+------------+-----------------+----------------------------------+
