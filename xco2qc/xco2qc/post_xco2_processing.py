"""
Look at Parse_2.bas line 115 to find how to do xCO2 dry
"""
# Standard library imports
from contextlib import ExitStack

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# Local imports
from .netcdf import NetCDFWriter
from . import core
from . import science_algorithms as sa


LICOR_VERSION_820_V1 = 1
LICOR_VERSION_820_V2 = 2
LICOR_VERSION_830_V1 = 3


class XCO2NetCDFWriter(NetCDFWriter):
    """
    Attributes
    ----------
    time : xarray
    """
    def __init__(self, src_ncfile, verbosity=None):
        super().__init__(src_ncfile=src_ncfile, verbosity=verbosity)

        self.nc_variable_defs = core.vardefs.data_dict['licor']

        # Ok, time has been written to be now, so we can use a higher interface
        # to manipulate time.
        ds = xr.open_dataset(self.src_ncfile)
        self.time = ds[core.TIME]


class LicorXCO2Processor(XCO2NetCDFWriter):

    def __init__(
        self, src_ncfile, rh=None, licor_version=LICOR_VERSION_820_V1,
        calculate_post_xco2=True,
        config=None,
        verbosity=None
    ):
        super().__init__(src_ncfile, verbosity=verbosity)

        self.licor_version = licor_version
        self.calculate_post_xco2 = calculate_post_xco2
        self.config = config
        self.rh = rh

        with xr.open_dataset(self.src_ncfile) as ds:
            self.pump_mode = ds.pump_mode

    def run(self):

        # This basically implements the postCalcxCO2UI VBA
        self.calculate_vapor_pressure()

        if not self.calculate_post_xco2:
            msg = f"Skipping post xco2 calculation on {self.pump_mode} file."
            self.logger.warning(msg)
            return

        self.recalculate_wet_dry_xco2()

    def calculate_vapor_pressure(self):

        if self.pump_mode not in ['air pump off', 'equil pump off']:
            msg = (
                f"Skipping vapor pressure calculation on "
                f"{self.pump_mode.upper()} "
            )
            self.logger.warning(msg)
            return

        with xr.open_dataset(self.src_ncfile) as ds:
            temp_rh = ds['rh_temp'].to_pandas()
            rh_equil = ds['rh'].to_pandas()
            p_kPa = ds['pressure'].to_pandas()

        # Get RH from span-pump-off file, reindex it to the current file
        ncfile = self.src_ncfile.parents[0] / core.licor.SPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            rh = ds['rh'].to_pandas()
            rh = rh.reindex(temp_rh.index, method='nearest')

        vapor_pressure = sa.calculate_vapor_pressure(temp_rh, rh_equil, rh)
        data = vapor_pressure * 1000 / p_kPa

        msg = f'Writing vapor_pressure to {self.src_ncfile}'
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.src_ncfile, mode='r+')
            )

            self.define_netcdf_variable('vapor_pressure')
            self.write_netcdf_variable('vapor_pressure', data)

    def recalculate_wet_dry_xco2(self):
        """
        It appears this calculation is only done for two pump modes.
        """
        if self.pump_mode not in ['air pump off', 'equil pump off']:
            msg = f"Skipping post xco2 calculation on {self.pump_mode} file."
            self.logger.warning(msg)
            return

        comment = (
            "Average wet xCO2 measurements are post-calibrated using a simple "
            "linear regression between original averaged measurements and "
            "span coefficients, a method similar to the post-cal established "
            "by the underway pCO2 community as described here:  Feely, R.A., "
            "R. Wanninkhof, H.B. Milburn, C.E. Cosca, M. stapp, and P.P. "
            "Murphy, A new automated underway system for making high "
            "precision pCO2 measurements onboard research ships, Analytica "
            "Chim.  Acta, 377, 185-191, 1998."
        )
        self.logger.info(comment)

        # xCO2 @RH:  xCO2 @RH Recalculated with new span coeff
        # xCO2 Dry Recalculated with new span coeff using span RH of last good
        # span
        self.recalc_xco2_wet()
        self.recalc_xco2_dry()

    def recalc_xco2_dry(self):

        with xr.open_dataset(self.src_ncfile) as ds:
            rh_temp = ds['rh_temp'].to_pandas()
            rh_equil = ds['rh'].to_pandas()
            temp = ds['temperature'].to_pandas()
            xco2_wet = ds['post_xco2_wet'].to_pandas()
            press = ds['pressure'].to_pandas()

        rh = self.rh.reindex(press.index, method='nearest')
        xco2_dry = sa.calc_dry_xco2(
            rh_temp, rh_equil, rh, temp, xco2_wet, press
        )

        msg = f'Writing post_xco2_dry to {self.src_ncfile}'
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.src_ncfile, mode='r+')
            )

            self.define_netcdf_variable('post_xco2_dry')
            self.write_netcdf_variable('post_xco2_dry', xco2_dry)

            # Just copy over the same QC for the pre xco2.
            self.write_netcdf_variable(
                'post_xco2_dry_qc', self.dst_nc['xco2_dry_qc'][:]
            )

    def recalc_xco2_wet(self):
        """
        """
        ncfile = self.src_ncfile.parents[0] / core.licor.SPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            sc = ds['updated_span_coefficient'].to_pandas()

        # Get the span2 coefficients from ZPON.
        ncfile = self.src_ncfile.parents[0] / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            sc2 = ds['span2_coefficient'].to_pandas()
            zc = ds['zero_coefficient'].to_pandas()

        # adjust zero and span indicies up 10 minutes. This accounts for 30 minute cycles, where APOFF and EPOFF are closer to the next measurement cycle than the current.
        sc.index += pd.Timedelta(minutes=10)
        sc2.index += pd.Timedelta(minutes=10)
        zc.index += pd.Timedelta(minutes=10)
        
        # Calculate both v1 and v2 post xco2 wet, but we only bless one of
        # them.
        if self.licor_version == LICOR_VERSION_830_V1:
            xco2, qc = self.process_post_xco2_wet_licor_v830(zc, sc, sc2)
        else:
            xco2_v1, qc_v1 = self.process_post_xco2_wet_licor_v1(zc, sc)
            xco2_v2, qc_v2 = self.process_post_xco2_wet_licor_v2(zc, sc, sc2)

            if self.licor_version == LICOR_VERSION_820_V1:
                xco2 = xco2_v1
                qc = qc_v1
            else:
                xco2 = xco2_v2
                qc = qc_v2

        msg = f'Writing post_xco2_wet to {self.src_ncfile}'
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.src_ncfile, mode='r+')
            )

            self.define_netcdf_variable('post_xco2_wet')
            self.write_netcdf_variable('post_xco2_wet', xco2, qc)

            self.dst_nc['post_xco2_wet'].licor_version = self.licor_version

    def process_post_xco2_wet_licor_v830(self, zc, s0, s1):
        """
        Parameters
        -----------
        s0, s1 : ndarray
            Span and span2 coefficients
        """
        with xr.open_dataset(self.src_ncfile) as ds:
            rawref = ds['raw_reference'].to_pandas()
            rawsam = ds['raw_sample'].to_pandas()
            pressure = ds['pressure'].to_pandas()
            temperature = ds['temperature'].to_pandas()

            # Just copy over the same QC for the pre xco2.
            qc = ds['xco2_wet_qc'].to_pandas()

        zc = zc.reindex(rawref.index, method='nearest')
        s0 = s0.reindex(rawref.index, method='nearest')
        s1 = s1.reindex(rawref.index, method='nearest')

        v830 = sa.Licorv830(self.config)
        xco2 = v830.calc_xco2(
            zc, s0, s1, rawsam, rawref, pressure, temperature
        )

        return xco2, qc

    def process_post_xco2_wet_licor_v2(self, zc, s0, s1):
        """
        Parameters
        -----------
        s0, s1 : ndarray
            Span and span2 coefficients
        """
        with xr.open_dataset(self.src_ncfile) as ds:
            rawref = ds['raw_reference'].to_pandas()
            rawsam = ds['raw_sample'].to_pandas()
            pressure = ds['pressure'].to_pandas()
            temperature = ds['temperature'].to_pandas()

        s0 = s0.reindex(temperature.index, method='nearest')
        s1 = s1.reindex(temperature.index, method='nearest')
        zc = zc.reindex(pressure.index, method='nearest')

        xco2 = sa.calc_xco2_licor_v2(
            temperature, pressure, rawref, rawsam, zc, s0, s1
        )

        msg = f'Writing post_xco2_wet_v2 to {self.src_ncfile}'
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.src_ncfile, mode='r+')
            )

            self.define_netcdf_variable('post_xco2_wet_v2')
            self.write_netcdf_variable('post_xco2_wet_v2', xco2)

            # Just copy over the same QC for the pre xco2.
            qc = self.dst_nc['xco2_wet_qc'][:]
            self.write_netcdf_variable('post_xco2_wet_v2_qc', qc)

        return xco2, qc

    def process_post_xco2_wet_licor_v1(self, zc, sc):
        """
        Parameters
        ----------
        xco2_name : str
            Name of netCDF variable that will contain the xCO2 data that is to
            be computed.
        sc : ndarray
            These are the span coefficients updated by the licor
            pressure / span regression calculation.
        """

        with xr.open_dataset(self.src_ncfile) as ds:
            rawref = ds['raw_reference'].to_pandas()
            rawsam = ds['raw_sample'].to_pandas()
            pressure = ds['pressure'].to_pandas()
            temperature = ds['temperature'].to_pandas()

        sc = sc.reindex(pressure.index, method='nearest')
        zc = zc.reindex(pressure.index, method='nearest')

        calc_xco2 = sa.calc_xco2(temperature, pressure, rawref, rawsam, zc, sc)

        msg = f'Writing post_xco2_wet_v1 to {self.src_ncfile}'
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.src_ncfile, mode='r+')
            )

            self.define_netcdf_variable('post_xco2_wet_v1')
            self.write_netcdf_variable('post_xco2_wet_v1', calc_xco2)

            # Just copy over the same QC for the pre xco2.
            qc = self.dst_nc['xco2_wet_qc'][:]
            self.write_netcdf_variable('post_xco2_wet_v1_qc', qc)

        return calc_xco2, qc


class PostXCO2Calc(core.MapCO2core):
    """
    Calculate post xCO2, wet and dry.

    Attributes
    ----------
    src_dir : pathlib paths
        Paths to the reduced source netCDF files (assumed to all be in the
        same directory).  We write back to these files.
    kwargs : dict
        Keyword arguments to be passed on to the various reducing processors.
    calculate_post_xco2 : bool
        It may seem silly, but the GUI will tell us whether or not to actually
        calculate post xco2.
    licor_version : int
        Either LICOR_VERSION_820_V1, LICOR_VERSION_820_V2, LICOR_VERSION_830_V1
    """
    def __init__(
        self, src_dir, verbosity=None, calculate_post_xco2=True,
        licor_version='820 v1'
    ):
        super().__init__(
            src_dir=src_dir, verbosity=verbosity, logger_name='post-xco2'
        )

        self.calculate_post_xco2 = calculate_post_xco2

        if licor_version == '820 v1':
            self.licor_version = LICOR_VERSION_820_V1
        elif licor_version == '820 v2':
            self.licor_version = LICOR_VERSION_820_V2
        elif licor_version == '830 v1':
            self.licor_version = LICOR_VERSION_830_V1
        else:
            raise RuntimeError(f"Unknown licor version '{licor_version}'")

    def run(self):
        """
        Run the XCO2 processing.
        """
        self.logger.info('Starting post xCO2 calculations...')

        # is the platform "saildrone"?  If so, override any value for the
        # licor version that was given.
        ncfile = self.src_dir / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            if hasattr(nc, 'platform') and nc.platform == 'saildrone':
                self.licor_version = LICOR_VERSION_830_V1
                msg = (
                    "The platform is saildrone, so we are overriding the "
                    "existing licor version, using 830 v1."
                )
                self.logger.info(msg)

        rh = self.determine_usable_rh()

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
                    src_ncfile,
                    rh=rh,
                    licor_version=self.licor_version,
                    calculate_post_xco2=self.calculate_post_xco2,
                    config=self.config,
                    verbosity=self.verbosity
                ) as p:
                    p.run()

        self.logger.info('Finished with xCO2 calculations...')

    def determine_usable_rh(self):
        """
        If loss of span occured, use the average RH.  Otherwise use RH from
        SPOFF.
        """
        filename = self.src_dir / core.licor.SPOFF_NCFILE
        with xr.open_dataset(filename) as ds:
            rh = ds['rh'].to_pandas()
            idx = rh.index

        filename = self.src_dir / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(filename) as ds:
            span_flag = ds['span_flag'].to_pandas()

            # reindex it, make sure we have the same length
            span_flag = span_flag.reindex(rh.index, method='nearest')

        # average the RH where the span flag is zero.
        usable_rh = np.where(span_flag == 255, np.nan, rh)
        avg_rh = np.nanmean(usable_rh)

        # Now substitute the avg rh in to RH where loss of span occured.
        n = (span_flag > 0).sum()
        if n > 0:
            msg = (
                f"Substituting avg RH = {avg_rh:.2} in {n} places due "
                "to loss of span."
            )
            self.logger.warning(msg)

            if avg_rh < 5 or avg_rh > 100:
                msg = f'RH average {avg_rh} is out of range.'
                self.logger.warning(msg)

        rh = np.where(span_flag, avg_rh, rh)

        return pd.Series(rh, index=idx)
