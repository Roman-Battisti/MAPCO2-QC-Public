"""
Data dictionary for all netCDF variables.
"""
# standard library imports
import importlib.resources as ir

# 3rd party library imports
import numpy as np
import yaml

# local imports
from . import config

# Load all the variable definitions for each instrument / data source.
data_dict = {}
for tag in [
    'raw_cycle_header', 'cycle_header',
    'raw_durafet', 'durafet',
    'historical',
    'raw_licor', 'licor',
    'raw_met', 'external_met', 'met',
    'raw_prawler_ctd', 'prawler_ctd',
    'raw_sami', 'external_sami', 'sami',
    'raw_sbe16', 'sbe16',
    'external_sbe63', 'sbe63',
    'raw_seafet', 'seafet',
    'merge',
    'socat',
]:
    yaml_file = f"{tag}.yml"
    with ir.as_file(ir.files(config).joinpath(yaml_file)) as path:
        data_dict[tag] = yaml.safe_load(path.open())

numpy_codes_to_numpy_datatypes = {
    'f8': np.float64,
    'f4': np.float32,
    'i8': np.int64,
    'i4': np.int32,
    'i2': np.int16,
    'i1': np.int8,
    'I1': np.uint8,
    'I2': np.uint16,
    'I4': np.uint32,
}

# Transform the datatypes from numpy codes to actual numpy datatypes.  The
# datatypes are listed as string codes because yaml requires them as strings.
for tag, vardefs in data_dict.items():
    for variable, metadata in vardefs.items():
        try:
            klass = numpy_codes_to_numpy_datatypes[metadata['datatype']]
        except KeyError:
            if metadata['datatype'] == 'str':
                # this is a special case for vlen strings
                metadata['datatype'] = str
            else:
                # nc_char type, datatype was S1
                metadata['datatype'] = np.dtype('S1')
        else:
            metadata['datatype'] = klass

# Provide a fill value.
for tag, vardefs in data_dict.items():
    for variable, metadata in vardefs.items():
        klass = metadata['datatype']
        if 'fill_value' not in metadata:
            # provide a default value of -9999
            # this is just like saying np.int32(-9999)
            metadata['fill_value'] = klass(-9999)
        elif klass == np.dtype('S1'):
            # do nothing, the fill value is already set
            pass
        else:
            # instantiate the assigned fill value according to the datatype.
            metadata['fill_value'] = klass(metadata['fill_value'])

# The flag masks must be the same as the variable (uint32?)
for tag, vardefs in data_dict.items():
    for variable, metadata in vardefs.items():
        if 'flag_values' in metadata['attributes']:
            klass = metadata['datatype']
            metadata['attributes']['flag_values'] = np.array(
                metadata['attributes']['flag_values'],
                dtype=klass
            )
        if 'flag_masks' in metadata['attributes']:
            klass = metadata['datatype']
            metadata['attributes']['flag_masks'] = np.array(
                metadata['attributes']['flag_masks'],
                dtype=klass
            )

# most floating point netCDF variables will use this fill value
DEFAULT_FILLVALUE = -9999

# all netCDF files will have this dimension
TIME = 'time'
