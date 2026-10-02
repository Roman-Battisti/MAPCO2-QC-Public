# local imports
from . import climatology
from . import data
from . import external_sami_quality
from . import licor
from . import quality
from . import socat

from .mapco2core import MapCO2core, InvalidMapCO2ConfigFile
from .mapco2core import MissingParametersError  # noqa : E401
from .vardefs import DEFAULT_FILLVALUE, TIME

# Mnemonic for data reduction method.
REDUCE_MEAN = 0
REDUCE_MEDIAN = 1

DEFAULT_SOCAT_FILLVALUE = -999

# name of netCDF file(s) associated with mapco2 cycle header data, durafet,
# merge data.  The licor netCDF files are treated separately in its own module.
CYCLE_HEADER_NCFILE = 'cycle_header.nc'
DURAFET_NCFILE = 'durafet.nc'
MERGE_NCFILE = 'merge.nc'
MET_NCFILE = 'MetSSTC.nc'
PRAWLER_CTD_NCFILE = 'prawler_ctd.nc'
SAILDRONE_NCFILE = 'saildrone.nc'
SAMI_NCFILE = 'sami.nc'
SBE16_NCFILE = 'sbe16.nc'
SEAFET_NCFILE = 'seafet.nc'
TRIMMED_NCFILE = 'trimmed.nc'

HISTORICAL_NCFILE = 'historical.nc'

# The "external" file is in case the MET data is produced by external
# software, producing a TEXT file we will convert into netCDF.
EXTERNAL_MET_NCFILE = 'met_external.nc'
VALIDATION_NCFILE = 'validation.nc'

# The "external" file is in case the SAMI data is produced by external
# software, producing a TEXT file that we will convert into netCDF.
EXTERNAL_SAMI_NCFILE = 'sami_external.nc'

# Same for SBE63
EXTERNAL_SBE63_NCFILE = 'sbe63_external.nc'
EXTERNAL_SEAFET_NCFILE = 'seafet-external.nc'

# This file keeps regression and clustering data produced during licor
# regression calculations.
MODELS_FILE = 'regression_and_clustering.pkl'

pco2sys_region_labels = [
    'None',
    'Washington State coast and Puget Sound',
    'California Current Ecosystem',
    'South Atlantic Bight',
    'Gulf of Maine',
    'Kuroshio Extension',
    'Northeast Pacific',
    'North Atlantic 30N - 80N',
    'North Pacific ≥ 30N',
    'Subtropics Atlantic 30S - 30N',
    'Subtropics Pacific 30S - 30N',
    'Subtropics Indian ≤ 30S',
    'Eastern Equatorial Upwelling Pacific',
    'Central Equatorial upwelling Pacific',
    'Other Equatorial Pacific',
    'Southern Ocean',
    'CCE1',
    'CCE2',
]


__all__ = [
    licor, quality, socat, data, DEFAULT_FILLVALUE, external_sami_quality,
    'MapCO2core', 'InvalidMapCO2ConfigFile', TIME, climatology
]
