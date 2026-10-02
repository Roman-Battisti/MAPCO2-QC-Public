===================
SOCAT Quality Flags
===================


The following quality flags are defined for the final merged-and-qc'd
netCDF file and SOCAT CSV file.  Only three variables will have associated 
SOCAT QC variables:

* xco2_sw_wet 
* xco2_air_wet 
* ph 

Be sure you are clear as to the meaning of the terms "flag_masks QC"
and "flag_values QC".  When the term "flag_masks QC" is used, we are
referring to the bitmask QC netCDF variable where a single condition
(i.e. out of range) corresponds to a single bit being flipped.

The term "flag_values QC" refers to the netCDF variables that describe
quality according to the WOCE standard.  In addition, it also refers to
the QF columns in the SOCAT CSV file.

Currently, after all QC tests have been completed and after
the merge process has completed, SOCAT quality variables are created in the
merged netCDF file according to the following table:

+--------------+-----------------+---------------------------------------------+
| Mnemonic     |           Value | Attribute Meaning                           |
+==============+=================+=============================================+
| GOOD         | 2               | Corresponds to a flag_masks value of zero.  |
|              |                 | The only way a particular datum can have a  |
|              |                 | SOCAT QC value of GOOD is if no implemented |
|              |                 | QC check found any issue with this datum.   |
+--------------+-----------------+---------------------------------------------+
| QUESTIONABLE | 3               | A datum that does not already have          |
|              |                 | its flag_value QC assigned the value        |
|              |                 | of GOOD, BAD, or MISSING will have          |
|              |                 | its flag_value QC assigned the value        |
|              |                 | of QUESTIONABLE.                            |
+--------------+-----------------+---------------------------------------------+
| BAD          | 4               | A datum that does not already have          |
|              |                 | its flag_value QC assigned the value        |
|              |                 | of GOOD or MISSING will have its            |
|              |                 | flag_value QC assigned the value of         |
|              |                 | BAD if either of the flag_mask QC bits      |
|              |                 | MANUALLY_FLAGGED or OUT_OF_RANGE has        |
|              |                 | been set.                                   |
+--------------+-----------------+---------------------------------------------+
| MISSING      | 5               | The flag_masks attribute had the            |
|              |                 | MISSING_DATA bit set.  Note that other      |
|              |                 | bits might be set as well, but the          | 
|              |                 | MISSING_DATA bit overrides them all.        |
+--------------+-----------------+---------------------------------------------+

For example, suppose that a pH datum has an associated flag_masks value
of 0.  The value of 0 has no bits set, so this corresponds to a WOCE
flag_value of 2, i.e. *GOOD*.

For a second example, suppose that a different pH datum has an associated
value of 1, which has a binary representation of 0x00000001.  This value
will yield a positive number when a bitwise AND is performed with the
flag_masks QC value for MISSING_DATA and translates into a WOCE QC value
of 5, i.e. *MISSING*.

For a third example, suppose that yet another pH datum has an associated
value of 66, which has a binary representation of 0x01000010.  This value
will yield a positive number when a bitwise AND is performed with the
flag_masks QC value for either OUT_OF_RANGE or BAD_GPS.  Right now we
do not care about BAD_GPS if the OUT_OF_RANGE bit has been set, so this
translates into a WOCE QC value of 4, i.e. *BAD*.

A dump of a netCDF file for these exammples is shown below.  For the sake
of brevity, all other netCDF variables and most of the global attributes
have been removed. ::

  netcdf a {
  dimensions:
  	time = UNLIMITED ; // (3 currently)
  variables:
  	int64 time(time) ;
  		time:long_name = "time" ;
  		time:standard_name = "time" ;
  		time:units = "seconds since 1970-01-01" ;
  		time:calendar = "gregorian" ;
  	double ph(time) ;
  		ph:_FillValue = -9999. ;
  		ph:long_name = "pH" ;
  		ph:units = "1" ;
  		ph:valid_range = 7.5, 8.9 ;
  		ph:ancillary_variables = "ph_qc ph_socat_qc" ;
  	uint ph_qc(time) ;
  		ph_qc:_FillValue = 4294967295U ;
  		ph_qc:flag_masks = 0LL, 1LL, 2LL, 4LL, 32LL, 64LL, 128LL ;
  		ph_qc:flag_meanings = "quality_good missing_data out_of_range spike_detected manually_flagged bad_gps bad_sstc" ;
  		ph_qc:long_name = "ph Quality" ;
  		ph_qc:standard_name = "status_flag" ;
  	ubyte ph_socat_qc(time) ;
  		ph_socat_qc:_FillValue = 255UB ;
  		ph_socat_qc:flag_meanings = "good questionable bad missing" ;
  		ph_socat_qc:flag_values = 2LL, 3LL, 4LL, 5LL ;
  		ph_socat_qc:long_name = "pH SOCAT QC" ;
  		ph_socat_qc:standard_name = "status_flag" ;
  
  // global attributes:
  		:firmware_version_number = 6.09 ;
  		:firmware_version_date = "2015-03-27T00:00:00" ;
  		:instrument = "MAPCO2" ;
  		:site_code = "WHOTS" ;
  		:site_id = "whots" ;
  		:system_number = 132LL ;
  		:standard_name_vocabulary = "CF Standard Name Table v27" ;
  data:
  
   time = 1537694220, 1537705020, 1537715820 ;
  
   ph = 8.0634, 9.0663, 8.0641 ;
  
   ph_qc = 0, 1, 66 ;
  
   ph_socat_qc = 2, 5, 4 ;
  }


