"""
Reduce the raw saildrone data
"""

# standard library imports
from contextlib import ExitStack
import datetime as dt
import pathlib

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd

# local imports
from . import core
from xco2qc.core.vardefs import data_dict as vardefs
from xco2qc.core.licor import GLOBAL_ATT_PUMP_MODES as PUMP_MODES


class SailDroneBase(core.MapCO2core):
    """
    Common functionality for saildrone classes.
    """

    def __init__(
        self, src_file, dst_dir, verbosity=None, logger_name=None, **kwargs
    ):

        super().__init__(
            dst_dir=dst_dir, logger_name=logger_name, verbosity=verbosity,
            **kwargs
        )

        self.src_file = pathlib.Path(src_file)

        if not self.dst_dir.exists():
            self.dst_dir.mkdir(exist_ok=True, parents=True)

        self.time_base = dt.datetime(1970, 1, 1)

    def determine_cycle_extents(self):
        """
        Determine where the licor cycle states start and stop.
        """
        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(
                netCDF4.Dataset(self.src_file, mode='r')
            )

            span_coef = self.src_nc['CO2DETECTOR_SPAN_COEFFICIENT_ASVCO2'][:]

            # look at the span coefficient to tell us where the cycles are.
            # There should be just a single span coefficient value in each
            # cycle, apparently.  At the very end of the cycle.
            cycle_indices = np.argwhere(~np.isnan(span_coef))
            if len(cycle_indices) == 0:
                msg = (
                    "There was no valid span coefficient data.  There is no "
                    "way to find the start or end of the cycles."
                )
                raise RuntimeError(msg)

            # Ok, the cycle end indices are in the 2nd column.  The first
            # column is all zeros, so use that as the cycle start indices.
            start = 0
            lst = []
            for j in range(len(cycle_indices)):
                idx = slice(start, cycle_indices[j, 0])
                lst.append(idx)
                start = cycle_indices[j, 0]

            self.cycle_indices = lst

    def write_output_netcdf_file(self, ncfile, df, state=None):
        """
        Parameters
        ----------
        ncfile : path or str
            Path to netCDF file we intend to create.
        df : pandas dataframe
            Contains all variable data to be written to netCDF file.
        state : str or None
            If str, this is an attribute to be written to the netCDF file.
        """

        if ncfile.exists():
            mode = 'r+'
        else:
            mode = 'w'

        with netCDF4.Dataset(ncfile, mode=mode) as nc:

            nc.createDimension('time', 0)

            self.write_global_attributes(nc, state=state)

            for varname in df.columns:
                self.logger.debug(f"Writing {varname} to {ncfile}")

                metadata = self.nc_variable_defs[varname]

                ncvar = nc.createVariable(
                    varname,
                    metadata['datatype'],
                    dimensions=('time',),
                    fill_value=metadata['fill_value']
                )

                # Write the netCDF variable attributes
                for attrname, attrvalue in metadata['attributes'].items():
                    setattr(ncvar, attrname, attrvalue)

                data = df[varname]
                data = data.fillna(metadata['fill_value'])

                ncvar[:] = data


class SailDroneCycleHeaders(SailDroneBase):
    """
    Reduce the saildrone cycle header variables.

    Attributes
    ----------
    inputfile : str or path
        Path to input raw file
    output_netcdf_dir : str or path
        Path to output directory for netCDF files
    """

    def __init__(
        self, src_file, dest_dir, verbosity=None, **kwargs
    ):
        """
        Parameters
        ----------
        src_file : str or path
            Path to input saildrone netCDF file
        dest_dir : str or path
            Path to output directory for netCDF files
        verbosity : str
            Logging level
        """
        super().__init__(
            src_file, dest_dir,
            logger_name='saildrone-header', verbosity=verbosity, **kwargs
        )

        self.nc_variable_defs = vardefs['cycle_header']

        self.time_base = dt.datetime(1970, 1, 1)

    def run(self):
        """
        Run the import process on a saildrone netCDF file.
        """
        self.determine_cycle_extents()

        self.write_reduced_variables()

    def write_reduced_variables(self):
        """
        Write cycle header data to netCDF file.
        """
        data = {}
        with ExitStack() as cm:

            # Safely acquire netCDF resources
            src_nc = cm.enter_context(netCDF4.Dataset(self.src_file, mode='r'))

            # justify this.
            # take the starting time of the cycle as the first time value
            idx = [cycle_index.start for cycle_index in self.cycle_indices]
            data['time'] = src_nc['time'][idx]
            data['latitude'] = src_nc['latitude'][idx]
            data['longitude'] = src_nc['longitude'][idx]

            # take these other values as the very last such items in the cycle
            zero_coef = self.src_nc['CO2DETECTOR_ZERO_COEFFICIENT_ASVCO2'][:]
            span_coef = self.src_nc['CO2DETECTOR_SPAN_COEFFICIENT_ASVCO2'][:]
            span2_coef = self.src_nc['CO2DETECTOR_SECONDARY_COEFFICIENT_ASVCO2'][:]  # noqa : E501

            idx = [cycle_index.stop for cycle_index in self.cycle_indices]
            data['zero_coefficient'] = zero_coef[idx]
            data['span_coefficient'] = span_coef[idx]
            data['span2_coefficient'] = span2_coef[idx]

            # Should these all be good?
            data['latitude_qc'] = np.full(
                data['span_coefficient'].shape, core.quality.GOOD
            )
            data['longitude_qc'] = np.full(
                data['span_coefficient'].shape, core.quality.GOOD
            )
            data['span_coefficient_qc'] = np.full(
                data['span_coefficient'].shape, core.quality.GOOD
            )
            # data['span_coefficient2_qc'] = np.full(
            #     data['span_coefficient'].shape, core.quality.GOOD
            # )

            # span_flag is the same as ASVCO2_SPAN_ERROR_FLAGS.  To keep
            # compatibility with the mapco2 system, we need only two values,
            # 0 or 255.
            # where is the span cal skipped?  See the manual.
            span_flag = src_nc['ASVCO2_SPAN_ERROR_FLAGS'][idx]
            data['span_flag'] = np.where(
                np.bitwise_and(span_flag, 0x00040000), 255, 0
            )

            data['zero_flag'] = src_nc['ASVCO2_ZERO_ERROR_FLAGS'][idx]

        df = pd.DataFrame(data)

        ncfile = self.dst_dir / core.CYCLE_HEADER_NCFILE

        self.write_output_netcdf_file(ncfile, df)

    def write_global_attributes(self, nc, state=None):
        """
        Create the netCDF file global attributes.
        """
        nc.data_source = 'MAPCO2'
        nc.platform = 'saildrone'


class SailDroneLicor(SailDroneBase):
    """
    Convert saildrone netCDF file into the same style of netCDF files that
    the text processing uses.

    Attributes
    ----------
    inputfile : str or path
        Path to input raw file
    output_netcdf_dir : str or path
        Path to output directory for netCDF files
    """

    def __init__(
        self, src_file, dest_dir,
        deployment_number=None, verbosity=None, **kwargs
    ):
        """
        Parameters
        ----------
        src_file : str or path
            Path to input raw file
        dest_dir : str or path
            Path to output directory for netCDF files
        verbosity : str
            Logging level
        """
        super().__init__(
            src_file, dest_dir,
            logger_name='saildrone-licor', verbosity=verbosity, **kwargs
        )

        self.nc_variable_defs = vardefs['licor']

    def run(self):
        """
        Run the import process on a saildrone netCDF file.

        """
        self.determine_cycle_extents()

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(
                netCDF4.Dataset(self.src_file, mode='r')
            )

            for state in self.src_nc['INSTRUMENT_STATE'].state_list.split():
                self.logger.debug(f'Looking at {state}')

                if state == 'SUMMARY':
                    self.logger.debug(f'Skipping {state}')
                    continue

                self.create_licor_file(state)

    def create_licor_file(self, state):
        """
        Create a netCDF file for just this particular state (pump-mode)
        """

        instrument_state = np.squeeze(self.src_nc['INSTRUMENT_STATE'])

        data = {}

        # initialize space for the data for this state (pump-mode)
        for varname in [
            'o2', 'o2_qc', 'pressure', 'pressure_qc',
            'temperature', 'temperature_qc',
            'rh', 'rh_qc', 'rh_stddev',
            'rh_temp', 'rh_temp_qc', 'rh_temp_stddev',
            'xco2_dry_air_asvco2', 'xco2_dry_air_asvco2_qc',
            'xco2_dry_sw_asvco2', 'xco2_dry_sw_asvco2_qc',
            'xco2_wet', 'xco2_wet_qc', 'xco2_wet_stddev',
            'time',
            'raw_reference', 'raw_reference_qc',
            'raw_sample', 'raw_sample_qc'
        ]:
            data[varname] = np.zeros((len(self.cycle_indices,)))

        # These two have just a single value defined, at the end of each
        # cycle.
        idx = [cycle_index.stop for cycle_index in self.cycle_indices]
        var = self.src_nc['XCO2_DRY_AIR_MEAN_ASVCO2']
        data['xco2_dry_air_asvco2'] = var[idx]

        var = self.src_nc['XCO2_DRY_SW_MEAN_ASVCO2']
        data['xco2_dry_sw_asvco2'] = var[idx]

        for j, cycle_idx in enumerate(self.cycle_indices):  # noqa : E501

            state_idx = np.argwhere(instrument_state[cycle_idx] == state)

            # justify this.
            # take the starting time of the cycle as the first time value
            # for this state
            cycle_time = self.src_nc['time'][cycle_idx]
            data['time'][j] = cycle_time[state_idx[0]]

            # for the rest, take the mean.
            cycle_data = self.src_nc['RH_ASVCO2'][cycle_idx]
            data['rh'][j] = np.nanmean(cycle_data[state_idx])
            data['rh_qc'][j] = self.qc(
                'RH_ASVCO2', data['rh'][j], cycle_idx, state_idx
            )
            data['rh_stddev'][j] = np.nanstd(cycle_data[state_idx])

            cycle_data = self.src_nc['RH_TEMP_ASVCO2'][cycle_idx]
            data['rh_temp'][j] = np.nanmean(cycle_data[state_idx])
            data['rh_temp_qc'][j] = self.qc(
                'RH_TEMP_ASVCO2', data['rh_temp'][j], cycle_idx, state_idx
            )  # noqa : E501

            cycle_data = self.src_nc['O2_ASVCO2'][cycle_idx]
            data['o2'][j] = np.nanmean(cycle_data[state_idx])
            data['o2_qc'][j] = self.qc(
                'O2_ASVCO2', data['o2'][j], cycle_idx, state_idx
            )

            cycle_data = self.src_nc['CO2_ASVCO2'][cycle_idx]
            data['xco2_wet'][j] = np.nanmean(cycle_data[state_idx])
            data['xco2_wet_qc'][j] = self.qc(
                'CO2_ASVCO2', data['xco2_wet'][j], cycle_idx, state_idx
            )
            data['xco2_wet_stddev'][j] = np.nanstd(cycle_data[state_idx])

            cycle_data = self.src_nc['CO2DETECTOR_TEMP_ASVCO2'][cycle_idx]
            data['temperature'][j] = np.nanmean(cycle_data[state_idx])
            data['temperature_qc'][j] = self.qc(
                'CO2DETECTOR_TEMP_ASVCO2', data['temperature'][j],
                cycle_idx, state_idx
            )

            # it's CO2DETECTOR_PRESS_UNCOMP_ASVCO2, it's NOT
            # CO2DETECTOR_PRESS_ASVCO2, see issue #296
            press_varname = 'CO2DETECTOR_PRESS_UNCOMP_ASVCO2'
            cycle_data = self.src_nc[press_varname][cycle_idx]
            data['pressure'][j] = np.nanmean(cycle_data[state_idx])
            data['pressure_qc'][j] = self.qc(
                press_varname, data['pressure'][j], cycle_idx, state_idx
            )

            cycle_data = self.src_nc['CO2DETECTOR_RAWSAMPLE_ASVCO2'][cycle_idx]  # noqa : E501
            data['raw_sample'][j] = np.nanmean(cycle_data[state_idx])
            data['raw_sample_qc'][j] = self.qc(
                'CO2DETECTOR_RAWSAMPLE_ASVCO2', data['raw_reference'][j],
                cycle_idx, state_idx
            )

            cycle_data = self.src_nc['CO2DETECTOR_RAWREFERENCE_ASVCO2'][cycle_idx]  # noqa : E501
            data['raw_reference'][j] = np.nanmean(cycle_data[state_idx])
            data['raw_reference_qc'][j] = self.qc(
                'CO2DETECTOR_RAWREFERENCE_ASVCO2', data['raw_sample'][j],
                cycle_idx, state_idx
            )

            data['xco2_dry_air_asvco2_qc'][j] = self.qc(
                'XCO2_DRY_AIR_MEAN_ASVCO2', data['xco2_dry_air_asvco2'][j],
                cycle_idx, state_idx
            )

            data['xco2_dry_sw_asvco2_qc'][j] = self.qc(
                'XCO2_DRY_SW_MEAN_ASVCO2', data['xco2_dry_sw_asvco2'][j],
                cycle_idx, state_idx
            )

        df = pd.DataFrame(data)

        output_ncfile = self.dst_dir / core.licor.SAILDRONE_NCFILES[state]

        self.write_output_netcdf_file(output_ncfile, df, state=state)

    def qc(self, asvco2_varname, datum, cycle_idx, state_idx):
        """
        The QC variables all start out as GOOD.  This is probably not
        correct.
        """
        if np.isnan(datum):
            return core.quality.OUT_OF_RANGE
        else:
            return core.quality.GOOD

    def write_global_attributes(self, nc, state=None):
        """
        Create the netCDF file global attributes.
        """
        nc.data_source = 'LICOR'
        nc.platform = 'saildrone'

        # these are unique to the licor files
        if state is not None:
            nc.pump_mode = PUMP_MODES[state]
