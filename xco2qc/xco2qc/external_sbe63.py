# standard library
import datetime as dt
import pathlib

# 3rd party library imports
import netCDF4
import pandas as pd

# local imports
from xco2qc import core


class ImportExternalSBE63(core.MapCO2core):

    def __init__(self, inputfile, dst_dir, **kwargs):
        super().__init__(
            dst_dir=dst_dir, logger_name='import_external_sbe63', **kwargs
        )
        self.inputfile = pathlib.Path(inputfile)

        self.vardefs = core.vardefs.data_dict['external_sbe63']
        self.time_base = dt.datetime(1970, 1, 1)

    def run(self):
        df = pd.read_csv(
            self.inputfile,
            sep=r'\s+|,',
            names=['date', 'time', 'o2'],
            skiprows=[0],
            # parse_dates={'timestamp': ['date', 'time']},
            engine='python'
        )
        df['timestamp'] = pd.to_datetime(df['date'].astype(str) + ' ' + df['time'].astype(str))
        df = df.drop(columns=['date', 'time'])

        ncfile = self.dst_dir / core.EXTERNAL_SBE63_NCFILE
        self.logger.info(f'writing out to {ncfile}...')

        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            nc.createDimension(core.TIME, 0)

            vardef = self.vardefs[core.TIME]
            ncvar = nc.createVariable(
                core.TIME, vardef['datatype'],
                dimensions=('time',),
                fill_value=vardef['fill_value']
            )
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            timedelta = df['timestamp'] - self.time_base
            ncvar[:] = timedelta.dt.total_seconds()

            # We only have salinity-compensated O2 here.
            vardef = self.vardefs['o2']

            ncvar = nc.createVariable(
                'o2',
                vardef['datatype'],
                dimensions=('time',),
                fill_value=vardef['fill_value']
            )

            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            ncvar[:] = df['o2']

            # mark the data as having come externally, but still from the SAMI
            # data_source
            nc.data_source = 'external-sbe63'
