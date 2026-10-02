# standard packages
import datetime as dt

# 3rd party packages
import numpy as np
import pandas as pd


def get_qc_mask_varname(nc, varname):
    """
    Given a netCDF file handle and a variable, return the name of the
    associated QC mask variable, if there is one.

    Parameters
    ----------
    nc : netCDF4 file handle
    varname : str
        name of a netCDF variable

    Returns
    -------
    str for the name of the associated variable or None
    """
    try:
        ancillary = nc[varname].ancillary_variables
    except AttributeError:
        # no ancillary variables, therefore no QC variable
        return None

    # by the CF convention, ancillary_variables is a space-delimited text
    # string of all the variables associated with the current variable
    for qcvarname in ancillary.split():

        # we want the ancillary variable that has the attribute
        # standard_name "status_flag"
        try:
            if nc[qcvarname].standard_name == 'status_flag':
                return qcvarname
        except AttributeError:
            pass

    # If we get through the loop, then there is no qc mask variable
    return None


def simple_timezone_offset(utc_datetime, longitude, adjust_hours_only=False):
    estimated_offset_in_float = 12 * longitude / 180
    if adjust_hours_only:
        estimated_offset_hours = np.round(estimated_offset_in_float, 0)
        estimated_offset = pd.Series([
            pd.Timedelta(hours=x) for x in estimated_offset_hours
        ])
        adjusted_datetime = utc_datetime + estimated_offset
    else:
        estimated_offset_total_seconds = np.round(
            estimated_offset_in_float * 3600, 0
        )
        estimated_offset = np.array([
            dt.timedelta(days=0, seconds=estimated_seconds)
            for estimated_seconds in estimated_offset_total_seconds
        ])
        adjusted_datetime = utc_datetime + estimated_offset

    return adjusted_datetime
