# standard library imports
from contextlib import ExitStack
import pathlib

# 3rd party libraries
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# Local imports
from . import core
from .netcdf import NetCDFWriter
from .science_algorithms import calc_ph_pco2sys, compute_ta


class MergeNetCDFWriter(NetCDFWriter):

    def __init__(self, ncfile):
        """
        Parameters
        ----------
        ncfile : path or str
            Write to this file.
        """
        super().__init__(ncfile)

        vardefs = core.vardefs.data_dict['merge']

        self.nc_variable_defs = vardefs


class XCO2Merge(core.MapCO2core):
    """
    Attributes
    ----------
    merge_ncfile : path
        Path to the merge netCDF file.
    epoff_ncfile, apoff_ncfile, spoff_ncfile, sbe16 : path or str
        Paths to EPOFF, APOFF, SPOFF, and SBE16 netCDF files
    """
    def __init__(self, src_dir, merge_ncfile, verbosity=None, region=None):
        """
        src_dir : path
            Path to reduced level netCDF files that are to be merged.
        merge_ncfile : path or str
            Data is merged into this file.
        region : int or None
            Region where pco2sys calculation comes into play.
        """
        self.merge_ncfile = pathlib.Path(merge_ncfile)
        super().__init__(
            src_dir=src_dir, dst_dir=self.merge_ncfile.parents[0],
            verbosity=verbosity, logger_name='merge',
        )

        self.region = region

        # Make sure that the merge netCDF file directory exists.
        if not self.merge_ncfile.parents[0].exists():
            self.merge_ncfile.parents[0].mkdir(parents=True)

        # But if the merge netCDF file itself exists, delete it.
        # That way we can run again and again without having to manually delete
        # it.
        if self.merge_ncfile.exists():
            self.merge_ncfile.unlink()

    def run(self):

        self.logger.info('Starting merge process...')
        self.logger.info(f'Merging to {self.merge_ncfile}...')

        self.setup_merge_file()

        self.copy_xco2_from_apoff_epoff()
        self.update_xco2_quality_for_xco2_inputs()
        self.copy_gps_variables()
        self.copy_sstc_variables()
        self.calculate_pco2_from_apoff_epoff()
        self.copy_ph()
        self.copy_temperature_from_licor()
        self.copy_vapor_pressures()
        self.calculate_o2_ratio()
        self.calculate_licor_pressure()
        self.calculate_fugacity()
        self.update_pco2_quality_for_sstc()
        self.update_xco2_quality_for_pressure()
        self.copy_chl_and_ntu()
        self.copy_dissolved_oxygen()
        self.calculate_ph_pco2sys()
        self.record_loss_of_span()

        self.logger.info('Finished merge process...')

    def setup_merge_file(self):
        """
        Create the merge file skeleton and setup the dimensions.  Copy over
        global variables from the cycle header file.
        """

        ncfile = self.src_dir / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            global_atts = ds.attrs

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='w')
                )

                ncw.define_dimensions()
                ncw.define_coordinate_variables()

                with netCDF4.Dataset(self.epoff_ncfile) as nc:
                    time = nc[core.TIME][:]
                ncw.dst_nc[core.TIME][:] = time

                # Copy over the attributes.
                for attrname, attrvalue in global_atts.items():
                    setattr(ncw.dst_nc, attrname, attrvalue)

    def calculate_ph_pco2sys(self):
        """
        """
        # if no met data, do not continue
        if (
            not self.external_met_ncfile.exists()
            and not self.met_ncfile.exists()
        ):
            self.logger.info(
                "No MET netCDF file found, not calculating pH (pco2sys)."
            )
            return

        if self.region is None:
            self.logger.info(
                "No region specified, not calculating pH via pco2sys."
            )
            return

        msg = (
            'Calculating pH via pco2sys for region '
            f'{core.pco2sys_region_labels[self.region]}'
        )
        self.logger.info(msg)

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                ncw.define_netcdf_variable('pH_pco2sys')

                SST = ncw.dst_nc['SST'][:]
                SSS = ncw.dst_nc['SSS'][:]
                pco2 = ncw.dst_nc['pCO2_sw'][:]
                # In the *very* rare instance pco2 is somehow negative, set values to float('nan')
                index = pco2 < 0
                pco2[index] = float('nan')
                
                longitude = ncw.dst_nc['longitude'][:]

                alk = compute_ta(SSS, SST, longitude, region=self.region)
                ph = calc_ph_pco2sys(alk, SSS, SST, pco2)
                ncw.write_netcdf_variable('pH_pco2sys', ph)

    def calculate_fugacity(self):
        """
        """
        try:
            df = self.recalculate_fco2()
        except core.MissingParametersError as e:
            self.logger.warning(e)
            return

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                ncw.define_netcdf_variable('fCO2_air')
                ncw.dst_nc['fCO2_air'][:] = df['fco2_air']
                ncw.dst_nc['fCO2_air_qc'][:] = df['fco2_air_qc']

                ncw.define_netcdf_variable('fCO2_sw')
                ncw.dst_nc['fCO2_sw'][:] = df['fco2_sw']
                ncw.dst_nc['fCO2_sw_qc'][:] = df['fco2_sw_qc']

    def update_pco2_quality_for_sstc(self):
        """
        Check for MISSING_DATA, OUT_OF_RANGE and SPIKE_DETECTED.

        Perform this check here rather than in the QC module because here the
        SST and salinity data are together with the pco2.
        """

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                # if there was no met data, then there is nothing to do here.
                if 'SSS_qc' not in ncw.dst_nc.variables.keys():
                    return
                if 'SST_qc' not in ncw.dst_nc.variables.keys():
                    return

                for pco2_qc_var in ['pCO2_air_qc', 'pCO2_sw_qc']:

                    qc = ncw.dst_nc[pco2_qc_var][:]

                    for sstc_qc_var in ['SST_qc', 'SSS_qc']:
                        sstc_qc = ncw.dst_nc[sstc_qc_var][:]

                        qc = np.where(
                            np.bitwise_and(
                                sstc_qc,
                                core.quality.MISSING_DATA
                            ) > 1,
                            core.quality.BAD_SSTC,
                            qc
                        )

                        qc = np.where(
                            np.bitwise_and(
                                sstc_qc,
                                core.quality.OUT_OF_RANGE
                            ) > 1,
                            core.quality.BAD_SSTC,
                            qc
                        )

                        qc = np.where(
                            np.bitwise_and(
                                sstc_qc,
                                core.quality.SPIKE_DETECTED
                            ) > 1,
                            core.quality.BAD_SSTC,
                            qc
                        )

                    ncw.dst_nc[pco2_qc_var][:] = qc

    def update_xco2_quality_for_xco2_inputs(self):
        """
        Go through all the xCO2 variables in the licor files and transfer some
        of the quality flags to the merge file.
        """
        self._update_for_out_of_span_range()
        self._update_for_trend()

    def _update_for_trend(self):

        # Transfer the TREND and RAW STDDEV OUT OF RANGE flags
        for src_ncfile in [
            self.src_dir / core.licor.APOFF_NCFILE,
            self.src_dir / core.licor.EPOFF_NCFILE,
        ]:
            with xr.open_dataset(src_ncfile) as ds:
                src_qc = ds['xco2_wet_qc'].to_pandas().astype(np.uint32)

            for varname in ['xco2_air_wet_qc', 'xco2_sw_wet_qc']:

                with xr.open_dataset(self.merge_ncfile) as ds:
                    dst_qc = ds[varname].to_pandas().astype(np.uint32)

                src_qc = src_qc.reindex(dst_qc.index, method='nearest')

                # Just doing a bitwise_or isn't quite right here.
                # If one is GOOD but the other is BAD, then the GOOD
                # flag must be cleared.
                dst_qc = np.bitwise_or(dst_qc, src_qc)
                dst_qc = np.where(
                    dst_qc > core.quality.GOOD,
                    np.bitwise_and(dst_qc, (~core.quality.GOOD) & 0xFFFFFFFF),
                    dst_qc
                )

                with MergeNetCDFWriter(self.merge_ncfile) as ncw:
                    with ExitStack() as cm:
                        # Safely acquire netCDF resources
                        ncw.dst_nc = cm.enter_context(
                            netCDF4.Dataset(self.merge_ncfile, mode='r+')
                        )

                        ncw.dst_nc[varname][:] = dst_qc

    def _update_for_out_of_span_range(self):

        # Transfer the OUT_OF_SPAN_RANGE_FLAG
        for src_ncfile in [
            self.src_dir / core.licor.SPOFF_NCFILE,
            self.src_dir / core.licor.SPOSTCAL_NCFILE,
        ]:

            with xr.open_dataset(src_ncfile) as ds:
                src_qc = ds['xco2_wet_qc'].to_pandas().astype(np.uint32)

            # Go thru each xco2 qc var
            for xco2qc_var in [
                'xco2_sw_wet_qc', 'xCO2_sw_qc',
                'xco2_air_wet_qc', 'xCO2_air_qc',
            ]:
                with xr.open_dataset(self.merge_ncfile) as ds:
                    dst_qc = ds[xco2qc_var].to_pandas().astype(np.uint32)

                src_qc = src_qc.reindex(dst_qc.index, method='nearest')

                # Just doing a bitwise_or isn't quite right here.
                # If one is GOOD but the other is BAD, then the GOOD
                # flag must be cleared.
                dst_qc = np.bitwise_or(dst_qc, src_qc)
                dst_qc = np.where(
                    dst_qc > core.quality.GOOD,
                    np.bitwise_and(dst_qc, (~core.quality.GOOD) & 0xFFFFFFFF),
                    dst_qc
                )

                with MergeNetCDFWriter(self.merge_ncfile) as ncw:
                    with ExitStack() as cm:

                        # Safely acquire netCDF resources
                        ncw.dst_nc = cm.enter_context(
                            netCDF4.Dataset(self.merge_ncfile, mode='r+')
                        )

                        ncw.dst_nc[xco2qc_var][:] = dst_qc

    def record_loss_of_span(self):
        """
        If loss of span occured, transfer that information to the merge ncfile
        in the form of attributes.
        """
        cycle_header_ncfile = self.src_dir / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(cycle_header_ncfile) as ds:
            ts = ds['time'][ds['span_flag'] > 0].to_series()

        if len(ts) == 0:
            # no loss of span
            return

        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            nc.loss_of_span_start = ts.iloc[0].strftime('%Y-%m-%d %H:%M:%S')
            nc.loss_of_span_stop = ts.iloc[-1].strftime('%Y-%m-%d %H:%M:%S')

    def calculate_licor_pressure(self):
        """
        Compute and save the Equilibrator pressure in hPa
        """
        self.logger.info("Calculating equilibrator atmospheric pressure...")

        with netCDF4.Dataset(self.epoff_ncfile) as nc:
            p_kPa = nc['pressure'][:]
            qc = nc['pressure_qc'][:]

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                data = p_kPa * 10

                ncw.define_netcdf_variable('atm_pressure')
                ncw.write_netcdf_variable('atm_pressure', data, qc=qc)

    def copy_vapor_pressures(self):
        """
        Copy from EPOFF and APOFF, name them accordingly.
        """

        # Do epoff first.
        self.logger.info(f"Copying EPOFF {'vapor_pressure'}...")
        ncfile = self.src_dir / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            try:
                data = nc['vapor_pressure'][:]
            except IndexError:
                # no vapor pressure means that the user decline to calculate
                # post xco2, so there was no vapor pressure calculated
                msg = (
                    "No vapor pressure found, was the post xco2 "
                    "calculation declined?  No vapor pressure will be "
                    "merged."
                )
                self.logger.warning(msg)
                return

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                ncw.define_netcdf_variable('vapor_pressure_sw')
                ncw.write_netcdf_variable('vapor_pressure_sw', data)

        # For APOFF
        self.logger.info(f"Copying APOFF {'vapor_pressure'}...")
        ncfile = self.src_dir / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            data = nc['vapor_pressure'][:]

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                ncw.define_netcdf_variable('vapor_pressure_air')
                ncw.write_netcdf_variable('vapor_pressure_air', data)

    def calculate_o2_ratio(self):
        """
        TODO
        """
        msg = f"Deriving {'o2_ratio'} from EPOFF and APOFF"
        self.logger.info(msg)

        with xr.open_dataset(self.epoff_ncfile) as epoff:
            epoff.load()
            with xr.open_dataset(self.apoff_ncfile) as apoff:
                apoff.load()

                data = epoff['o2'].data / apoff['o2'].data  # noqa : E501

                # We need to compute QC as well
                epoff_qc = epoff['o2_qc'].data
                apoff_qc = apoff['o2_qc'].data

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                # O2 derived from both EPOFF and APOFF
                ncw.define_netcdf_variable('o2_ratio')

                # Start with all good QC.
                # If any values in the input were bad, flag that appropriately.
                o2_qc = np.full((len(data),), core.quality.GOOD)
                o2_qc = np.where(
                    apoff_qc != core.quality.GOOD,
                    core.quality.BAD_APOFF_O2,
                    o2_qc
                )
                o2_qc = np.where(
                    epoff_qc != core.quality.GOOD,
                    core.quality.BAD_EPOFF_O2,
                    o2_qc
                )

                ncw.write_netcdf_variable('o2_ratio', data, qc=o2_qc)

    def copy_temperature_from_licor(self):
        """
        Copy any needed LICOR variables into the merge file.
        """
        self.logger.info("Copying EPOFF temperature ...")

        with xr.open_dataset(self.epoff_ncfile) as epoff:
            epoff.load()
            temperature = epoff['temperature']
            qc = epoff['temperature_qc']

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                ncw.define_netcdf_variable('temperature')
                ncw.write_netcdf_variable('temperature', temperature, qc)

    def calculate_pco2_from_apoff_epoff(self):
        """
        Calculate the partial CO2 variables.
        """
        try:
            df = self.recalculate_pco2()
        except core.MissingParametersError as e:
            # Probably no SSS/SST
            self.logger.warning(e)
            return

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                self.logger.info("Copying EPOFF pCO2 to merge pCO2_sw...")
                ncw.define_netcdf_variable('pCO2_sw')
                ncw.write_netcdf_variable('pCO2_sw', df['pco2_sw'], qc=df['pco2_qc'])  # noqa : E501

                self.logger.info("Copying APOFF pco2 to merge pCO2_air...")
                ncw.define_netcdf_variable('pCO2_air')
                ncw.write_netcdf_variable('pCO2_air', df['pco2_air'], qc=df['pco2_qc'])  # noqa : E501

    def copy_xco2_from_apoff_epoff(self):
        """
        Copy xCO2 air from apoff, xCO2 sw from epoff
        """
        # First copy EPOFF
        with xr.open_dataset(self.epoff_ncfile) as ds:
            df = ds.load().to_dataframe()

            try:
                xco2_wet = df['post_xco2_wet']
                xco2_wet_qc = df['post_xco2_wet_qc']
            except KeyError:
                # no post xco2?  use pre
                msg = (
                    "Using xco2_wet for xco2_sw_wet instead of post_xco2_wet"
                )
                self.logger.warning(msg)
                xco2_wet = ds['xco2_wet']
                xco2_wet_qc = ds['xco2_wet_qc']

            try:
                xco2_dry = df['post_xco2_dry']
                xco2_dry_qc = df['post_xco2_dry_qc']
            except KeyError:
                # no post xco2 data? use pre
                msg = (
                    "Using xco2_dr' for xCO2_sw instead of post_xco2_dry"
                )
                self.logger.warning(msg)
                xco2_dry = df['xco2_dry']
                xco2_dry_qc = df['xco2_dry_qc']

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                self.logger.info(
                    "Copying EPOFF post_xco2_wet to merge xco2_sw_wet..."
                )

                ncw.define_netcdf_variable('xco2_sw_wet')
                ncw.write_netcdf_variable(
                    'xco2_sw_wet', xco2_wet, qc=xco2_wet_qc
                )

                self.logger.info(
                    "Copying EPOFF post_xco2_dry to merge xCO2_sw..."
                )

                ncw.define_netcdf_variable('xCO2_sw')
                ncw.write_netcdf_variable(
                    'xCO2_sw', xco2_dry, qc=xco2_dry_qc
                )

        # Now repeat for the air pump file
        with xr.open_dataset(self.apoff_ncfile) as ds:
            df = ds.load().to_dataframe()

            try:
                xco2_wet = df['post_xco2_wet']
                xco2_wet_qc = df['post_xco2_wet_qc']
            except KeyError:
                # no post xco2?  use pre
                msg = (
                    "Using xco2_wet for xco2_air_wet instead of post_xco2_wet"
                )
                self.logger.warning(msg)
                xco2_wet = df['xco2_wet']
                xco2_wet_qc = df['xco2_wet_qc']

            try:
                xco2_dry = df['post_xco2_dry']
                xco2_dry_qc = df['post_xco2_dry_qc']
            except KeyError:
                # no post xco2 data? use pre
                msg = (
                    "Using xco2_dry for xCO2_air instead of post_xco2_dry"
                )
                self.logger.warning(msg)
                xco2_dry = df['xco2_dry']
                xco2_dry_qc = df['xco2_dry_qc']

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                self.logger.info(
                    "Copying APOFF post_xco2_wet to merge xco2_air_wet..."
                )

                ncw.define_netcdf_variable('xco2_air_wet')
                ncw.write_netcdf_variable(
                    'xco2_air_wet', xco2_wet, qc=xco2_wet_qc
                )

                self.logger.info(
                    "Copying APOFF post_xco2_dry to merge xCO2_air..."
                )

                ncw.define_netcdf_variable('xCO2_air')
                ncw.write_netcdf_variable(
                    'xCO2_air', xco2_dry, qc=xco2_dry_qc
                )

    def update_xco2_quality_for_pressure(self):
        """
        If the pressure variable has bad QC, the xCO2 QC variables must reflect
        this.  Carry over the following flags:

            EXCESS_PRESSURE_OFF_DIFFERENCE
            AIR_PUMP_PRESSURE_DIFFERENCE
            EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE
            SPAN_PUMP_PRESSURE_DIFFERENCE

        Parameters
        ----------
        ncw : object
            netCDF writer for merged netCDF file
        """
        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                with netCDF4.Dataset(self.epoff_ncfile) as nc:
                    pressure_qc = nc['pressure_qc'][:]
                for xco2qc_var in ['xco2_sw_wet_qc', 'xCO2_sw_qc']:
                    self.__update_xco2qc_for_pressure(
                                                    ncw,
                                                    pressure_qc,
                                                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE,
                                                    xco2qc_var
                                                    )
                with netCDF4.Dataset(self.apoff_ncfile) as nc:
                    pressure_qc = nc['pressure_qc'][:]
                for xco2qc_var in ['xco2_air_wet_qc', 'xCO2_air_qc']:
                    self.__update_xco2qc_for_pressure(
                                                    ncw,
                                                    pressure_qc,
                                                    core.quality.AIR_PUMP_PRESSURE_DIFFERENCE,
                                                    xco2qc_var
                                                    )

    def __update_xco2qc_for_pressure(self, ncw, pressure_qc, flag, xco2qc_var):
        """
        Get the bitwise flags for particular flag/xco2 qc variable combination.
        QC variables will always have an EXCESS_PRESSURE_OFF_DIFFERENCE and
        SPAN_PUMP_PRESSURE_DIFFERENCE, but the AIR_PUMP and EQUILIBRATOR_PUMP
        PRESSURE_DIFFERENCE will depend on the xco2qc_var parameter.
        
        Parameters
        ----------
        ncw: object
            netCDF writer for merged netCDF file
        pressure_qc: np.array
            pressure quality control flags
        flag: int
            core.quality flag
        xco2qc_var: str
            parameter qc variable name to map new flags to
        """
        mask = 0
        for f in [
            core.quality.EXCESS_PRESSURE_OFF_DIFFERENCE,
            core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE,
            flag
        ]:
            mask |= f

        # Restrict QC to just those pressure flag values.
        pressure_qc = np.bitwise_and(np.copy(pressure_qc), mask)
        
        dst_qc = ncw.dst_nc[xco2qc_var][:]

        # Just doing a bitwise_or isn't quite right here.
        # If one is GOOD but the other is BAD, then the GOOD
        # flag must be cleared.
        dst_qc = np.bitwise_or(dst_qc, pressure_qc)
        dst_qc = np.where(
            dst_qc > core.quality.GOOD,
            np.bitwise_and(dst_qc, (~core.quality.GOOD) & 0xFFFFFFFF),
            dst_qc
        )

        ncw.dst_nc[xco2qc_var][:] = dst_qc
    
    def copy_dissolved_oxygen(self):
        """
        Copy the SBE16/SBE63 dissolved oxygen variables into the merge file.

        Parameters
        ----------
        ncw : object
            netCDF writer for merged netCDF file
        """
        if (
            not self.sbe16_ncfile.exists()
            and not self.external_sbe63_ncfile.exists()
        ):
            # If no dissolved oxygen file, then there is nothing to do.
            return
        elif self.external_sbe63_ncfile.exists():
            ncfile = self.external_sbe63_ncfile
        else:
            ncfile = self.sbe16_ncfile

        # We may have to reindex the oxygen data.  Pandas can help us there.
        with xr.open_dataset(self.merge_ncfile) as ds:
            ds.load()
            ts = ds[core.TIME].to_series()

        with xr.open_dataset(ncfile) as ds:

            if 'o2' not in ds:
                return

            df = ds.to_dataframe()

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                ncw.define_netcdf_variable('dissolved_oxygen')

                doxy = df['o2'].reindex(
                    ts.index, method='nearest', tolerance='30min',
                    fill_value=ncw.nc_variable_defs['pH_sw']['fill_value']
                )
                qc = df['o2_qc'].reindex(
                    ts.index, method='nearest', tolerance='30min',
                    fill_value=core.quality.MISSING_DATA
                )
                ncw.write_netcdf_variable('dissolved_oxygen', doxy, qc=qc)

    def copy_chl_and_ntu(self):
        """
        Copy chl and ntu data from the sbe16 into the merge file.
        """
        if not self.sbe16_ncfile.exists():
            self.logger.info(
                "No SBE16 netCDF file found, not merging any chl/ntu data."
            )
            return

        # We may have to reindex the chl/ntu data.  Pandas can help us there.
        with xr.open_dataset(self.merge_ncfile) as ds:
            ds.load()
            ts = ds[core.TIME].to_series()

        with xr.open_dataset(self.sbe16_ncfile) as ds:
            df = ds.to_dataframe()

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                if 'chl' in df.columns:
                    ncw.define_netcdf_variable('chl')

                    chl = df['chl'].reindex(
                        ts.index, method='nearest', tolerance='30min',
                        fill_value=ncw.nc_variable_defs['chl']['fill_value']
                    )
                    ncw.write_netcdf_variable('chl', chl)

                    qc = df['chl_qc'].reindex(
                        ts.index, method='nearest', tolerance='30min',
                        fill_value=core.quality.MISSING_DATA
                    )
                    ncw.write_netcdf_variable('chl_qc', qc)

                    # CHL Nighttime
                    ncw.define_netcdf_variable('chl_nighttime')

                    chl_nighttime = df['chl_nighttime'].reindex(
                        ts.index, method='nearest', tolerance='30min',
                        fill_value=ncw.nc_variable_defs['chl_nighttime']['fill_value']  # noqa : E501
                    )
                    ncw.write_netcdf_variable('chl_nighttime', chl_nighttime)

                    qc = df['chl_nighttime_qc'].reindex(
                        ts.index, method='nearest', tolerance='30min',
                        fill_value=core.quality.MISSING_DATA
                    )
                    ncw.write_netcdf_variable('chl_nighttime_qc', qc)

                if 'ntu' in df.columns:
                    ncw.define_netcdf_variable('ntu')

                    ntu = df['ntu'].reindex(
                        ts.index, method='nearest', tolerance='30min',
                        fill_value=ncw.nc_variable_defs['ntu']['fill_value']
                    )
                    ncw.write_netcdf_variable('ntu', ntu)

                    qc = df['ntu_qc'].reindex(
                        ts.index, method='nearest', tolerance='30min',
                        fill_value=core.quality.MISSING_DATA
                    )
                    ncw.write_netcdf_variable('ntu_qc', qc)

    def copy_ph(self):
        """
        Copy pH data into the merge file.  This can come either from SAMI
        data derived from the mapco2 text file or from an externally provided
        text file.
        """
        ph_varname, src_ncfile = self.determine_src_ph_ncfile()
        self.logger.info(f"Using {src_ncfile} as source for ph.")
        if src_ncfile is None:
            self.logger.info(
                "No pH data file found, not merging any pH data."
            )
            return

        with xr.open_dataset(src_ncfile) as ds:
            ds.load()
            df = ds.to_dataframe()

            qc_varname = f"{ph_varname}_qc"

            flag_masks = ds[qc_varname].flag_masks
            flag_meanings = ds[qc_varname].flag_meanings

            # grab the source attribute so that the merge file will clearly
            # show where the ph came from.
            ph_source = ds.data_source

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                # We may have to reindex the sami data.  Pandas can help us
                # there.
                v = ncw.dst_nc['time'][:]
                data = pd.to_datetime(
                    v, unit='s', origin=pd.Timestamp('1970-01-01')
                )
                ts = pd.Series(data, index=data)

                ncw.define_netcdf_variable('pH_sw')

                pH_sw = df[ph_varname].reindex(
                    ts.index, method='nearest', tolerance='30min',
                    fill_value=ncw.nc_variable_defs['pH_sw']['fill_value']
                )
                ncw.write_netcdf_variable('pH_sw', pH_sw)

                # log the source of the ph
                ncw.dst_nc['pH_sw'].source = ph_source

                qc = df[qc_varname].reindex(
                    ts.index, method='nearest', tolerance='30min',
                    fill_value=core.quality.MISSING_DATA
                )
                ncw.write_netcdf_variable('pH_sw_qc', qc)

                # copy the mask attributes
                ncw.dst_nc['pH_sw_qc'].flag_masks = flag_masks
                ncw.dst_nc['pH_sw_qc'].flag_meanings = flag_meanings

    def copy_sstc_variables(self):
        """
        Copy any needed SSTC (probably just salinity and sea surface
        temperature) variables into the merge file.
        """
        sss_varname, sst_varname, src_ncfile = self.determine_src_sstc_ncfile()

        if src_ncfile is None:
            return

        with xr.open_dataset(src_ncfile) as ds:
            ds.load()
            df = ds.to_dataframe()

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                # We may have to reindex the met data.
                # Pandas can help us there.
                v = ncw.dst_nc['time'][:]
                data = pd.to_datetime(
                    v, unit='s', origin=pd.Timestamp('1970-01-01')
                )
                ts = pd.Series(data, index=data)

                # salinity and qc
                ncw.define_netcdf_variable('SSS')

                fill_value = ncw.nc_variable_defs['SSS']['fill_value']
                
                sss_index = ~df[sss_varname].isna()
                data = df.loc[sss_index, sss_varname].reindex(
                    ts.index, method='nearest', tolerance='20min',
                    fill_value=fill_value
                )
                ncw.dst_nc['SSS'].source = ds[sss_varname].source

                sss_qcvarname = ds[sss_varname].ancillary_variables
                qc = df.loc[sss_index, sss_qcvarname].reindex(
                    ts.index, method='nearest', tolerance='20min',
                    fill_value=core.quality.MISSING_DATA
                )

                ncw.write_netcdf_variable('SSS', data, qc=qc)

                # temperature and qc
                ncw.define_netcdf_variable('SST')
                
                sst_index = ~df[sst_varname].isna()
                data = df.loc[sst_index, sst_varname].reindex(
                    ts.index, method='nearest', tolerance='20min',
                    fill_value=ncw.nc_variable_defs['SST']['fill_value']
                )

                ncw.dst_nc['SST'].source = ds[sst_varname].source

                sst_qcvarname = ds[sst_varname].ancillary_variables
                qc = df.loc[sst_index, sst_qcvarname].reindex(
                    ts.index, method='nearest', tolerance='20min',
                    fill_value=core.quality.MISSING_DATA
                )

                ncw.write_netcdf_variable('SST', data, qc=qc)

    def copy_gps_variables(self):
        """
        Copy lat/lon variables into the merge file.
        """
        self.logger.info("Tranferring GPS data...")

        ncfile = self.src_dir / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            lat = ds['latitude'].to_pandas()
            lat_qc = ds['latitude_qc'].to_pandas()
            lon = ds['longitude'].to_pandas()
            lon_qc = ds['longitude_qc'].to_pandas()

        # we need to reindex the data
        with xr.open_dataset(self.merge_ncfile) as ds:
            xco2 = ds['xCO2_sw'].to_pandas()

            latitude = lat.reindex(xco2.index, method='nearest')
            latitude_qc = lat_qc.reindex(xco2.index, method='nearest')
            longitude = lon.reindex(xco2.index, method='nearest')
            longitude_qc = lon_qc.reindex(xco2.index, method='nearest')

        with MergeNetCDFWriter(self.merge_ncfile) as ncw:
            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.merge_ncfile, mode='r+')
                )

                ncw.define_netcdf_variable('latitude')
                ncw.write_netcdf_variable('latitude', latitude, qc=latitude_qc)

                ncw.define_netcdf_variable('longitude')
                ncw.write_netcdf_variable(
                     'longitude', longitude, qc=longitude_qc
                )
