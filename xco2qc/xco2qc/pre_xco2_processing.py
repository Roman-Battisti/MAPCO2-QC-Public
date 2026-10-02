"""
Produce pCO2 and pre xCO2 (dry)
"""
# Standard library imports
from contextlib import ExitStack
import datetime as dt

# 3rd party library imports
import netCDF4
import numpy as np
import xarray as xr

# Local imports
from .netcdf import NetCDFWriter
from . import core


class XCO2NetCDFWriter(NetCDFWriter):
    """
    Attributes
    ----------
    time : xarray
    """
    def __init__(self, src_ncfile, verbosity=None):
        super().__init__(src_ncfile=src_ncfile, verbosity=verbosity)

        self.nc_variable_defs = core.vardefs.data_dict['licor']


class LicorXCO2Processor(XCO2NetCDFWriter):

    def __init__(self, src_ncfile, verbosity=None):
        super().__init__(src_ncfile, verbosity=verbosity)

        # Need SPOFF rh for all licor files, so get it just once.
        ncfile = self.src_ncfile.parents[0] / core.licor.SPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            self.rh_spoff = ds['rh'].to_pandas()

    def run(self):

        self.logger.info(f"Starting at {dt.datetime.now()}.")

        # xCO2 dry are calculated for every pump mode (i.e. every
        # licor netCDF file).
        self.process_xco2_dry()

        self.logger.info(f"Ending at {dt.datetime.now()}.")

    def process_pco2(self):
        """
        Calculate partial pressure of carbon dioxide.
        """

        pressure = self.dst_nc['pressure'][:]
        xco2 = self.dst_nc['xco2_wet'][:]
        pco2 = pressure / 101.325 * xco2

        msg = f'Writing pco2 to {self.dst_ncfile}'
        self.logger.info(msg)

        self.define_netcdf_variable('pco2')
        self.write_netcdf_variable('pco2', pco2)

        self.dst_nc.sync()

    def process_xco2_dry(self):

        with xr.open_dataset(self.dst_ncfile) as ds:
            rh_temp = ds['rh_temp'].to_pandas()
            pressure = ds['pressure'].to_pandas()
            rh = ds['rh'].to_pandas()
            xco2_wet = ds['xco2_wet'].to_pandas()

            # reindex rh_spoff to the current file
            rh_spoff = self.rh_spoff.reindex(rh_temp.index, method='nearest')

        saturation_vapor_pressure = (
            0.61365 * np.exp((17.502 * rh_temp) / (240.97 + rh_temp))
        )
        vapor_pressure_licor = (
            (rh - rh_spoff) * saturation_vapor_pressure / 100
        )
        xco2_dry = xco2_wet / ((pressure - vapor_pressure_licor) / pressure)

        msg = f'Writing xco2_dry to {self.dst_ncfile}'
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.define_netcdf_variable('xco2_dry')
            self.write_netcdf_variable('xco2_dry', xco2_dry)

            # Assume the quality of the xco2 dry is the same as the
            # wet for now, which means that the only flags that could be
            # present would be GOOD or MISSING.  The QC module will fill
            # in more detail.
            qc = self.dst_nc['xco2_wet_qc'][:]
            self.write_netcdf_variable('xco2_dry_qc', qc)


class PreXCO2Calc(core.MapCO2core):
    """
    Compute pCO2 and pre xCO2 (dry).

    Attributes
    ----------
    src_dir : pathlib paths
        Paths to the reduced source netCDF files (assumed to all be in the
        same directory).  We write back to these files.
    kwargs : dict
        Keyword arguments to be passed on to the various reducing processors.
    """
    def __init__(self, src_dir, verbosity=None):
        super().__init__(
            src_dir=src_dir, verbosity=verbosity, logger_name='pre-xco2'
        )

    def run(self):
        """
        Run the XCO2 processing.
        """
        self.logger.info(f'Starting at {dt.datetime.now()}.')

        # process in reverse alphabetical order to ensure that SPOFF is
        # available to EPOFF and APOFF.  Revise this later.
        g = self.src_dir.glob('*.nc')
        for src_ncfile in sorted(list(g), reverse=True):

            # Determine which reducer to use
            with netCDF4.Dataset(src_ncfile) as src_nc:
                data_source = src_nc.data_source

            if data_source == 'LICOR':

                self.logger.info(f"Processing xco2 in {src_ncfile}")

                with LicorXCO2Processor(
                    src_ncfile, verbosity=self.verbosity
                ) as p:
                    p.run()

        self.logger.info(f'Finishing at {dt.datetime.now()}.')
