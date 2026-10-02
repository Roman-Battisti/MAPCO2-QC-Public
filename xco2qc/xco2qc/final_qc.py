"""
Update socat quality flags in a netCDF file according to a list of vertices
defining a region and given a new socat qc value.
"""
# standard library imports
import pathlib

# 3rd party library imports
import matplotlib.dates as mdates
from matplotlib.path import Path
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from . import core


class XCO2FinalQC(core.MapCO2core):
    """
    Performs final update of socat QC variables.

    Attributes
    ----------
    ncfile : path or str
        Path to netCDF file where we perform the qc updates.
    primary_var : str
        Name of netCDF variable whose associated SOCAT QC will be updated.
    region : list
        list of points defining a region.  All points within this region will
        be set to the new qc value.
    new_socat_qc_value : int
        Set the QC points within the region to this value.
    user_comment : str
        This might be a specific reason for the new_socat_qc_value.  It will be
        logged into a csv file.
    qflog : path
        Save the user comments to this CSV file.
    """
    def __init__(
        self, ncfile, primary_var, region, new_socat_qc_value, user_comment="",
        qflog=None, logger=None
    ):
        """
        """
        self.ncfile = pathlib.Path(ncfile)
        self.primary_var = primary_var
        self.region = region
        self.new_socat_qc_value = new_socat_qc_value
        self.user_comment = user_comment
        self.logger = logger

        try:
            self.qflog = pathlib.Path(qflog)
        except TypeError:
            self.qflog = None

    def run(self):

        path = Path(self.region)

        with xr.open_dataset(self.ncfile) as ds:
            ds.load()
            s = ds[self.primary_var].to_pandas()

        # convert the time data into matlab dates.
        x = mdates.date2num(s.index)
        y = s.values

        # find the points that fall within the polygon
        data = np.array(list(zip(x, y)))
        idx = np.nonzero(path.contains_points(data))[0]

        self.update_primary(idx, s.index[idx])

    def update_non_socat_qc_variable(
        self, nc, qc_var, idx, flag=core.quality.MANUALLY_FLAGGED_XCO2
    ):
        """
        Update qc variables which are not socat.

        Parameters
        ----------
        nc : netCDF file handle
        qc_var : str
            netCDF variable name
        idx : array
            Indices where socat QC was set.
        flag : int
            This is the flag to set.
        """
        try:
            qc = nc[qc_var][idx]
        except IndexError:
            # the variable is not present.
            # self.logger.warn(f"{qc_var} not present.")
            return
        if self.new_socat_qc_value == core.quality.SOCAT_GOOD:
            # remove the manually flagged data
            qc = self.clear_flag(qc, flag)

            # It's not quite right to reset the qc to GOOD, as the data
            # might not have been GOOD to begin with.  If all flags
            # have been unset, only then can we set the QC back to
            # GOOD.
            # qc = np.where(qc == 0, core.quality.GOOD, qc)
            
            # not sure why the above reasoning was chosen, since a manual flag should override every other flag.
            # currently, if the user tries to unflag a spike flag SST/SSS, the value will not unflag because of the above logic.
            qc = core.quality.GOOD
            
        else:
            # unset the good bit and set it to be manually flagged.
            qc = self.clear_flag(qc, core.quality.GOOD)
            qc = np.bitwise_or(qc, flag)

        nc[qc_var][idx] = qc

    def append_user_comment(self, time_index):
        """

        """
        if self.qflog is None:
            return

        # construct the new data from the current run
        uc = [self.user_comment] * len(time_index)
        pvar = [self.primary_var] * len(time_index)
        data = {'Parameter': pvar, 'Reason': uc}
        dfnew = pd.DataFrame(data=data, index=time_index)

        dfnew.index.name = 'Date/Time'

        # If the CSV file already exists, read in the existing "old" data,
        # combine with the new data, and remove duplicates
        if self.qflog.exists():

            dfold = pd.read_csv(
                self.qflog,
                index_col='Date/Time', parse_dates=['Date/Time']
            )

            df = pd.concat([dfold, dfnew], axis='index')
            df = df.reset_index()
            df = df.drop_duplicates(
                subset=['Date/Time', 'Parameter'], keep='last'
            )
            df = df.set_index('Date/Time').sort_index()

        else:

            df = dfnew

        df.to_csv(self.qflog)

    def update_primary(self, idx, time):
        """
        Update the SOCAT quality variable for the given indices

        Parameters
        ----------
        idx : array
            0-based indices where the SOCAT quality variable is to be updated
        time : pandas.DatetimeIndex
            time values corresponding to idx
        """
        with netCDF4.Dataset(self.ncfile, 'r+') as nc:
            # Get the QC variable.
            ancillary_variables = nc[self.primary_var].ancillary_variables
            try:
                bitmask_qc_var, socat_qc_var = ancillary_variables.split()
            except ValueError:
                # There's no socat QC var.
                bitmask_qc_var = ancillary_variables
            else:
                # update the socat quality variable in the netCDF file
                nc[socat_qc_var][idx] = self.new_socat_qc_value
            finally:
                # Update the QF log
                self.append_user_comment(time)

                # update the bitmask QC regardless of any socat qc
                self.update_non_socat_qc_variable(
                    nc, bitmask_qc_var, idx, flag=core.quality.MANUALLY_FLAGGED
                )

            # update associated quality variables
            if self.primary_var == 'xCO2_air':
                self.update_non_socat_qc_variable(nc, 'fCO2_air_qc', idx)
                self.update_non_socat_qc_variable(nc, 'pCO2_air_qc', idx)
            elif self.primary_var == 'xCO2_sw':
                self.update_non_socat_qc_variable(nc, 'fCO2_sw_qc', idx)
                self.update_non_socat_qc_variable(nc, 'pCO2_sw_qc', idx)
