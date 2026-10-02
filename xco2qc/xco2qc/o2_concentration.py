"""
Calculate O2 concentration from maxtec o2
"""

# Standard library imports

# 3rd party library imports
import numpy as np
import netCDF4
import xarray as xr

# local imports
from . import core
from xco2qc.science_algorithms import percentO2_to_O2conc


class CalcO2Concentration(core.MapCO2core):
    """
    Add dissolved oxygen to the licor files.

    Attributes
    ----------
    src_dir, dst_dir : pathlib paths
        Paths to the raw source netCDF files (assumed to all be in the
        same directory) and the destination directory where the reduced files
        will be written.
    """
    def __init__(self, src_dir, verbosity=None):
        super().__init__(
            src_dir=src_dir, verbosity=verbosity,
            logger_name='o2-concentration'
        )

        self.nc_variable_defs = core.vardefs.data_dict['licor']

    def run(self):

        self.logger.info("Calculating O2 concentration from maxtec o2 .")

        for stem in [core.licor.EPON_NCFILE, core.licor.EPOFF_NCFILE]:

            ncfile = self.src_dir / stem
            self.calculate_o2_conc(ncfile)

    def calculate_o2_conc(self, equilibrator_ncfile):
        msg = f"Calculating O2 concentration for {equilibrator_ncfile}"
        self.logger.info(msg)

        # Gather all the inputs
        with xr.open_dataset(equilibrator_ncfile) as ds:
            o2 = ds.load().to_dataframe()['o2']

        mapco2_met_ncfile = self.src_dir / core.MET_NCFILE
        external_met_ncfile = self.src_dir / core.EXTERNAL_MET_NCFILE
        if mapco2_met_ncfile.exists() and external_met_ncfile.exists():
            ncfile = external_met_ncfile
        elif mapco2_met_ncfile.exists() and not external_met_ncfile.exists():
            ncfile = mapco2_met_ncfile
        elif not mapco2_met_ncfile.exists() and external_met_ncfile.exists():
            ncfile = external_met_ncfile
        else:
            msg = "No met data available, cannot compute O2 concentration"
            self.logger.warning(msg)
            return

        with xr.open_dataset(ncfile) as ds:
            df = ds.load().to_dataframe()
            sss = df['SSS']
            sst = df['SST']

        ncfile = self.src_dir / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            df = ds.load().to_dataframe()
            lat = df['latitude']
            lon = df['longitude']

        # reindex all the timeseries values to that of o2
        sss = sss.reindex(o2.index, method='nearest').values
        sst = sst.reindex(o2.index, method='nearest').values
        lat = lat.reindex(o2.index, method='nearest').values
        lon = lon.reindex(o2.index, method='nearest').values
        press = np.full(o2.shape, 0.5)

        # don't calculate this in percent!
        o2 = o2 / 100

        dissolved_oxygen = percentO2_to_O2conc(
            o2.values, sss, sst, lat, lon, press
        )

        with netCDF4.Dataset(equilibrator_ncfile, mode='r+') as nc:
            vardef = core.vardefs.data_dict['licor']['dissolved_oxygen']

            ncvar = nc.createVariable(
                'dissolved_oxygen', vardef['datatype'],
                dimensions=('time',),
                fill_value=vardef['fill_value']
            )

            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            ncvar[:] = dissolved_oxygen

            # create the QC variable as well.
            vardef = core.vardefs.data_dict['licor']['dissolved_oxygen_qc']

            ncvar = nc.createVariable(
                'dissolved_oxygen_qc', vardef['datatype'],
                dimensions=('time',),
                fill_value=vardef['fill_value']
            )

            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            # force the QC to all be good instead of uninitialized.
            data = np.full(
                ncvar.shape, core.quality.GOOD, dtype=vardef['datatype']
            )

            ncvar[:] = data
