"""
Take the raw netCDF files and process them, i.e. apply data reduction.  This
means that the data is reduced from the arrays of raw observations at each time
step to a single value.
"""

# Standard library imports
from contextlib import ExitStack
import datetime as dt
import logging
import shutil
import warnings

# 3rd party library imports
import gsw
import numpy as np
import netCDF4
import pandas as pd
import xarray as xr

# local imports
from . import core
from .netcdf import NetCDFWriter
from xco2qc import sami
from xco2qc.seawater_density import seawater_density
from xco2qc.utilities import simple_timezone_offset
from xco2qc import SailDroneLicor, SailDroneCycleHeaders


class DataReductionNetCDFWriter(NetCDFWriter):
    """
    Comprises superclass that takes care of most operations.

    Attributes
    ----------
    nc_variable_defs : dict
        MetadataWriter for each netCDF variable.
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    reduction_method : int
        Use this method to reduce the samples at each cycle to a single
        measurement.
    """
    def __init__(
        self, src_ncfile, dst_ncfile, verbosity=None, reduce=core.REDUCE_MEAN
    ):
        """
        Parameters
        ----------
        reduce : str
            Use this method to reduce the samples at each cycle to a single
            measurement.
        verbosity : str
            Logging level
        """
        super().__init__(
            src_ncfile, verbosity=verbosity, dst_ncfile=dst_ncfile
        )

        self.logger = logging.getLogger('reduce')

        self.reduction_method = reduce

        self.initialize_netcdf_definitions()

    def transfer_coordinate_variables(self):
        """
        The coordinate variables should never change from level to level.
        """
        # Transfer the coordinate variables (just time for now).  Since these
        # are coordinate variables, they should already be defined in the
        # netcdf file.
        self.dst_nc[core.TIME][:] = self.src_nc[core.TIME][:]

    def reduce(self, raw_data, metadata=None):
        """
        Reduce the data to a single value.

        Parameters
        ----------
        raw_data : masked ndarray
            raw netCDF data, corresponds to what is in the mapco2 text file
        metadata : dict, optional
            metadata for the data in question

        Returns
        -------
        data_mean, data_stddev : ndarray
            1D array of a geophysical quantity, mean and standard deviation
        qc : ndarray
            Quality array corresponding to the reduced data
        """
        if self.reduction_method == core.REDUCE_MEAN:
            # np.nanmean will produce a masked array
            data = np.nanmean(raw_data, axis=1)
        elif self.reduction_method == core.REDUCE_MEDIAN:
            # np.nanmedian will turn the masked input into a regular array.
            with warnings.catch_warnings():
                # the median function can produce warnings if some of the rows
                # are all NaN.  They just clutter up the output, so suppress
                # them.
                warnings.simplefilter("ignore")
                data = np.nanmedian(raw_data, axis=1)

        stddev = np.nanstd(raw_data, axis=1)

        # Ok, where ever we have nans, that is missing data
        qc = np.where(
            np.isnan(data),
            core.quality.MISSING_DATA,
            core.quality.GOOD
        )

        # If the raw data was masked and an integer datatype (floating point
        # datatypes seem to result in np.nan, which is caught above), then the
        # data reduction will not produce NaNs.  So wherever the data was
        # masked should be interpreted as missing data.
        if hasattr(data, 'mask'):
            qc = np.where(data.mask, core.quality.MISSING_DATA, qc)

        # np.nanmedian will introduce NaNs into the data if the
        # data is masked and floating point and we don't want that (it causes
        # netCDF4 to complain).  Best to replace any NaNs with the fill value.
        # data = np.where(np.isnan(data), raw_data.fill_value, data)

        return data, stddev, qc


class XCO2Reduce(core.MapCO2core):
    """
    Transform the raw netCDF files by data reduction.  Most of the time, we
    will just use the mean.

    Attributes
    ----------
    src_dir, dst_dir : pathlib paths
        Paths to the raw source netCDF files (assumed to all be in the
        same directory) and the destination directory where the reduced files
        will be written.
    kwargs : dict
        Keyword arguments to be passed on to the various reducers.
    """
    def __init__(
        self, src_dir, dst_dir, verbosity=None, mapco2_licor_reduce=core.REDUCE_MEAN,
        sbe16_mapping=False, **kwargs
    ):
        super().__init__(
            src_dir=src_dir, dst_dir=dst_dir, verbosity=verbosity,
            logger_name='reduce'
        )
        self.verbosity = verbosity

        if mapco2_licor_reduce not in [core.REDUCE_MEAN, core.REDUCE_MEDIAN]:
            raise RuntimeError(f"Unrecognized data reduction scheme: {mapco2_licor_reduce}")
        else:
            self.mapco2_licor_reduce = mapco2_licor_reduce  # this is only useful when processing MAPCO2 data. This does not affect Saildrone processing.

        self.sbe16_mapping = sbe16_mapping

        if not self.dst_dir.exists():
            self.dst_dir.mkdir(parents=True, exist_ok=True)

        self.kwargs = kwargs

    def run(self):

        self.logger.info(f"Starting at {dt.datetime.now()}.")

        self.process_cycle_headers()
        self.process_licor()
        self.process_external_met()
        self.process_met()
        self.process_sbe16()
        self.process_prawler_ctd()
        self.process_sami()
        self.process_seafet()
        self.process_durafet()
        self.process_external_sbe63()
        self.process_historical()

        self.post_mortem()

    def post_mortem(self):
        """
        Take care of miscellaneous tasks.
        """

        # is there any validation data?  if so, copy it to the reduce area
        src_ncfile = self.src_dir / 'validation.nc'
        if src_ncfile.exists():
            dst_ncfile = self.dst_dir / 'validation.nc'
            shutil.copyfile(src_ncfile, dst_ncfile)

        # Display the new "reduced" netCDF files and their sizes.
        for ncfile in sorted(
            self.dst_dir.glob('*.nc'), key=lambda path: path.name
        ):
            kb_size = ncfile.stat().st_size / 1024
            self.logger.info(f"{ncfile.name:25}  {kb_size:8.2f} KB")

        self.logger.info(f"Finishing at {dt.datetime.now()}.")

    def process_cycle_headers(self):

        # If there is a saildrone file, then that has the cycle header
        # information.
        src_file = self.src_dir / core.SAILDRONE_NCFILE
        if src_file.exists():

            with SailDroneCycleHeaders(
                src_file, self.dst_dir, verbosity=self.verbosity
            ) as o:
                o.run()

        else:
            self.process_cycle_headers_text()

    def process_cycle_headers_text(self):
        """
        There is no data reduction for the cycle header data, but we do need
        to add some QC variables for this stage.
        """
        src = self.src_dir / core.CYCLE_HEADER_NCFILE
        dst = self.dst_dir / core.CYCLE_HEADER_NCFILE
        shutil.copyfile(src, dst)

        for variable, metadata in core.vardefs.data_dict['cycle_header'].items():  # noqa : E501

            # Are there associated variables?
            try:
                anc_vars = metadata['attributes']['ancillary_variables']
            except KeyError:
                # no ancillary variables, so this variable does not have an
                # associated QC variable.  Skip it.
                continue

            # Is one of those associated variables a QC variable?
            # Usually there is just a single ancillary variable, but not
            # always, so we need to be careful about how we treat this.  Force
            # it to be a list of strings.
            try:
                qc_var = [
                    anc_var for anc_var in anc_vars.split()
                    if anc_vars.endswith('_qc')
                ][0]
            except IndexError:
                # no QC variable in the list of ancillary variables.  Again,
                # just skip this variable.
                continue

            vardef = core.vardefs.data_dict['cycle_header'][qc_var]

            with netCDF4.Dataset(dst, mode='r+') as nc:
                ncvar = nc.createVariable(
                    qc_var, vardef['datatype'],
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

    def process_licor(self):

        # If there is a saildrone file, then that has the cycle header
        # information.
        src_file = self.src_dir / core.SAILDRONE_NCFILE
        if src_file.exists():

            with SailDroneLicor(
                src_file, self.dst_dir, verbosity=self.verbosity
            ) as o:
                o.run()

        else:
            self.process_licor_text()

    def process_licor_text(self):

        if all(not src_ncfile.exists() for src_ncfile in [
            self.src_dir / ncfile for ncfile in core.licor.NCFILES
        ]):
            # no LICOR files, so don't do anything
            return

        for src_ncfile in [
            self.src_dir / ncfile for ncfile in core.licor.NCFILES
        ]:

            dst_ncfile = self.dst_dir / f"{src_ncfile.stem}.nc"

            with LicorProcessor(src_ncfile, dst_ncfile, reduce=self.mapco2_licor_reduce) as p:
                p.run()
        self.logger.info(f"Licor reduction method: {self.mapco2_licor_reduce}.")

    def process_sbe16(self):
        """
        If we have site ID and deployment number information, we can try
        to reduce the SBE16 file.  Otherwise we just decline to do anything.
        The reason for this is that we need to know what the channels mean
        before it makes any sense to do anything with them.
        """
        # Sometimes there is no SBE16 file, so there is nothing to do.
        src_ncfile = self.src_dir / core.SBE16_NCFILE
        if not src_ncfile.exists():
            return

        dst_ncfile = self.dst_dir / f"{src_ncfile.stem}.nc"

        if not self.sbe16_mapping:
            self.logger.warning("SBE16 processing disabled")
            return

        # we need longitude, pressure and ssst data in order to process sbe16
        mapco2_ncfile = self.dst_dir / core.CYCLE_HEADER_NCFILE
        pressure_ncfile = self.dst_dir / core.licor.EPOFF_NCFILE
        met_ncfile = self.dst_dir / core.MET_NCFILE
        with SBE16Processor(
            src_ncfile, dst_ncfile, mapco2_ncfile, pressure_ncfile,
            met_ncfile, **self.kwargs
        ) as p:
            p.run()

    def process_historical(self):
        """
        Take a netCDF file of historical data and copy it to the next stage.
        """
        # Sometimes (usually) there is no external SBE63 file, so there is
        # nothing to do.
        src_ncfile = self.src_dir / core.HISTORICAL_NCFILE
        if not src_ncfile.exists():
            return

        dst_ncfile = self.dst_dir / core.HISTORICAL_NCFILE

        msg = f"Reducing {src_ncfile} to {dst_ncfile}"
        self.logger.info(msg)

        shutil.copyfile(src_ncfile, dst_ncfile)

    def process_external_sbe63(self):
        """
        Take a netCDF file of raw sbe63 data derived from an external source
        and process it to the reduced stage.
        """
        # Sometimes (usually) there is no external SBE63 file, so there is
        # nothing to do.
        src_ncfile = self.src_dir / core.EXTERNAL_SBE63_NCFILE
        if not src_ncfile.exists():
            return

        dst_ncfile = self.dst_dir / core.EXTERNAL_SBE63_NCFILE

        with ExternalSBE63Processor(src_ncfile, dst_ncfile) as p:
            p.run()

    def process_external_met(self):
        """
        Take a netCDF file of raw met data derived from an external source and
        process it.
        """
        # Sometimes (usually) there is no external MET file, so there is
        # nothing to do.
        src_ncfile = self.src_dir / core.EXTERNAL_MET_NCFILE
        if not src_ncfile.exists():
            return

        dst_ncfile = self.dst_dir / core.EXTERNAL_MET_NCFILE

        with ExternalMetProcessor(src_ncfile, dst_ncfile) as p:
            p.run()

    def process_met(self):
        """
        Take a netCDF file of raw met data and process it.  We also wish to
        produce a CSV file with SSS data.
        """

        # Sometimes there is no MET file, so there is nothing to do.
        src_ncfile = self.src_dir / core.MET_NCFILE
        if not src_ncfile.exists():
            return

        dst_ncfile = self.dst_dir / core.MET_NCFILE

        with MetProcessor(src_ncfile, dst_ncfile) as p:
            p.run()

        # Process the MET to CSV as well.  Do this for work with SAMI.
        ncfile = self.dst_dir / core.MET_NCFILE
        csvfile = self.dst_dir / 'met.csv'
        with xr.open_dataset(ncfile) as ds:
            df = ds.to_dataframe()
            df.to_csv(csvfile)

            msg = f"Constructing CSV file {csvfile} for SAMI consumption..."
            self.logger.info(msg)

    def process_sami(self):
        """
        Take a netCDF file of raw sami hex data and process it.
        """

        # sami data might either come from mapco2 text file or from an
        # externally produced CSV file.
        src_ncfile = self.src_dir / core.EXTERNAL_SAMI_NCFILE
        if src_ncfile.exists():

            dst_ncfile = self.dst_dir / f"{src_ncfile.stem}.nc"

            with ExternalSamiProcessor(src_ncfile, dst_ncfile) as p:
                p.run()

        src_ncfile = self.src_dir / core.SAMI_NCFILE
        if src_ncfile.exists():

            dst_ncfile = self.dst_dir / f"{src_ncfile.stem}.nc"

            # We may wish to use the met salinity, if it is available.
            met_ncfile = self.dst_dir / core.MET_NCFILE
            if not met_ncfile.exists():
                met_ncfile = None

            with SamiProcessor(
                src_ncfile, dst_ncfile, met_ncfile=met_ncfile
            ) as p:
                p.run()

    def process_prawler_ctd(self):
        """
        Take a netCDF file of raw prawler ctd data and process it.
        """

        # Sometimes there is no prawler ctd file, so there is nothing to do.
        src_ncfile = self.src_dir / core.PRAWLER_CTD_NCFILE
        if not src_ncfile.exists():
            return

        dst_ncfile = self.dst_dir / f"{src_ncfile.stem}.nc"

        with PrawlerCTDProcessor(src_ncfile, dst_ncfile) as p:
            p.run()

    def process_seafet(self):
        """
        Take a netCDF file of raw seafet data and process it.
        """

        # Sometimes there is no seafet file, so there is nothing to do.
        src_ncfile = self.src_dir / core.SEAFET_NCFILE
        if src_ncfile.exists():
            dst_ncfile = self.dst_dir / f"{src_ncfile.stem}.nc"
            with SeafetProcessor(src_ncfile, dst_ncfile) as p:
                p.run()

        src_ncfile = self.src_dir / core.EXTERNAL_SEAFET_NCFILE
        if src_ncfile.exists():
            dst_ncfile = self.dst_dir / f"{src_ncfile.stem}.nc"
            with SeafetProcessor(src_ncfile, dst_ncfile) as p:
                p.run()

    def process_durafet(self):
        """
        Take a netCDF file of raw durafet data and process it.
        """

        # Sometimes there is no seafet file, so there is nothing to do.
        src_ncfile = self.src_dir / core.DURAFET_NCFILE
        if not src_ncfile.exists():
            return

        dst_ncfile = self.dst_dir / f"{src_ncfile.stem}.nc"

        with DurafetProcessor(src_ncfile, dst_ncfile) as p:
            p.run()


class LicorProcessor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    """
    def __init__(self, src_ncfile, dst_ncfile, reduce=core.REDUCE_MEAN):
        super().__init__(src_ncfile, dst_ncfile, reduce=reduce)

        self.nc_variable_defs = core.vardefs.data_dict['licor']

    def run(self):
        msg = f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.transfer_coordinate_variables()
            self.process_LICOR()

    def process_LICOR(self):

        # apparently we skip that first measurement
        data = self.src_nc['li'][:, 1:, :]

        # Li is broken down into five variables
        #
        # xCO2, temp, press, count1, count2

        # xCO2 is the 1st variable, must be scaled.
        raw_data = data[:, :, 0] / 100
        mean, stddev, qc = self.reduce(raw_data)
        self.define_netcdf_variable('xco2_wet')
        self.write_netcdf_variable('xco2_wet', mean, qc=qc)

        self.define_netcdf_variable('xco2_wet_stddev')
        self.write_netcdf_variable('xco2_wet_stddev', stddev)

        # temperature is the 2nd variable, must be scaled.
        raw_data = data[:, :, 1] / 100
        mean, _, qc = self.reduce(raw_data)
        self.define_netcdf_variable('temperature')
        self.write_netcdf_variable('temperature', mean, qc=qc)

        # pressure is the 3rd variable, must be scaled.
        raw_data = data[:, :, 2] / 100
        mean, _, qc = self.reduce(raw_data)
        self.define_netcdf_variable('pressure')
        self.write_netcdf_variable('pressure', mean, qc=qc)

        # raw_reference and raw_sample are the 4th and 5th columns,
        # these must NOT be scaled.
        raw_data = data[:, :, 3]
        mean, _, qc = self.reduce(raw_data)
        self.define_netcdf_variable('raw_reference')
        self.write_netcdf_variable('raw_reference', mean, qc=qc)

        raw_data = data[:, :, 4]
        mean, _, qc = self.reduce(raw_data)
        self.define_netcdf_variable('raw_sample')
        self.write_netcdf_variable('raw_sample', mean, qc=qc)

        # Oxygen:  must be scaled
        data = self.src_nc['o2'][:] / 100.0
        mean, _, qc = self.reduce(data)
        self.define_netcdf_variable('o2')
        self.write_netcdf_variable('o2', mean, qc=qc)

        # RH:  must be scaled
        data = self.src_nc['rh'][:] / 100.0
        mean, stddev, qc = self.reduce(data)
        self.define_netcdf_variable('rh')
        self.write_netcdf_variable('rh', mean, qc=qc)

        # RH std deviation
        self.define_netcdf_variable('rh_stddev')
        self.write_netcdf_variable('rh_stddev', stddev)

        # Rh_temp:  must be scaled
        data = self.src_nc['rh_temp'][:] / 100.0
        mean, stddev, qc = self.reduce(data)
        self.define_netcdf_variable('rh_temp')
        self.write_netcdf_variable('rh_temp', mean, qc=qc)
        self.define_netcdf_variable('rh_temp_stddev')
        self.write_netcdf_variable('rh_temp_stddev', stddev)


class SBE16Processor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    mapco2_ncfile, met_ncfile, pressure_ncfile : str or path
        netCDF files for cycle header, SSST and pressure data
    channel_mapping : pandas.Series
        Maps the channels to concrete variables
    chl_ntu_o2_constants : pandas.Series
        TBD
    """
    def __init__(
        self, src_ncfile, dst_ncfile, mapco2_ncfile, pressure_ncfile,
        met_ncfile, chl_channel=0, ntu_channel=1, o2_channel=2,
        o2_temp_channel=3,
        chl_scale_factor=[10],
        chl_dark_count=[0.06],
        ntu_scale_factor=[5],
        ntu_dark_count=[0.06],
        o2_salinity_setting=[0],
        chl_global_conversion=1,
        instrument_time_split=None
    ):

        super().__init__(
            src_ncfile, dst_ncfile, reduce=core.REDUCE_MEDIAN
        )
        self.logger = logging.getLogger('xco2qc.reduce')

        self.pressure_ncfile = pressure_ncfile
        self.met_ncfile = met_ncfile
        self.mapco2_ncfile = mapco2_ncfile

        self.config['QC']['chl_channel'] = chl_channel
        self.config['QC']['ntu_channel'] = ntu_channel
        self.config['QC']['o2_channel'] = o2_channel
        self.config['QC']['o2_temp_channel'] = o2_temp_channel

        self.config['QC']['chl_scale_factor'] = chl_scale_factor
        self.config['QC']['chl_dark_count'] = chl_dark_count
        self.config['QC']['ntu_scale_factor'] = ntu_scale_factor
        self.config['QC']['ntu_dark_count'] = ntu_dark_count
        self.config['QC']['chl_global_conversion'] = chl_global_conversion
        self.config['QC']['o2_salinity_setting'] = o2_salinity_setting

        if instrument_time_split is None:
            self.instrument_time_split = []
        else:
            if isinstance(instrument_time_split, dt.datetime):
                self.instrument_time_split = [instrument_time_split]
            else:
                # already a list?
                if len(instrument_time_split) > 1:
                    msg = (
                        "More than one instrument time split is not currently "
                        "allowed."
                    )
                    raise RuntimeError(msg)

                self.instrument_time_split = instrument_time_split

        # We want to bracket the time splits with a value before the start
        # of processing and a value after the end of processing.  This allows
        # us to process ALL of the data with one code block.
        #
        # Ensure they are all pandas timestamps
        with xr.open_dataset(self.src_ncfile) as ds:
            b0 = pd.Timestamp(ds['time'].values[0]) - dt.timedelta(seconds=1)
            self.instrument_time_split.insert(0, b0)

            b1 = pd.Timestamp(ds['time'].values[-1]) + dt.timedelta(seconds=1)
            self.instrument_time_split.append(b1)

            self.instrument_time_split = [
                pd.Timestamp(item) for item in self.instrument_time_split
            ]

        self.data_vars = [
            'current', 'density', 'voltage'
        ]

        self.nc_variable_defs = core.vardefs.data_dict['sbe16']

    def run(self):

        if not self.met_ncfile.exists():
            msg = "There is no salinity / temperature data available."
            self.logger.warning(msg)
            return

        msg = (
            f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        )
        self.logger.info(msg)

        self.setup_pressure()
        self.setup_met()

        self.transfer_coordinate_variables()
        self.process_channel_variables()
        self.add_nighttime()
        self.compute_o2_percent_sat()
        self.process_density_voltage_current()

        # we may have new chl parameters
        self._save_config()

    def setup_pressure(self):
        """
        Index the pressure data to the SBE16 data, convert to decibars
        """

        # index the pressure data to the sbe16 data
        with xr.open_dataset(self.src_ncfile) as ds_sbe16:
            sbe16_index = ds_sbe16[core.TIME].values
            with xr.open_dataset(self.pressure_ncfile) as ds_licor:
                pressure = ds_licor['pressure'].to_series()
                pressure = pressure.reindex(
                    sbe16_index, method='nearest', tolerance='30min'
                )

        # licor pressure is in kPa, convert to decibar
        pressure *= 0.10

        self.pressure = xr.DataArray(
            pressure.values, coords=[pressure.index], dims=['time']
        )

    def setup_met(self):
        """
        index the met data to the sbe16 data
        """
        with xr.open_dataset(self.src_ncfile) as ds_sbe16:
            sbe16_index = ds_sbe16[core.TIME].values
            with xr.open_dataset(self.met_ncfile) as ds_met:
                self.met_df = ds_met.to_dataframe().reindex(
                    sbe16_index, method='nearest', tolerance='30min'
                )

    def transfer_coordinate_variables(self):
        """
        The coordinate variables should never change from level to level.
        """
        # Transfer the coordinate variables (just time for now).  Since these
        # are coordinate variables, they should already be defined in the
        # netcdf file.
        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.dst_nc[core.TIME][:] = self.src_nc[core.TIME][:]

    def process_density_voltage_current(self):

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            # Density, voltage, and current
            for varname in self.data_vars:

                # If the variable is not present in the raw file, then we
                # cannot process it.
                if varname not in self.src_nc.variables.keys():
                    continue

                data = self.src_nc[varname][:]
                mean, _, qc = self.reduce(data)
                self.define_netcdf_variable(varname)
                self.write_netcdf_variable(varname, mean, qc=qc)

    def process_channel_variables(self):
        """
        The channel variables need to be mapped to specific variables.
        """
        with (
            ExitStack() as cm,
            xr.open_dataset(self.src_ncfile) as src_ds
        ):

            # Safely acquire netCDF resources
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            # Channel variables.  These are not always present.
            for channel_num in range(6):

                varname = f"channel_{channel_num}"

                if varname not in self.src_nc.variables.keys():
                    continue

                self.logger.debug(f"processing raw SBE16 {varname}")
                da = src_ds[varname]

                # For the channel data, mask out any zero values.
                # if hasattr(data, 'mask'):
                #     data = np.ma.masked_where(data == 0, data)
                # else:
                #     data = np.where(data == 0, np.nan, data)

                if channel_num == self.config['QC']['chl_channel']:
                    output_varname = 'chl'
                    self.process_chlorophyll(da)
                    msg = f'Processing SBE16 channel {channel_num} into chl'
                    self.logger.info(msg)
                elif channel_num == self.config['QC']['ntu_channel']:
                    output_varname = 'ntu'
                    self.process_ntu(da)
                    msg = f'Processing SBE16 channel {channel_num} into ntu'
                    self.logger.info(msg)
                elif channel_num == self.config['QC']['o2_channel']:
                    output_varname = 'o2'
                    self.process_aanderaa_o2(da)
                    msg = f'Processing SBE16 channel {channel_num} into o2'
                    self.logger.info(msg)
                elif channel_num == self.config['QC']['o2_temp_channel']:
                    output_varname = 'o2_temp'
                    da = da * 9 - 5
                    msg = (
                        f'Processing SBE16 channel {channel_num} into o2_temp'
                    )
                    self.logger.info(msg)
                else:
                    msg = f"channel {channel_num} is unmapped"
                    self.logger.warning(msg)
                    continue

                reduced_data, stddev, qc = self.reduce(da.values)

                # the data...
                self.define_netcdf_variable(output_varname)
                self.write_netcdf_variable(output_varname, reduced_data, qc=qc)

                # and the standard devation ...
                stddev_varname = f"{output_varname}_stddev"
                self.define_netcdf_variable(stddev_varname)
                self.write_netcdf_variable(stddev_varname, stddev)

                self.dst_nc.sync()

    def compute_o2_percent_sat(self):
        """
        Convert optode oxygen (in uM) to % saturation.
        """
        with xr.open_dataset(self.dst_ncfile) as ds:

            if 'o2' not in ds:
                return

            ds = ds.load()
            o2 = ds['o2']

        temperature = self.met_df['SST']
        temperature = temperature.where(temperature >= -298.15, np.nan)

        salinity = self.met_df['SSS']
        salinity = salinity.where(salinity >= 0, np.nan)

        density = seawater_density(temperature, salinity, self.pressure)

        temp_scaled = np.log((298.15 - temperature) / (273.15 + temperature))

        a0, a1, a2, a3, a4, a5 = (
            2.00856, 3.224, 3.99063, 4.80299, 0.978188, 1.71069
        )
        b0, b1, b2, b3 = [-6.24097e-3, -6.93498e-3, -6.90358e-3, -4.29155e-3]
        c0 = -3.1168e-7

        ln_cstar = pd.Series(index=o2['time'], data=np.zeros((len(o2['time']),)))  # noqa : E501
        data = pd.Series(index=o2['time'], data=np.zeros((len(o2['time']),)))

        for idx in range(len(self.instrument_time_split) - 1):

            sal_setting = self.config['QC']['o2_salinity_setting'][idx]

            t0 = self.instrument_time_split[idx]
            t1 = self.instrument_time_split[idx + 1]

            t_scaled = temp_scaled.loc[t0:t1]

            ln_cstar.loc[t0:t1] = (
                a0
                + a1 * t_scaled
                + a2 * t_scaled ** 2
                + a3 * t_scaled ** 3
                + a4 * t_scaled ** 4
                + a5 * t_scaled ** 5
                + sal_setting * (
                    b0
                    + b1 * t_scaled + b2 * t_scaled ** 2
                    + b3 * t_scaled ** 3
                )
                + c0 * sal_setting ** 2
            )

            data.loc[t0:t1] = o2.loc[t0:t1] * (
                (density.loc[t0:t1] / 1000)
                * 2.2414
                / (100 * np.exp(ln_cstar.loc[t0:t1]))
            )

        with ExitStack() as cm:
            # Safely acquire netCDF resources
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.define_netcdf_variable('o2_sat')
            self.write_netcdf_variable('o2_sat', data)

    def add_nighttime(self):
        """
        Calculate night time data.  Right now, this is just chlorophyll and
        NTU.
        """
        # we need the cycle header data, specifically the longitude
        with xr.open_dataset(self.mapco2_ncfile) as ds:
            ds.load()
            longitude = ds['longitude'].to_series()

        with xr.open_dataset(self.dst_ncfile) as ds:
            ds.load()
            df = ds.to_dataframe()

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            vars = [
                'chl',
                'chl_qc',
                'chl_stddev',
                'ntu',
                'ntu_qc',
                'ntu_stddev',
            ]
            if not all(var in df.columns for var in vars):
                msg = (
                    "Missing one or both of chlorophyll and NTU, no nighttime "
                    "products produced."
                )
                self.logger.warning(msg)
                return

            df = df[vars].reset_index()

            df['localtime'] = simple_timezone_offset(
                df[core.TIME], longitude, adjust_hours_only=True
            )

            is_daytime = (
                (df['localtime'].dt.time >= dt.time(3, 10))
                & (df['localtime'].dt.time <= dt.time(20, 50))
            )

            self._add_nighttime(
                df,
                is_daytime,
                'chl',
                'chl_qc',
                'chl_nighttime'
            )

            self._add_nighttime(
                df, is_daytime, 'chl_stddev', None, 'chl_nighttime_stddev'
            )

            self._add_nighttime(
                df,
                is_daytime,
                'ntu',
                'ntu_qc',
                'ntu_nighttime'
            )

            self._add_nighttime(
                df, is_daytime, 'ntu_stddev', None, 'ntu_nighttime_stddev'
            )

    def _add_nighttime(self, df, is_daytime, alldayvar, qcvar, nightvar):

        df[nightvar] = df[alldayvar].copy()
        df.loc[is_daytime, nightvar] = core.DEFAULT_FILLVALUE
        self.define_netcdf_variable(nightvar)

        if qcvar is not None:
            # adjust the qc such that the fill value reflects daytime
            # be sure to clear out the GOOD bit at these points
            qc = df[qcvar].astype(np.uint32)
            qc = np.where(
                is_daytime,
                np.bitwise_or(
                    self.clear_flag(qc, core.quality.GOOD),
                    core.quality.DAYTIME
                ),
                qc
            )
        else:
            # In this case, there's no associated QC variable.
            qc = None

        self.write_netcdf_variable(nightvar, df[nightvar], qc=qc)

    def process_chlorophyll(self, data):

        global_conversion = self.config['QC']['chl_global_conversion']

        for idx in range(len(self.instrument_time_split) - 1):

            scale_factor = self.config['QC']['chl_scale_factor'][idx]
            dark_counts = self.config['QC']['chl_dark_count'][idx]

            t0 = self.instrument_time_split[idx]
            t1 = self.instrument_time_split[idx + 1]

            data.loc[t0:t1, :] = (
                scale_factor
                / (1 + global_conversion)
                * (data.loc[t0:t1, :] - dark_counts)
            )

    def process_ntu(self, data):

        for idx in range(len(self.instrument_time_split) - 1):

            scale_factor = self.config['QC']['ntu_scale_factor'][idx]
            dark_counts = self.config['QC']['ntu_dark_count'][idx]

            t0 = self.instrument_time_split[idx]
            t1 = self.instrument_time_split[idx + 1]

            data.loc[t0:t1, :] = scale_factor * (data.loc[t0:t1, :] - dark_counts)  # noqa : E501

    def process_aanderaa_o2(self, data):
        data *= 100

        temp = self.met_df['SST']
        sal = self.met_df['SSS']
        density = seawater_density(temp, sal, self.pressure)
        density = xr.DataArray(
            density.values, coords=[density.index], dims=['time']
        )

        for idx in range(len(self.instrument_time_split) - 1):

            sal_setting = self.config['QC']['o2_salinity_setting'][idx]

            t0 = self.instrument_time_split[idx]
            t1 = self.instrument_time_split[idx + 1]

            data.loc[t0:t1, :] = self.salinity_compensation(
                data.loc[t0:t1, :], temp[t0:t1], sal[t0:t1], sal_setting
            )
            data.loc[t0:t1, :] = self.pressure_compensation(
                data.loc[t0:t1, :], self.pressure.loc[t0:t1]
            )

            # convert umol/l to umol/kg for submission
            data.loc[t0:t1, :] = (data.T * 1. / (density.loc[t0:t1] / 1000)).T

    def pressure_compensation(self, data, pressure):
        """
        Compensate for pressure effects on the optode foil.
        """
        data *= (1 + 0.032 * pressure / 1000)
        return data

    def salinity_compensation(self, data, temp, sal, sal_setting):
        """
        Compensate measured Optode O2 for salinity and temperature

        Parameters
        ----------
        sal_setting : float
            (PSU) internal salinity setting of Optode, normally zero

        Returns
        -------
        array-like (uM/L)
        """
        B0, B1, B2, B3 = [-6.24097e-3, -6.93498e-3, -6.90358e-3, -4.29155e-3]
        C0 = -3.11680e-7

        temperature = temp.where(temp >= -298.15, np.nan)
        salinity = sal.where(sal >= 0, np.nan)

        t_scaled = np.log((298.15 - temperature) / (273.15 + temperature))
        sal_comp = np.exp(
            (salinity - sal_setting)
            * (B0 + B1 * t_scaled + B2 * t_scaled ** 2 + B3 * t_scaled ** 3)
            + C0 * (salinity ** 2 - sal_setting ** 2)
        )

        data = (data.T * sal_comp.values).T
        return data


class PrawlerCTDProcessor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    """
    def __init__(self, src_ncfile, dst_ncfile):
        super().__init__(src_ncfile, dst_ncfile)

        self.nc_variable_defs = core.vardefs.data_dict['prawler_ctd']

    def run(self):
        msg = (
            f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        )
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.process_prawler_ctd()

    def process_prawler_ctd(self):
        """
        Prawler CTD seems pretty easy, all we do is take the mean?
        """

        with xr.open_dataset(self.src_ncfile) as ds:
            data = {}
            for name in [
                'temperature',
                'conductivity',
                'pressure'
            ]:
                data[name] = ds[name].mean(axis=1)

            df_mean = pd.DataFrame(index=ds.time.to_index(), data=data)

        # compute salinity.  If conductivity is S/m, we have to convert to
        # mS/cm (multiply by 10).  If pressure is kPa, we have to convert to
        # dbar (divide by 10).
        df_mean['salinity'] = gsw.SP_from_C(
            df_mean['conductivity'].copy() * 10,
            df_mean['temperature'].copy(),
            df_mean['pressure'].copy() * 0.1
        )

        # Must turn the time into seconds since 1970.
        s = df_mean.reset_index()[core.TIME]
        seconds = (s - self.time_base.replace(tzinfo=None)).dt.total_seconds()
        self.write_netcdf_variable(core.TIME, seconds)

        for varname in df_mean.columns:

            self.define_netcdf_variable(varname)
            self.write_netcdf_variable(varname, df_mean[varname])


class DurafetProcessor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    """
    def __init__(self, src_ncfile, dst_ncfile):
        super().__init__(src_ncfile, dst_ncfile)

        self.nc_variable_defs = core.vardefs.data_dict['durafet']

    def run(self):
        msg = (
            f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        )
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            with xr.open_dataset(self.src_ncfile) as ds:
                df = ds.to_dataframe()

            # All of the variables here are already just simple time series.

            # Must turn the time into seconds since 1970.
            s = df.reset_index()[core.TIME]
            seconds = (s - self.time_base.replace(tzinfo=None)).dt.total_seconds()  # noqa : E501
            self.write_netcdf_variable(core.TIME, seconds)

            for varname in df.columns:

                if varname == 'durafet_time':
                    # For some reason this causes CF to not be able to read
                    # the file.  Skip this variable for now.
                    continue

                self.define_netcdf_variable(varname)
                self.write_netcdf_variable(varname, df[varname])


class SeafetProcessor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    """
    def __init__(self, src_ncfile, dst_ncfile):
        super().__init__(src_ncfile, dst_ncfile)

        self.nc_variable_defs = core.vardefs.data_dict['seafet']

    def run(self):
        msg = (
            f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        )
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.process_seafet()

    def process_seafet(self):

        with xr.open_dataset(self.src_ncfile) as ds:
            df = ds.to_dataframe()

        df_mean = df.groupby('time').mean(numeric_only=True)

        # Must turn the time into seconds since 1970.
        s = df_mean.reset_index()['time']
        seconds = (s - self.time_base.replace(tzinfo=None)).dt.total_seconds()
        self.write_netcdf_variable('time', seconds)

        for varname in df_mean.columns:

            # skip these two for now, they don't make sense as averaged
            if varname in ['status', 'check_sum']:
                continue

            self.define_netcdf_variable(varname)
            self.write_netcdf_variable(varname, df_mean[varname])


class ExternalSamiProcessor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    """
    def __init__(self, src_ncfile, dst_ncfile):
        super().__init__(src_ncfile, dst_ncfile)

        self.nc_variable_defs = core.vardefs.data_dict['external_sami']

    def run(self):
        msg = (
            f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        )
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.transfer_coordinate_variables()
            self.process_sami()

    def process_sami(self):
        """
        For the most part, just copy the data from the source netCDF file to
        the destination netCDF file.  The only exception is the flag variable.
        """

        with xr.open_dataset(self.src_ncfile) as ds:
            df = ds.to_dataframe()

        self.define_netcdf_variable('SSS')
        self.write_netcdf_variable('SSS', df['SSS'])

        self.define_netcdf_variable('temperature')
        self.write_netcdf_variable(
            'temperature', df['temperature']
        )

        self.define_netcdf_variable('ph')
        self.write_netcdf_variable('ph', df['ph'])

        self.define_netcdf_variable('ph_err')
        self.write_netcdf_variable('ph_err', df['ph_err'])

        self.define_netcdf_variable('external_flag')
        self.write_netcdf_variable(
            'external_flag', df['external_flag']
        )


class SamiProcessor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    met_ncfile : str or path
        The netCDF file for the met data, if it exists.
    """
    def __init__(self, src_ncfile, dst_ncfile, met_ncfile=None):
        super().__init__(src_ncfile, dst_ncfile)

        self.met_ncfile = met_ncfile

        self.nc_variable_defs = core.vardefs.data_dict['sami']

    def run(self):
        msg = (
            f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        )
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.transfer_coordinate_variables()
            self.process_sami()

    def process_sami(self):

        # get the raw sami hex strings
        with xr.open_dataset(self.src_ncfile) as ds:
            sami_hex = ds['hex_string'].to_series()

        if self.met_ncfile is not None:

            with netCDF4.Dataset(self.met_ncfile) as nc:
                fill_value = nc['SSS'].getncattr('_FillValue')

            with xr.open_dataset(self.met_ncfile) as ds:

                # align the salinity with the sami data.
                salinity = ds['SSS'].to_series().reindex(
                    sami_hex.index, method='nearest', tolerance='30min',
                    fill_value=fill_value
                )

        else:
            # Fall back to a default value of 35 for all salinity values
            salinity = pd.Series([35] * len(sami_hex), index=sami_hex.index)

        df = sami.process_sami_strings(sami_hex, salinity)

        self.define_netcdf_variable('temperature')
        self.write_netcdf_variable(
            'temperature', df['temperature']
        )

        self.define_netcdf_variable('ph')
        self.write_netcdf_variable(
            'ph', df['ph'], qc=df['ph_qc']
        )

        self.define_netcdf_variable('slope')
        self.write_netcdf_variable('slope', df['slope'])

        self.define_netcdf_variable('r2')
        self.write_netcdf_variable('r2', df['r2'])

        self.define_netcdf_variable('battery')
        self.write_netcdf_variable('battery', df['battery'])

        # Have to post process the sami hex time a bit, to seconds since the
        # epoch.  We also have to be carefull of any uninitialized values.
        fv = self.nc_variable_defs['sami_time']['fill_value']
        s = pd.Series(np.full((len(df),), fv))
        if df['sami_time'].isnull().sum() < len(df):
            s = s.where(
                df['sami_time'].isnull(),
                (df['sami_time'] - self.time_base).dt.total_seconds()
            )

        self.define_netcdf_variable('sami_time')
        self.write_netcdf_variable('sami_time', s)


class ExternalSBE63Processor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    """
    def __init__(self, src_ncfile, dst_ncfile, reduce=core.REDUCE_MEAN):
        super().__init__(src_ncfile, dst_ncfile, reduce=reduce)

        self.nc_variable_defs = core.vardefs.data_dict['sbe63']

    def run(self):
        msg = (
            f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        )
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.transfer_coordinate_variables()
            self.process_sbe63()

    def process_sbe63(self):

        rawdata = self.src_nc['o2'][:]
        self.define_netcdf_variable('o2')
        self.write_netcdf_variable('o2', rawdata)


class ExternalMetProcessor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    """
    def __init__(self, src_ncfile, dst_ncfile, reduce=core.REDUCE_MEAN):
        super().__init__(src_ncfile, dst_ncfile, reduce=reduce)

        self.nc_variable_defs = core.vardefs.data_dict['met']

    def run(self):
        msg = (
            f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        )
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.transfer_coordinate_variables()
            self.process_met()

    def process_met(self):

        # temperature
        rawdata = self.src_nc['SST'][:]
        self.define_netcdf_variable('SST')
        self.write_netcdf_variable('SST', rawdata)

        # salinity
        rawdata = self.src_nc['SSS'][:]
        self.define_netcdf_variable('SSS')
        self.write_netcdf_variable('SSS', rawdata)


class MetProcessor(DataReductionNetCDFWriter):
    """
    Attributes
    ----------
    src_ncfile, dst_ncfile : str or path
        Source raw netCDF file and destination reduced netCDF file.
    """
    def __init__(self, src_ncfile, dst_ncfile, reduce=core.REDUCE_MEAN):
        super().__init__(src_ncfile, dst_ncfile, reduce=reduce)

        self.nc_variable_defs = core.vardefs.data_dict['met']

    def run(self):
        msg = (
            f"Reducing raw {self.src_ncfile} to {self.dst_ncfile}"
        )
        self.logger.info(msg)

        with ExitStack() as cm:

            # Safely acquire netCDF resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='r+')
            )

            self.transfer_coordinate_variables()
            self.process_met()

    def process_met(self):

        # temperature
        metadata = self.nc_variable_defs['SST']
        rawdata = self.src_nc['sstc'][:, :, 0]
        mean, _, qc = self.reduce(rawdata, metadata=metadata)
        self.define_netcdf_variable('SST')
        self.write_netcdf_variable('SST', mean, qc=qc)

        # conductivity
        metadata = self.nc_variable_defs['conductivity']
        rawdata = self.src_nc['sstc'][:, :, 1]
        mean, _, qc = self.reduce(rawdata, metadata=metadata)
        self.define_netcdf_variable('conductivity')
        self.write_netcdf_variable('conductivity', mean, qc=qc)

        # salinity
        metadata = self.nc_variable_defs['SSS']
        rawdata = self.src_nc['sstc'][:, :, 2]
        mean, _, qc = self.reduce(rawdata, metadata=metadata)
        self.define_netcdf_variable('SSS')
        self.write_netcdf_variable('SSS', mean, qc=qc)
