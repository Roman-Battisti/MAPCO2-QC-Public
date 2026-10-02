"""
This provides a mechanism for importing historical data.
"""

# standard library imports
import datetime as dt
import importlib.resources as ir
import itertools
import pathlib

# 3rd party imports
from erddapy import ERDDAP
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr
import yaml

# local imports
from xco2qc import core


class ImportHistorical(core.MapCO2core):
    """
    Attributes
    ----------
    inputfile : path or str or file-like
        the input CSV "file" for the salinity and temperature
    netcdf_path : path
        the directory where the netcdf files are located
    vardefs : dict
        has definitions for salinity and temperature
    site_id : str or None
        Provide this to override a bad site ID in the raw file.
    """

    def __init__(self, source, netcdf_path, site_id=None, **kwargs):
        """
        Parameters
        ----------
        source : path or str or file-like or None
            The input CSV "file" for the historical data.  If None, then we
            attempt to construct a source for PMEL erddap data.
        netcdf_path : path or str
            The output directory where the historical netcdf file will be
            created.
        site_id : str or None
            Provide this to override a bad site ID in the raw file.
        """
        super().__init__(
            dst_dir=netcdf_path, logger_name='historical', **kwargs
        )

        self.netcdf_path = pathlib.Path(netcdf_path)

        self.site_id = site_id
        self.inputfile = None
        self.url = None

        if isinstance(source, str):
            # turn a string into a path
            self.inputfile = pathlib.Path(source)
        else:
            # case of path or file-like object or maybe None
            self.inputfile = source

        # is there a saildrone file?
        self.saildrone_file = netcdf_path / core.SAILDRONE_NCFILE

        self.vardefs = core.vardefs.data_dict['historical']
        self.time_base = dt.datetime(1970, 1, 1)

    def run(self):

        self.logger.info(f"Starting at {dt.datetime.now()}")

        # Don't run if given a directory
        if (
            isinstance(self.inputfile, pathlib.Path)
            and self.inputfile.is_dir()
        ):
            self.logger.info("No historical data will be imported.")
            return

        if self.saildrone_file.exists():
            msg = (
                "A saildrone netCDF file was detected, so there is no "
                "historical data to retrieve."
            )
            self.logger.info(msg)
            return
        elif self.inputfile is None:
            # No text file was given, so retrieve from ERDDAP
            self.read_pmel_erddap()
        else:
            # Read a text file for historical data.
            self.read_local_data()

        self.logger.info(f"Finishing at {dt.datetime.now()}")

    def read_pmel_erddap(self):
        """
        We were instructed to read data from PMEL's erddap server.
        """

        # Get the site ID, use that to produce the URL for the PMEL
        # ERDDAP server.
        if self.site_id is None:
            ncfile = self.netcdf_path / core.CYCLE_HEADER_NCFILE
            with xr.open_dataset(ncfile) as ds:
                self.site_id = ds.site_id

        with ir.as_file(ir.files(core.data).joinpath('sites.yml')) as path:
            with path.open() as f:
                sites_metadata = yaml.safe_load(f)

        search_terms = sites_metadata[self.site_id]['erddap_search_term']

        e = ERDDAP(server="https://data.pmel.noaa.gov/pmel/erddap")
        url = e.get_search_url(search_for=search_terms, response="csv")

        self.logger.info(f'Reading data from {url}...')
        df = pd.read_csv(url)

        e.constraints = None
        e.protocol = 'tabledap'
        e.dataset_id = df.loc[
            df['Dataset ID'].str.startswith('pmel_co2_moorings'), 'Dataset ID'
        ].iloc[0]

        ds = e.to_xarray(decode_times=False)

        ncfile = self.netcdf_path / core.HISTORICAL_NCFILE
        self.logger.info(f"Saving to {ncfile}.")
        ds.to_netcdf(ncfile)

        # Need to append our special data_source attribute here.
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc.data_source = 'historical'

    def read_local_data(self):
        """
        We were given something on the local filesystem.
        """

        self.logger.info(f'parsing {self.inputfile}...')

        try:
            df = self.read_data()
        except UnicodeDecodeError as e:
            msg = (
                "An error was encountered trying to read {self.inputfile}.  "
                "Check that the file is a tab-delimited CSV file.  "
                "The original error was"
                "\n\n"
                f"{e}"
            )
            raise RuntimeError(msg)
        else:
            df = self.post_process(df)
            self.write_netcdf(df)

    def read_data(self):
        """
        Read the CSV file.
        """

        # first figure out how many header rows start off as a comment.
        f = open(self.inputfile)
        it = itertools.takewhile(lambda x: x.startswith('#'), f)
        skiprows = len(list(it))

        f.seek(0)

        # Ok, so we have generic data.
        # Reject anything that cannot be easily parsed.
        df = pd.read_csv(
            f,
            parse_dates=[0],
            skiprows=skiprows,
            sep=r'\t',
            engine='python',
        )

        # replace that first column name
        columns = df.columns[1:]
        columns = columns.insert(0, 'timestamp')
        df.columns = columns

        return df

    def read_pmel_historical(self, f, skiprows):
        """
        Attempt to read the file.

        Parameters
        ----------
        f : file object
            possibly opened CSV file handle
        skiprows : int
            number of rows to skip in the file header
        """

        names = [
            'time', 'SST', 'sss', 'pco2_sw', 'pco2_air', 'xco2_air',
            'ph_sw'
        ]
        df = pd.read_csv(
            f,
            names=names,
            parse_dates=['time'],
            skiprows=skiprows,
            engine='python',
            sep=r'\t'
        )

        return df

    def post_process(self, df):
        """
        Do any manipulations needed.
        """

        # remap to netCDF variable names
        mapper = {
            'datetime_utc': 'time',
            'datetime': 'time',
            'timestamp': 'time',
        }
        df = df.rename(mapper=mapper, axis='columns')

        return df

    def write_netcdf(self, df):
        """
        Write the dataframe to the historical netcdf file.  If the file already
        exists, the two timeseries must be meshed together.

        Parameters
        ----------
        df : pandas.Dataframe
            has historical data
        """

        ncfile = self.netcdf_path / core.HISTORICAL_NCFILE
        if ncfile.exists():
            df = df.set_index('time')
            self.assimilate_new_data(ncfile, df)
        else:
            self.write_initial_data(ncfile, df)

    def assimilate_new_data(self, ncfile, df1):

        self.logger.info(f'assimilating new data into {ncfile}...')

        with xr.open_dataset(ncfile) as ds:
            df2 = ds.to_dataframe()

            # merge the two dataframes
            df = df1.merge(df2, how='outer', left_index=True, right_index=True)

            df = df.reset_index()

        # rewrite any previously existing variables, and define and write any
        # new variables
        with netCDF4.Dataset(ncfile, mode='r+') as nc:

            timedelta = df['time'] - self.time_base
            nc['time'][:] = timedelta.dt.total_seconds()

            # define all the data variables
            for varname, vardef in self.vardefs.items():

                if varname not in df.columns:
                    continue

                if varname == 'time':
                    continue

                vardef = self.vardefs[varname]

                if varname in nc.variables:
                    # just rewrite the data if the variable already exists
                    nc.variables[varname][:] = df[varname]
                else:
                    # define AND write if the variable is new
                    ncvar = nc.createVariable(
                        varname,
                        vardef['datatype'],
                        dimensions=('time',),
                        fill_value=vardef['fill_value']
                    )

                    for attrname, attrvalue in vardef['attributes'].items():
                        setattr(ncvar, attrname, attrvalue)

                    ncvar[:] = df[varname]

    def write_initial_data(self, ncfile, df):
        """
        Create the netCDF file, write out the dataframe.
        """

        self.logger.info(f'writing out to {ncfile}...')

        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            # defining the time dimension is something we can only do once
            nc.createDimension(core.TIME, 0)

            vardef = self.vardefs['time']
            ncvar = nc.createVariable('time', np.int64,
                                      dimensions=('time',),
                                      fill_value=vardef['fill_value'])
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            timedelta = df['time'] - self.time_base
            ncvar[:] = timedelta.dt.total_seconds()

            # define all the other data variables
            for varname, vardef in self.vardefs.items():

                if varname not in df.columns:
                    continue

                if varname == 'time':
                    continue

                vardef = self.vardefs[varname]

                ncvar = nc.createVariable(
                    varname,
                    vardef['datatype'],
                    dimensions=('time',),
                    fill_value=vardef['fill_value']
                )

                for attrname, attrvalue in vardef['attributes'].items():
                    setattr(ncvar, attrname, attrvalue)

                ncvar[:] = df[varname]

            # must write out some global attributes
            nc.data_source = 'historical'
