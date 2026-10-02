"""
This module is responsible for performing a licor pressure correction and/or
the MBL correction, if both/either are warrented.
"""
# standard library imports
from contextlib import ExitStack
import pathlib

# 3rd party libraries
import netCDF4
import xarray as xr

# Local imports
from xco2qc import core
from xco2qc import science_algorithms as sa


class XCO2Adjustments(core.MapCO2core):
    """
    Attributes
    ----------
    src_dir : path
        Path to reduced level netCDF files, we need APOFF and EPOFF
        to recalculate vapor pressure in case of a non-zero pressure
        correction.
    merge_ncfile : path
        Path to the merge netCDF file.
    mbl_correction : float
        Correction/offset/adjustment suggested by the Marine Boundary Layer
        (MBL) data.
    pressure_correction : float
        TODO
    """
    def __init__(self, src_dir, merge_ncfile, mbl_correction=0.0,
                 pressure_correction=0.0, verbosity=None):
        """
        src_dir : path
            Path to reduced level netCDF files, we need APOFF and EPOFF
            to recalculate vapor pressure in case of a non-zero pressure
            correction.
        merge_ncfile : path or str
            Data is merged into this file.
        mbl_correction : float or None
            Correction/offset/adjustment suggested by the Marine Boundary Layer
            (MBL) data.
        pressure_correction : float or None
            TODO
        """
        super().__init__(
            src_dir=src_dir, verbosity=verbosity, logger_name='adjustments'
        )

        self.merge_ncfile = pathlib.Path(merge_ncfile)

        config = self.config['adjustments']
        if mbl_correction is None:
            # Get the correction from the config file
            self.mbl_offset = config['mbl_correction']
        else:
            # Take the specified xco2 correction
            self.mbl_offset = mbl_correction

        if pressure_correction is None:
            # Get the pressure correction from the config file
            self.licor_pressure_offset = config['licor_pressure_correction']
        else:
            # Take the specified pressure correction
            self.licor_pressure_offset = pressure_correction

    def run(self):
        self.record_mbl_correction()
        self.record_licor_pressure_offset()
        if self.mbl_offset == 0 and self.licor_pressure_offset == 0:
            msg = (
                'No adjustment will be made since the MBL correction and '
                'the pressure offset are both zero.'
            )
            self.logger.info(msg)
        else:
            self.logger.info('Starting with adjustments...')

        self.recalculate_licor_pressure()
        self.recalculate_vapor_pressures()
        self.recompute_xco2_with_correction()
        self.recompute_pco2()
        self.recompute_fco2()
            
        self.logger.info('Finished with adjustments...')
    
    def recompute_fco2(self):
        """
        Calculate the fCO2 variables.
        """
        try:
            df = self.recalculate_fco2()
        except core.MissingParametersError as e:
            # Probably no SSS/SST
            self.logger.warning(e)
            return

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            nc = cm.enter_context(
                netCDF4.Dataset(self.merge_ncfile, mode='r+')
            )

            nc['fCO2_sw'][:] = df['fco2_sw']
            nc['fCO2_air'][:] = df['fco2_air']

    def recompute_pco2(self):
        """
        Calculate the partial CO2 variables.
        """
        try:
            df = self.recalculate_pco2()
        except RuntimeError as e:
            # Probably no SSS/SST
            self.logger.warning(e)
            return

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            nc = cm.enter_context(
                netCDF4.Dataset(self.merge_ncfile, mode='r+')
            )

            nc['pCO2_sw'][:] = df['pco2_sw']
            nc['pCO2_air'][:] = df['pco2_air']

    def record_mbl_correction(self):
        """
        Record the mbl adjustment and the timestamp of the MBL data file
        """

        timestamp = core.data.mbl.get_timestamp()
        if timestamp is None:
            msg = (
                'Unable to locate the file creation timestamp in the MBL '
                'file.  This prevents us from populating the SOCAT XML file '
                'with this metadata.'
            )
            self.logger.warning(msg)
            return

        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            nc.mbl_correction = self.mbl_offset
            nc.mbl_timestamp = str(timestamp)
    
    def record_licor_pressure_offset(self):
        """
        Record the licor pressure offset.
        """
        
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            nc.licor_pressure_correction = self.licor_pressure_offset
    
    def recalculate_licor_pressure(self):
        """
        Compute and save the Equilibrator pressure in hPa

        Parameters
        ----------
        p_kPa, qc : ndarray
            equilibrilator pressure in kPa, and quality
        """
        self.logger.info('Recalculating LICOR pressure...')

        # the pressure must be adjusted from the source, which is EPOFF
        ncfile = self.src_dir / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            p_kPa = nc['pressure'][:] + self.licor_pressure_offset
            qc = nc['pressure_qc'][:]

        data = p_kPa * 10

        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            nc['atm_pressure'][:] = data
            nc['atm_pressure_qc'][:] = qc

    def recalculate_vapor_pressures(self):
        """
        TODO
        """
        self.logger.info('Recalculating vapor pressure...')

        ncfile = self.src_dir / core.licor.SPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            rh = nc['rh'][:]

        # Recalculate wet vapor pressure for EPOFF
        ncfile = self.src_dir / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            p_kPa = nc['pressure'][:] + self.licor_pressure_offset
            temp_rh = nc['rh_temp'][:]
            rh_equil = nc['rh'][:]

        vapor_pressure = sa.calculate_vapor_pressure(temp_rh, rh_equil, rh)
        data = vapor_pressure * 1000 / p_kPa
        
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            nc['vapor_pressure_sw'][:] = data

        # Recalculate wet vapor pressure for APOFF
        ncfile = self.src_dir / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            p_kPa = nc['pressure'][:] + self.licor_pressure_offset
            temp_rh = nc['rh_temp'][:]
            rh_air = nc['rh'][:]
        
        vapor_pressure = sa.calculate_vapor_pressure(temp_rh, rh_air, rh)
        data = vapor_pressure * 1000 / p_kPa

        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            nc['vapor_pressure_air'][:] = data

    def recompute_xco2_with_correction(self):
        """
        Recompute the xCO2 variables with MBL corrections.  The new "wet" xCO2
        will just be a constant offset difference from the old wet xCO2, but
        since the xCO2 computation is non-linear, the new "dry" xCO2 will NOT
        just differ by that constant value from the old "dry" value.
        """
        self.logger.info('Recalculating xCO2 ...')

        # first for the equilibrator pump off file
        ncfile = self.src_dir / core.licor.EPOFF_NCFILE
        ds_wet = self._recompute_xco2_with_correction(ncfile)

        # Now repeat for the air pump file
        ncfile = self.src_dir / core.licor.APOFF_NCFILE
        ds_dry = self._recompute_xco2_with_correction(ncfile)

        # and write to file
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            # write for the EPOFF xco2
            nc['xco2_sw_wet'][:] = ds_wet['xco2_wet'].data
            nc['xCO2_sw'][:] = ds_wet['xco2_dry'].data

            # Now repeat for the APOFF xco2
            nc['xco2_air_wet'][:] = ds_dry['xco2_wet'].data
            nc['xCO2_air'][:] = ds_dry['xco2_dry'].data

    def _recompute_xco2_with_correction(self, source_ncfile):
        """
        Returns
        -------
        xarray Dataset of xCO2 wet and dry, both QC variables
        """

        ncfile = self.src_dir / core.licor.SPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            rh = ds['rh'].data

        with xr.open_dataset(source_ncfile) as ds:
            # get the appropriate xco2 data to adjust
            if 'post_xco2_wet' in ds.keys():
                xco2_wet = ds['post_xco2_wet'] + self.mbl_offset
            else:
                xco2_wet = ds['xco2_wet'] + self.mbl_offset
            time = ds[core.TIME]
            rh_temp = ds['rh_temp'].data
            rh_equil = ds['rh'].data
            temp = ds['temperature'].data
            press = ds['pressure'].data + self.licor_pressure_offset  # we are not saving the licor pressure correction to the APOFF nor EPOFF ncfiles, so must apply them here.
            # qc_wet and qc_dry are not used in this process, so they don't need to be set.
            # qc_wet = ds['xco2_wet_qc'].data
            # qc_dry = ds['xco2_dry_qc'].data
        
        xco2_dry = sa.calc_dry_xco2(rh_temp, rh_equil, rh, temp, xco2_wet,
                                    press)

        ds = xr.Dataset(
            data_vars={
                'xco2_wet': xco2_wet,
                # 'qc_wet': qc_wet,
                'xco2_dry': xco2_dry,
                # 'qc_dry': qc_dry,
            },
            coords={'time': time}
        )
        return ds
