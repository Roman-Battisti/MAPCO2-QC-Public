"""
This module converts the mapco2 netcdf file to CSV.
"""

# 3rd party library imports
import xarray as xr

# local imports
from xco2qc import core


class ExportToCSV(core.MapCO2core):

    def __init__(self, ncfile, csvfile):
        """
        Parameters
        ----------
        ncfile, csvfile : pathlib.Path
            Paths to the input netCDF file, output CSV file.
        """
        self.ncfile = ncfile
        self.csvfile = csvfile

    def run(self):

        with xr.open_dataset(self.ncfile) as ds:
            df = ds.to_dataframe()
            df.to_csv(self.csvfile)
