# netCDF variable names when read from the raw mapco2 file
# RAW_LI = 'Li'
# O2 = 'O2'
# RH = 'RH'
# RH_TEMP = 'Rh_temp'

# Use mnemonics because the format of the filename might change, and we use
# these all over the place.
APON = 'air-pump-on'
APOFF = 'air-pump-off'
EPON = 'equil-pump-on'
EPOFF = 'equil-pump-off'
SPON = 'span-pump-on'
SPOFF = 'span-pump-off'
SPOSTCAL = 'span-post-cal'
ZPON = 'zero-pump-on'
ZPOFF = 'zero-pump-off'
ZPOSTCAL = 'zero-post-cal'

PUMP_MODES = [
    APON, APOFF, EPON, EPOFF, SPON, SPOFF, SPOSTCAL, ZPON, ZPOFF, ZPOSTCAL
]

# Hard code netCDF file names for the LICOR pump modes.
APON_NCFILE = f'licor.{APON}.nc'
APOFF_NCFILE = f'licor.{APOFF}.nc'
EPON_NCFILE = f'licor.{EPON}.nc'
EPOFF_NCFILE = f'licor.{EPOFF}.nc'
SPON_NCFILE = f'licor.{SPON}.nc'
SPOFF_NCFILE = f'licor.{SPOFF}.nc'
SPOSTCAL_NCFILE = f'licor.{SPOSTCAL}.nc'
ZPON_NCFILE = f'licor.{ZPON}.nc'
ZPOFF_NCFILE = f'licor.{ZPOFF}.nc'
ZPOSTCAL_NCFILE = f'licor.{ZPOSTCAL}.nc'

NCFILES = [
    APON_NCFILE, APOFF_NCFILE, EPON_NCFILE, EPOFF_NCFILE, SPON_NCFILE,
    SPOFF_NCFILE, SPOSTCAL_NCFILE, ZPON_NCFILE, ZPOFF_NCFILE, ZPOSTCAL_NCFILE
]

# Map the saildrone states to netCDF file names.
SAILDRONE_NCFILES = {
    'APON': APON_NCFILE,
    'APOFF': APOFF_NCFILE,
    'EPON': EPON_NCFILE,
    'EPOFF': EPOFF_NCFILE,
    'SPON': SPON_NCFILE,
    'SPOFF': SPOFF_NCFILE,
    'SPPCAL': SPOSTCAL_NCFILE,
    'ZPON': ZPON_NCFILE,
    'ZPOFF': ZPOFF_NCFILE,
    'ZPPCAL': ZPOSTCAL_NCFILE,
}

# This will be a global attribute for each licor netCDF file
GLOBAL_ATT_PUMP_MODES = {
    'APON': 'air pump on',
    'APOFF': 'air pump off',
    'EPON': 'equil pump on',
    'EPOFF': 'equil pump off',
    'SPON': 'span pump on',
    'SPOFF': 'span pump off',
    'SPPCAL': 'span post cal',
    'ZPON': 'zero pump on',
    'ZPOFF': 'zero pump off',
    'ZPPCAL': 'zero post cal',
}
