"""
This module is responsible for splicing PH data into the SOCAT CSV file
"""
# standard library imports
import pathlib

# 3rd party library
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core


class PHSocatWriter(core.MapCO2core):
    """
    Attributes
    ----------
    df : pandas.Dataframe
        corresponding to the merge netCDF file
    merge_ncfile : path or str
        the netCDF file merged together out of disparate sources, will be the
        final authoritative product
    csvfile : path
        path to output CSV file for submission to SOCAT
    """
    def __init__(
        self, *, ncfile=None, csvfile=None, verbosity=None,
    ):
        super().__init__(verbosity=verbosity, logger_name='ph-socat')
        self.merge_ncfile = pathlib.Path(ncfile)
        self.csvfile = pathlib.Path(csvfile)

    def run(self):

        # Now that the netCDF writing is done, read the pH from the merge
        # netCDF file and update the socat CSV file with it.
        with xr.open_dataset(self.merge_ncfile) as self.ds:
            self.update_socat_csv()

    def update_socat_csv(self):
        """
        Write a CSV file that can be delivered to SOCAT.
        """
        self.logger.info('Merging PH into SOCAT CSV file...')

        # Get the header for the CSV file, we need to keep that.
        with open(self.csvfile) as f:
            header = ''.join([f.readline() for _ in range(4)])

        df = pd.read_csv(self.csvfile, skiprows=4)
        ph = self.ds['pH_sw'].to_series()
        ph_qc = self.ds['pH_sw_socat_qc'].to_series().astype(np.uint8)

        # we should not have to reindex
        df[core.socat.PH] = ph.values
        df[core.socat.PH_QC] = ph_qc.values

        # and write the content back to the csv file, preserving the header
        with open(self.csvfile, 'wt') as f:

            f.write(header)

            # write a portion of xarray dataset to the rest of the CSV file
            df.to_csv(f, index=False, lineterminator='\n')
