# Quality flags
GOOD = 1
MISSING_DATA = 2

# data was outside of netCDF valid_range attribute
OUT_OF_RANGE = 4

# If spike detection is turned on, then the data has spiked.  Usually this
# means that standard deviation is high?
SPIKE_DETECTED = 8

# The user manually flagged the data via the jupyter notebook.
MANUALLY_FLAGGED = 64

# These flags are for when quality is deemed questionable due to another
# variable, but not one that is used to compute the xco2.  For instance, a bad
# gps reading doesn't necessarily mean that the xco2 data is bad.
BAD_GPS = 128
BAD_SSTC = 256

# xco2-specific
TREND_STDDEV_OUT_OF_RANGE = 512
RAW_STDDEV_OUT_OF_RANGE = 1024
EXCESS_PRESSURE_OFF_DIFFERENCE = 2048
AIR_PUMP_PRESSURE_DIFFERENCE = 4096
EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE = 8192
SPAN_PUMP_PRESSURE_DIFFERENCE = 16384
EXCESS_RH_STDDEV = 32768
EXCESS_RH_TEMP_STDDEV = 65536

# this is set on pco2 and others if xco2 is manually flagged
MANUALLY_FLAGGED_XCO2 = 131072

# Whether xCO2 in SPOSTCAL, SPOFF is in a specific range of the initial span
# value
OUT_OF_SPAN_RANGE = 131072

# specific to the merge o2 ratio
BAD_APOFF_O2 = 512
BAD_EPOFF_O2 = 1024

# ph specific
EXTERNAL_SAMI_OUTLIER = 512
EXTERNAL_SAMI_PUMP = 1024
EXTERNAL_SAMI_SATURATION = 2048
EXTERNAL_SAMI_BLANK = 4096
INVALID_434_578_MEASUREMENT = 8192
TOO_FEW_MEASUREMENTS = 16384

# specific to nighttime ntu and chlorophyll
DAYTIME = 512

# specific to updated span coefficient
BAD_TEMPERATURE = 512

# SOCAT quality flags
SOCAT_GOOD = 2
SOCAT_QUESTIONABLE = 3
SOCAT_BAD = 4
SOCAT_MISSING = 5
