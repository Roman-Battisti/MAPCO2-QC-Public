=================================
Overview of netCDF File Structure
=================================

There are two ways one can look at the structure of the netCDF files.
Obviously, one way is by looking at the output of the
`ncdump <https://www.unidata.ucar.edu/software/netcdf/docs/netcdf_utilities_guide.html#ncdump_SYNOPSIS>`_
program, which shows the structure of the file in the language of netCDF 
(called `CDL <https://www.unidata.ucar.edu/software/netcdf/docs/netcdf_utilities_guide.html>`_).
But before we can actually get to that structure, we can start with
something similar, but perhaps easier to wrap one's head around.
The most basic definitions of what goes into a netCDF file is kept in
`YAML <https://yaml.org>`_ files within the `xco2qc.core.vardefs` package.  YAML provides
a simple way to put together lists and dictionaries that is very nearly
sufficient to fully describe netCDF variables.

One item that bears explains are the YAML representation of netCDF datatypes,
which don't have a one-to-one translation.  Instead, we use the `numpy <https://numpy.org/>`_
package's character codes.  For example, "f4" in numpy means 32-bit floating point, which is just
"float" in the netCDF language, and "I8" means 64-bit unsigned integer. 

.. _Licor netCDF:

-----
Licor
-----

Raw
===

YAML 
----

Shown below is a portion of the YAML file for the LICOR O2 data after the samples have been averaged.

::

    o2:
      attributes:
        ancillary_variables: o2_qc
        long_name: Surface Seawater O2 Percent
        units: '1'
      datatype: f8
      dimensions:
      - time
      fill_value: -9999

netCDF
------

Shown below is the actual output of ``ncdump`` when run on Licor APOFF data that has been processed from the
raw text form into netCDF.  As you can see, most but not all of the information is the same.  Differences 
include the sizes of the dimensions which are not known until the data is actually read, as well as what's
known as global attributes, or metadata about the file.  Often these global attributes are also not known
until the data is actually read.

The entire file is shown, rather than just the O2 portion.

In this case, the O2 data spans 1703 time cycles, and each time cycle
allows for 58 measurements.  This data can be read as a two-dimensional
array (likely with 1703 rows and 58 columns).
::


    netcdf licor.air-pump-off {
    dimensions:
    	time = UNLIMITED ; // (1703 currently)
    	li_max_sample_size = 58 ;
    	num_li_vars = 5 ;
    	rh_max_sample_size = 58 ;
    	o2_max_sample_size = 58 ;
    	rh_temp_max_sample_size = 58 ;
    variables:
    	int64 time(time) ;
    		time:_FillValue = -9999LL ;
    		time:axis = "T" ;
    		time:calendar = "proleptic_gregorian" ;
    		time:long_name = "Time" ;
    		time:standard_name = "time" ;
    		time:units = "seconds since 1970-01-01T00:00:00" ;
    	int li(time, li_max_sample_size, num_li_vars) ;
    		li:_FillValue = -9999 ;
    	int rh(time, rh_max_sample_size) ;
    		rh:_FillValue = -9999 ;
    	int o2(time, o2_max_sample_size) ;
    		o2:_FillValue = -9999 ;
    	int rh_temp(time, rh_temp_max_sample_size) ;
    		rh_temp:_FillValue = -9999 ;
    
    // global attributes:
    		:data_source = "LICOR" ;
    		:pump_mode = "air pump off" ;
    		:site_code = "CCE2_09" ;
    		:site_id = "cce2_09" ;
    		:system_number = 109LL ;
    		:deployment_number = 9LL ;
    }

In this particular case, the site code extracted from the raw text file
is problematic, it is shown as *CCE2_09* when it should just be *CCE2*.

.. _Licor-averaged:

Averaged (reduced)
==================

These netCDF files have had averaging applied to their raw variables to
produce a one-dimensional time series, but more importantly, ancillary
quality variables have been introduced that describe the status of
various quality checks performed against each variable.  The
`flag_masks and flag_meanings <http://cfconventions.org/cf-conventions/cf-conventions.html#flags>`_
attributes describe the quality checks,
see :ref:`Quality Flags`.


::


    netcdf licor.air-pump-off {
    dimensions:
    	time = UNLIMITED ; // (1703 currently)
    variables:
    	int64 time(time) ;
    		time:long_name = "time" ;
    		time:standard_name = "time" ;
    		time:units = "seconds since 1970-01-01T00:00:00" ;
    		time:calendar = "gregorian" ;
    	double xco2_wet(time) ;
    		xco2_wet:_FillValue = -9999. ;
    		xco2_wet:ancillary_variables = "xco2_wet_qc xco2_wet_stddev" ;
    		xco2_wet:long_name = "Mole fraction of CO2" ;
    		xco2_wet:standard_name = "mole_concentration_of_carbon_dioxide_in_air" ;
    		xco2_wet:units = "umol / mol" ;
    		xco2_wet:valid_range = 0., 700. ;
    	uint xco2_wet_qc(time) ;
    		xco2_wet_qc:_FillValue = 4294967295U ;
    		xco2_wet_qc:flag_masks = 1U, 2U, 4U, 8U, 64U, 512U, 1024U, 131072U ;
    		xco2_wet_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged trend_stddev_out_of_range raw_stddev_out_of_range out_of_span_range" ;
    		xco2_wet_qc:long_name = "xco2_wet Quality" ;
    		xco2_wet_qc:standard_name = "status_flag" ;
    	double xco2_wet_stddev(time) ;
    		xco2_wet_stddev:_FillValue = -9999. ;
    		xco2_wet_stddev:long_name = "Mole fraction of CO2 STDDEV" ;
    		xco2_wet_stddev:units = "umol / mol" ;
    	double temperature(time) ;
    		temperature:_FillValue = -9999. ;
    		temperature:ancillary_variables = "temperature_qc" ;
    		temperature:long_name = "Temperature" ;
    		temperature:units = "degrees_Celsius" ;
    	uint temperature_qc(time) ;
    		temperature_qc:_FillValue = 4294967295U ;
    		temperature_qc:flag_masks = 1U, 2U, 4U, 8U, 64U ;
    		temperature_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged" ;
    		temperature_qc:long_name = "temperature Quality" ;
    		temperature_qc:standard_name = "status_flag" ;
    	double pressure(time) ;
    		pressure:_FillValue = -9999. ;
    		pressure:ancillary_variables = "pressure_qc" ;
    		pressure:long_name = "Pressure" ;
    		pressure:standard_name = "sea_water_pressure" ;
    		pressure:units = "kPa" ;
    	uint pressure_qc(time) ;
    		pressure_qc:_FillValue = 4294967295U ;
    		pressure_qc:flag_masks = 1U, 2U, 4U, 8U, 64U ;
    		pressure_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged" ;
    		pressure_qc:long_name = "pressure Quality" ;
    		pressure_qc:standard_name = "status_flag" ;
    	double voltage_counts1(time) ;
    		voltage_counts1:_FillValue = -9999. ;
    		voltage_counts1:ancillary_variables = "voltage_counts1_qc" ;
    		voltage_counts1:long_name = "LICOR Voltage Counts:  Raw 1" ;
    	uint voltage_counts1_qc(time) ;
    		voltage_counts1_qc:_FillValue = 4294967295U ;
    		voltage_counts1_qc:flag_masks = 1U, 2U, 4U, 8U, 64U ;
    		voltage_counts1_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged" ;
    		voltage_counts1_qc:long_name = "voltage_counts1 Quality" ;
    		voltage_counts1_qc:standard_name = "status_flag" ;
    	double voltage_counts2(time) ;
    		voltage_counts2:_FillValue = -9999. ;
    		voltage_counts2:ancillary_variables = "voltage_counts2_qc" ;
    		voltage_counts2:long_name = "LICOR Voltage Counts:  Raw 2" ;
    	uint voltage_counts2_qc(time) ;
    		voltage_counts2_qc:_FillValue = 4294967295U ;
    		voltage_counts2_qc:flag_masks = 1U, 2U, 4U, 8U, 64U ;
    		voltage_counts2_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged" ;
    		voltage_counts2_qc:long_name = "voltage_counts2 Quality" ;
    		voltage_counts2_qc:standard_name = "status_flag" ;
    	double o2(time) ;
    		o2:_FillValue = -9999. ;
    		o2:ancillary_variables = "o2_qc" ;
    		o2:long_name = "Surface Seawater O2 Percent" ;
    		o2:units = "1" ;
    	uint o2_qc(time) ;
    		o2_qc:_FillValue = 4294967295U ;
    		o2_qc:flag_masks = 1U, 2U, 4U, 8U, 64U ;
    		o2_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged" ;
    		o2_qc:long_name = "o2 Quality" ;
    		o2_qc:standard_name = "status_flag" ;
    	double rh(time) ;
    		rh:_FillValue = -9999. ;
    		rh:ancillary_variables = "rh_qc rh_stddev" ;
    		rh:long_name = "Relative Humidity" ;
    		rh:units = "TODO" ;
    	uint rh_qc(time) ;
    		rh_qc:_FillValue = 4294967295U ;
    		rh_qc:flag_masks = 1U, 2U, 4U, 8U, 64U ;
    		rh_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged" ;
    		rh_qc:long_name = "rh Quality" ;
    		rh_qc:standard_name = "status_flag" ;
    	double rh_stddev(time) ;
    		rh_stddev:_FillValue = -9999. ;
    		rh_stddev:long_name = "Relative Humidity STDDEV" ;
    		rh_stddev:units = "TODO" ;
    	double rh_temp(time) ;
    		rh_temp:_FillValue = -9999. ;
    		rh_temp:ancillary_variables = "rh_temp_qc rh_temp_stddev" ;
    		rh_temp:long_name = "Relative Humidity Temperature" ;
    		rh_temp:units = "TODO" ;
    	uint rh_temp_qc(time) ;
    		rh_temp_qc:_FillValue = 4294967295U ;
    		rh_temp_qc:flag_masks = 1U, 2U, 4U, 8U, 64U ;
    		rh_temp_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged" ;
    		rh_temp_qc:long_name = "rh_temp Quality" ;
    		rh_temp_qc:standard_name = "status_flag" ;
    	double rh_temp_stddev(time) ;
    		rh_temp_stddev:_FillValue = -9999. ;
    		rh_temp_stddev:long_name = "Relative Humidity Temperature STDDEV" ;
    		rh_temp_stddev:units = "TODO" ;
    
    // global attributes:
    		:data_source = "LICOR" ;
    		:pump_mode = "air pump off" ;
    		:site_code = "CCE2_09" ;
    		:site_id = "cce2_09" ;
    		:system_number = 109LL ;
    		:deployment_number = 9LL ;
    }

.. _SAMI netCDF:

----
SAMI
----

.. _SAMI-averaged:

Averaged
========

Here we have a netCDF file for the processed SAMI pH data.  The
temperature, pH, slope, r2, and battery variables have been derived from
the raw hex_string variable.

::

    netcdf sami {
    dimensions:
    	time = UNLIMITED ; // (294 currently)
    variables:
    	int64 time(time) ;
    		time:long_name = "time" ;
    		time:standard_name = "time" ;
    		time:units = "seconds since 1970-01-01T00:00:00" ;
    		time:calendar = "gregorian" ;
    	double temperature(time) ;
    		temperature:_FillValue = -9999. ;
    		temperature:ancillary_variables = "temperature_qc" ;
    		temperature:long_name = "Temperature" ;
    		temperature:units = "degrees_Celsius" ;
    	uint temperature_qc(time) ;
    		temperature_qc:_FillValue = 4294967295U ;
    		temperature_qc:flag_masks = 0LL, 1LL, 2LL, 4LL, 32LL ;
    		temperature_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged" ;
    		temperature_qc:long_name = "temperature Quality" ;
    		temperature_qc:standard_name = "status_flag" ;
    	double ph(time) ;
    		ph:_FillValue = -9999. ;
    		ph:ancillary_variables = "ph_qc" ;
    		ph:long_name = "pH" ;
    		ph:valid_range = 7.5, 8.9 ;
    	uint ph_qc(time) ;
    		ph_qc:_FillValue = 4294967295U ;
    		ph_qc:flag_masks = 0LL, 1LL, 2LL, 4LL, 32LL, 128LL, 4096LL, 8192LL ;
    		ph_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged bad_sstc invalid_434_578_measurement too_few_measurements" ;
    		ph_qc:long_name = "ph Quality" ;
    		ph_qc:standard_name = "status_flag" ;
    	double slope(time) ;
    		slope:_FillValue = -9999. ;
    		slope:long_name = "slope of pH linear regression" ;
    	double r2(time) ;
    		r2:_FillValue = -9999. ;
    		r2:long_name = "R**2 of pH linear regression" ;
    	double battery(time) ;
    		battery:_FillValue = -9999. ;
    		battery:long_name = "Battery" ;
    		battery:units = "volts" ;
    	int64 sami_time(time) ;
    		sami_time:_FillValue = -9999LL ;
    		sami_time:calendar = "proleptic_gregorian" ;
    		sami_time:comment = "timestamp from SAMI cycle" ;
    		sami_time:long_name = "Time" ;
    		sami_time:standard_name = "time" ;
    		sami_time:units = "seconds since 1970-01-01T00:00:00" ;
    
    // global attributes:
    		:instrument = "SAMI" ;
    		:site_code = "WHOTS" ;
    		:site_id = "whots" ;
    		:system_number = 132LL ;
    		:deployment_number = 1LL ;
    }
