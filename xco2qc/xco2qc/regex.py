"""
Setup all the regular expressions we need to parse the raw MAPCO2 file.
"""

import re

# Set up a regex to match the 1st header line, which looks something
# like this:
#
# NORM 00000 00000 2016/10/19 18:00:00     CCE1 0013 06.09 03/27/2015
pattern = r"""
           ^
           (?P<header_mode>\w{4})
           \s
           (?P<rand1>\d{5})
           \s
           (?P<rand2>\d{5})
           \s
           (?P<time>\d{4}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2})
           \s+
           (?P<site_id>\w+)
           \s
           (?P<system_number>\d{4})
           \s
           (
               (?P<ver_num>\d+\.\d+)
               \s
               (?P<ver_date>\d{2}/\d{2}/\d{4})
           )?
           \s*
           $
           """
header_line1_regex = re.compile(pattern, re.VERBOSE)

# The subsequent header line looks like this:
# 10/19/2016 18:07:34 3328.2727 N 12231.9959 W 0155 1.7 \
#       2016/10/19 12:26:23 2016/10/19 12:26:22     I 0030
pattern = r"""
           ^
           (?P<gps_dtime>\d{2}/\d{2}/\d{4}\s\d{2}:\d{2}:\d{2})
           \s
           (?P<raw_lat>[+-]?[0-9]+\.[0-9]+)
           \s
           (?P<NorS>N|S)
           \s
           (?P<raw_lon>[+-]?[0-9]+\.[0-9]+)
           \s
           (?P<EorW>E|W)
           \s
           (?P<gps_aqtime>\d{4})
           \s
           # the digits past the decimal point are optional
           (?P<gps_qf>[+-]?[0-9]+\.([0-9]+)?)
           (
               \s
               (?P<sys_dtime2>\d{4}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2})
               \s
               (?P<gps_dtime_ck>\d{4}/\d{2}/\d{2}\s\d{2}:\d{2}:\d{2})
               \s+
               (
                   (?P<in_out_flag>I|O)
                   \s
                   (?P<valve_pulse>\d{4})
                   \s
               )?
           )?
           """
header_line2_regex = re.compile(pattern, re.VERBOSE)

# The final header header line looks like this:
# 13.5 10.3 00.830764 00.896006 00.000000 0000
pattern = r"""
           ^
           (?P<battery_logic>[+-]?[0-9]+\.[0-9]+)
           \s
           (?P<battery_trans>[+-]?[0-9]+\.[0-9]+)
           \s
           (?P<zero_coefficient>[+-]?[0-9]+\.[0-9]+)
           \s
           (?P<span_coefficient>[+-]?[0-9]+\.[0-9]+)
           \s
           (
               (?P<span2_coefficient>[+-]?[0-9]+\.[0-9]+)
               \s
           )?
           (?P<li_flag>\w{4})
           \s+
           $
           """
header_line3_regex = re.compile(pattern, re.VERBOSE)

pattern = r"""
    ^
    \*+
    \s
    (?P<mode>(Zero|Span|Equil|Air))
    \s
    cycle
    \s
    (?P<action>(pump|post))
    \s
    (?P<state>(on|off|cal))
    \s
    (?P<minutes_past_cycle_start>\d{2})
"""
mapco2_pump_regex = re.compile(pattern, re.VERBOSE)

pattern = r"""
    ^
    (?P<sensor>(Li|O2|RH|Rh\stemp))
    \s
    samples
    \s
    (?P<num_samples>-?\d+)
"""
mapco2_sensor_regex = re.compile(pattern, re.VERBOSE)

pattern = r"""
    ^
    \**
    \s
    Durafet\sData\spump\stime
    \s
    (?P<item>\d{4})
"""
durafet_section_banner = re.compile(pattern, re.VERBOSE)

pattern = r"""
   \s+
   (?P<year>\d{4})
   /
   (?P<month>\d{2})
   /
   (?P<day>\d{2})
   \s
   (?P<hour>\d{2})
   :
   (?P<minute>\d{2})
   :
   (?P<second>\d{2})
   \s+
   (?P<battery>-?\d+\.\d+)
   \s+
   (?P<temperature>-?\d+\.\d+)
   \s+
   (?P<fet_int>-?\d+\.\d+)
   \s+
   (?P<fet_ext>-?\d+\.\d+)
   \s+
   (?P<isolated_power>-?\d+\.\d+)
   \s+
   (?P<controller_temp>-?\d+\.\d+)
   \s+
   (?P<temperature_voltage>-?\d+\.\d+)
   \s+
   (?P<pressure>-?\d+\.\d+)
   \s+
   (?P<ph_ext>-?\d+\.\d+)
   \s+
   (?P<ph_int>-?\d+\.\d+)
"""
durafet_data = re.compile(pattern, re.VERBOSE)

pattern = r"""
    ^
    \**
    \s
    (?P<sensor>Met)\sData
"""
met_section_banner = re.compile(pattern, re.VERBOSE)

pattern = r"""
    ^
    \**
    \s
    (
        (?P<sensor>Met|SBE16)\sData$
        |
        (?P<seafet>Seafet)
    )
"""
other_sensor_regex = re.compile(pattern, re.VERBOSE)

# CTD data
#
# example
#
# **************************************** CTD Data
pattern = r"""
    ^
    \**
    \s
    (?P<sensor>CTD)\sData
"""
ctd_section_banner = re.compile(pattern, re.VERBOSE)

# PRAWLER CTD data
#
# example
#
# PRAWLER CTD Samples 15 17
#
# The importance of the 15, 17 are unknown.  They are ignored.
pattern = r"""
    ^
    PRAWLER\sCTD\sSamples
    \s
    (?P<unused1>\d+)\s(?P<unused2>\d+)
"""
prawler_ctd_cycle_header = re.compile(pattern, re.VERBOSE)

pattern = r"""^
              (?P<sensor>SSTC|Wind)
              \s
              samples
              \s
              (?P<num_samples>\d+)
"""
met_variable = re.compile(pattern, re.VERBOSE)

pattern = r"""
    ^
    (?P<data_source>
        Pressure
        |
        Channel\s(?P<sub_channel>\d)
        |
        Serial\s(?P<sub_serial>SBE38|SBE50|GTD|dual\sGTD|optode|sbe63)
        |
        Wetlabs
        |
        Sound\svelocity
        |
        Density
        |
        Voltage
        |
        Current
    )
    \s
    samples
    \s+
    (?P<num_samples>\d+)
"""
sbe16_regex = re.compile(pattern, re.VERBOSE | re.IGNORECASE)

pattern = r"""
    ^
    \s+
    Sami
    \s
    Data
    \s*
    $
"""
sami_section_regex = re.compile(pattern, re.VERBOSE)
