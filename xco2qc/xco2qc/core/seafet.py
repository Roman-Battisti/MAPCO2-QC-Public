# These are the dataframe column names when the long frame raw data is read
LONG_FRAME_COLUMNS = [
    'header', 'date', 'time', 'ph_int', 'ph_ext', 'temperature', 'temp_ctd',
    's_ctd', 'o_ctd', 'p_ctd', 'vrs_fet_int', 'vrs_fet_ext', 'v_therm',
    'v_supply', 'i_supply', 'humidity', 'v_5v', 'v_mbatt', 'v_iso',
    'v_isobatt', 'i_b', 'i_k', 'v_k', 'status', 'check_sum'
]

# These are the dataframe column names when the short frame raw data is read
SHORT_FRAME_COLUMNS = [
    'header', 'date', 'time', 'ph_int', 'ph_ext', 'temp', 'temp_ctd',
    's_ctd', 'o_ctd', 'p_ctd', 'status', 'check_sum'
]

# These are the dataframe column names when the 3rd "unknown" format is read.
VBA_FRAME_COLUMNS = [
    'header', 'date', 'time', 'ph_int', 'ph_ext', 'temperature',
    'vrs_fet_int', 'vrs_fet_ext', 'v_therm', 'v_supply',
    'unknown', 'i_supply', 'humidity', 'v_5v', 'v_iso', 'check_sum'
]
