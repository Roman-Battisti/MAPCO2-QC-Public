"""
Covert raw text files to raw netCDF.  There is no QC done at this level,
just take the raw data and convert it to netCDF.
"""
# standard library imports
import datetime as dt
import importlib.resources as ir
import io
import pathlib
import re
import shutil
import warnings

# 3rd party library imports
import dateutil.parser
import netCDF4
import numpy as np
import pandas as pd
from pandas.api.types import CategoricalDtype
import xarray as xr
import yaml

# local imports
import xco2qc
from . import core
from xco2qc.core.vardefs import data_dict as vardefs
from xco2qc import seafet

MIN_LICOR_MEASUREMENTS = 30


class NoDataForNetCDFError(RuntimeError):
    """
    This exception is raised if we start writing a netCDF file but find that we
    don't have any data for it.
    """
    pass


class TruncatedCycleError(RuntimeError):
    """
    If we run into an unrecoverable error in a cycle, we need to quit,
    discarding the current cycle contents.
    """
    pass


class UnhandledDataStreamError(RuntimeError):
    """
    Raise this exception if we find a datastream that we do not recognize.
    """
    pass


class RawTextToRawNC(core.MapCO2core):
    """
    Convert raw MAPCO2 text file to equivalent "raw" netCDF.  No data
    conversion is performed.

    Attributes
    ----------
    cycle_offset : ndarray
        offsets in bytes from start of file to start of cycle headers
    df : pandas.DataFrame
        dataframe of the cycle header information
    saildrone : object
        If True, then the input was a netCDF file.
    inputfile : str or path
        Path to input raw file
    dst_dir : str or path
        Path to output directory for netCDF files
    deployment_number : int
        Identifies a deployment.  This is currently only needed for cases where
        SBE16 data is to be processed into CHL and NTU.  We need to be able to
        map the channel data, which depends on the deployment number.
    """

    def __init__(
        self, input_path, dst_dir, deployment_number=None,
        require_config_in_output_directory_tree=False, **kwargs
    ):
        """
        Parameters
        ----------
        input_path : str or path
            Path to input raw file
        dst_dir : str or path
            Path to output directory for netCDF files
        verbosity : str
            Logging level
        """
        super().__init__(
            dst_dir=dst_dir, logger_name='raw2nc', **kwargs
        )

        self.inputfile = pathlib.Path(input_path)
        if not self.dst_dir.exists():
            self.dst_dir.mkdir(exist_ok=True, parents=True)

        if self.inputfile.is_dir():
            self.is_saildrone = True
            return
        elif self.is_netcdf_file(self.inputfile):
            # Reset to run on the parent directory.
            self.inputfile = self.inputfile.parents[0]
            self.is_saildrone = True
            return
        else:
            self.f = self.inputfile.open(mode='rb')
            self.is_saildrone = False

        self.determine_deployment_number(deployment_number)
        self.check_config_file()

        self.time_base = dt.datetime(1970, 1, 1)

    def check_config_file(self):
        """
        If there is a config file in the mapco2 source directory, copy it over
        into the root output directory.  And load it.
        """
        custom_config_path = self.inputfile.parents[0] / 'config.yml'
        if custom_config_path.exists():
            self.logger.info(
                f'Custom config file located at {custom_config_path}.'
            )
            dest_path = self.output_directory_tree_root / 'config.yml'
            shutil.copyfile(custom_config_path, dest_path)

            self.read_config_file()

    def determine_deployment_number(self, deployment_number):
        """
        Don't do this if we have saildrone data?
        """

        if deployment_number is None:
            # Try to parse it out of the filename.  If we see a sequence
            # looking like "..._dpNN_", then that's the clue that there is a
            # deployment number.  The deployment token can optionally come at
            # the beginning of the filename, but if not, it must be preceded
            # by an underscore.
            pattern = r'[\^_]dp(?P<deployment_number>\d{1,2})_'
            regex = re.compile(pattern)
            if m := regex.search(str(self.inputfile)):
                deployment_number = int(m.group('deployment_number'))
                msg = (
                    f'A deployment number of {deployment_number} was taken '
                    'from the file name.'
                )
                self.logger.info(msg)
                self.deployment_number = deployment_number
            else:
                self.logger.info('No deployment number was available.')
                self.deployment_number = None
        else:
            self.deployment_number = deployment_number

    def is_netcdf_file(self, file):
        """
        Is the input source a netCDF file?
        """
        try:
            nc = netCDF4.Dataset(file)
            nc.close()
            return True
        except (ValueError, OSError):
            return False

    def run(self):
        """
        Read, process the raw text file.
        """
        if self.is_saildrone:
            self.run_saildrone()
        else:
            self.run_text()

        self.logger.info("Finished.")

    def run_saildrone(self):
        """
        Concatenate all the saildrone files into one netCDF file.
        """
        src_dir = self.inputfile

        self.define_concatenated_ncfile(src_dir)
        self.concatenate_saildrone_files(src_dir)

    def define_concatenated_ncfile(self, src_dir):
        """
        Define all the netCDF variables and attributes.  Basically it is the
        same as the input saildrone files, but it's not a trajectory netCDF
        file.
        """

        # map the datatypes from the first netCDF file to a string that
        # netCDF4 can understand
        # for more np.dtype info: https://numpy.org/doc/stable/reference/arrays.dtypes.html
        dtype_dict = {
            np.dtype('O'): str,  # vlen string
            np.dtype('float64'): 'f8',
            np.dtype('float32'): 'f8',
            np.dtype('uint32'): 'u4',
            np.dtype('int32'): 'i4',
            np.dtype('<M8[ns]'): 'f8',
            np.dtype('<U6'): str,
        }

        src_ncfiles = sorted(src_dir.glob('*.nc'))

        # Use a single saildrone netCDF file to create the concatenated file
        ds = xr.open_dataset(src_ncfiles[0])
        
        out_ncfile = self.dst_dir / core.SAILDRONE_NCFILE

        with netCDF4.Dataset(out_ncfile, mode='w') as dst_nc:
            dst_nc.createDimension('time', None)

            # loop thru each variable, define them
            for varname in ds:
                # if varname not in ['time', 'latitude', 'longitude']:  # Note, if time, lat, long is a variable in ds, re-creating this dimension will throw an error.
                dtype = dtype_dict.get(ds[varname].dtype, str)
                if dtype == 'f8':
                    fill_value = np.nan
                else:
                    fill_value = None

                ncvar = dst_nc.createVariable(
                    varname, dtype, dimensions=('time',), fill_value=fill_value
                )

                # copy the attributes
                for attr in ds[varname].attrs:
                    value = getattr(ds[varname], attr)
                    setattr(ncvar, attr, value)

                # copy the global attributes
                for attr in ds.attrs:
                    value = getattr(ds, attr)
                    setattr(dst_nc, attr, value)

            # The coordinate variables also need to be defined.
            for varname in ['time', 'latitude', 'longitude']:
                dtype = dtype_dict.get(ds[varname].dtype, str)
                ncvar = dst_nc.createVariable(
                    varname, dtype, dimensions=('time',), fill_value=np.nan
                )

                # copy the attributes
                for attr in ds[varname].attrs:
                    value = getattr(ds[varname], attr)
                    setattr(ncvar, attr, value)

                if varname == 'time':
                    ncvar.units = "seconds since 1970-01-01T00:00:00+00:00"
                    ncvar.calendar = 'gregorian'

                # copy the global attributes
                for attr in ds.attrs:
                    value = getattr(ds, attr)
                    setattr(dst_nc, attr, value)

    def concatenate_saildrone_files(self, src_dir):
        """
        Concatenate all the saildrone netCDF files.
        """

        src_ncfiles = sorted(src_dir.glob('*.nc'))

        out_ncfile = self.dst_dir / core.SAILDRONE_NCFILE

        # now copy all the data
        with netCDF4.Dataset(out_ncfile, mode='a') as dst_nc:
            for src_ncfile in src_ncfiles:

                msg = f"Concatenating {src_ncfile} onto {out_ncfile}"
                self.logger.info(msg)

                with netCDF4.Dataset(src_ncfile) as src_nc:
                    dim = 'obs' if 'obs' in src_nc.dimensions else 'time'
                    src_idx = slice(0, src_nc.dimensions[dim].size)
                    dst_idx = slice(
                        dst_nc.dimensions['time'].size,
                        dst_nc.dimensions['time'].size + src_nc.dimensions[dim].size  # noqa : E501
                    )

                    with warnings.catch_warnings():
                        # There's a UserWarning coming from inside the netCDF4
                        # module due to a missing_value attribute.  That's
                        # outside our control, so silence it.
                        warnings.simplefilter('ignore')
                        for varname in src_nc.variables:
                            if varname == 'trajectory':
                                continue
                            if varname == 'time':
                                pass  # continue
                            # depending on the deployment, they either have shape (x,), (x, 1), or (1, x). Need to check which and slice appropriately
                            if len(src_nc[varname].shape) == 1:
                                dst_nc[varname][dst_idx] = src_nc[varname][src_idx]
                            elif src_nc[varname].shape[0] > src_nc[varname].shape[1]:
                                dst_nc[varname][dst_idx] = src_nc[varname][src_idx, 0]
                            else:
                                dst_nc[varname][dst_idx] = src_nc[varname][0, src_idx]
                            # dst_nc[varname][dst_idx] = src_nc[varname][0, src_idx]  # noqa : E501

    def run_text(self):
        """
        Run the import process on the raw text file.
        """
        self.logger.info(f'Starting to parse {self.inputfile}...')

        self.process_cycle_headers()
        self.process_licor()
        self.process_sbe16()
        self.process_met()
        self.process_sami()
        self.process_seafet()
        self.process_prawler_ctd()
        self.process_durafet()

        # New data source code goes here
        # self.process_shiny_new_data_source()

        self.record_site_id_and_deployment_number_and_system_number()
        self.display_file_sizes()

        self.logger.info(f'Finished with {self.inputfile}...')

    def display_file_sizes(self):

        # Display the new "raw" netCDF files and their sizes.
        for ncfile in sorted(
            self.dst_dir.glob('*.nc'), key=lambda path: path.name
        ):
            kb_size = ncfile.stat().st_size / 1024
            self.logger.info(f"{ncfile.name:25}  {kb_size:8.2f} KB")

        self.logger.info('Finished with raw data conversion..')

    def record_site_id_and_deployment_number_and_system_number(self):
        """
        The site ID and deployment number are pieces of metadata that should
        to travel with each netCDF file thru the processing.  If we don't have
        them, though, all the processing can still occur with the exception
        of SBE16.
        """
        # Validate the site ID before we record it.
        with ir.as_file(ir.files('xco2qc.core.data').joinpath('sites.yml')) as path:
            config = yaml.safe_load(path.open())

        site_id = self.df['site_id'].iloc[0].lower()
        if site_id not in config.keys():
            msg = f'{site_id} was not found in the list of known sites'
            self.logger.warning(msg)

        # Harvest global attributes from the input dataframe.
        # In each case, the columns should never change, so just take the first
        # value.

        # Always record site ID.
        for ncfile in self.dst_dir.glob('*.nc'):
            with netCDF4.Dataset(ncfile, mode='r+') as nc:

                site_id = self.df['site_id'].iloc[0]

                if site_id == 'enrique':
                    # it just is
                    site_id = 'laparguera'

                # site_code is an OceanSITES attribute
                nc.site_code = site_id.upper()

                # site_id is MAPCO2 lingo
                nc.site_id = site_id.lower()

                # We always have the system number
                nc.system_number = self.df['system_number'].iloc[0]

                # Record deployment number, if we have them.
                if self.deployment_number is not None:
                    nc.deployment_number = self.deployment_number
                else:
                    nc.deployment_number = -1

    def process_licor(self):

        self.logger.info("Processing LICOR...")

        records = self.parse_licor_sections()

        # if no records, then do nothing
        if len(records) == 0:
            msg = 'No LICOR data detected, not writing any.'
            self.logger.info(msg)
            return

        pump_modes = set(key for record in records for key in record.keys())
        for pump_mode in pump_modes:
            pump_mode_records = [record[pump_mode] for record in records]
            self.write_licor_records(pump_mode_records, pump_mode)

    def parse_licor_sections(self):
        """
        Parse the raw text file for LICOR data and write it to file.

        Returns
        -------
        list of records, one for each cycle where sbe16 data is present
        """
        records = []

        # Loop through each cycle

        for offset, extent in zip(self.cycle_offset, self.cycle_extent):

            self.f.seek(offset)
            buffer = self.f.read(extent).decode('utf-8', errors='replace')
            sf = io.StringIO(buffer)
            try:
                d = self.parse_licor_section(sf)
            except TruncatedCycleError:
                # Mark the record as bad this way because it's easier to detect
                # when we merge with the header time.
                record = {pumpmode: None for pumpmode in core.licor.PUMP_MODES}
                records.append(record)
            except IndexError:
                # there was no licor section
                pass
            else:
                records.append(d)

        return records

    def parse_sbe16_sections(self):
        """
        Parse the raw text file for SBE16 data

        Returns
        -------
        list of records, one for each cycle where sbe16 data is present
        """

        records = []

        # Loop through each cycle

        for offset, extent in zip(self.cycle_offset, self.cycle_extent):
            self.f.seek(offset)
            buffer = self.f.read(extent).decode('utf-8', errors='replace')
            sf = io.StringIO(buffer)
            d = self.parse_sbe16_section(sf)
            records.append(d)

        return records

    def parse_seafet_sections(self):
        """
        Parse the raw text file for seafet data

        Returns
        -------
        pandas.DataFrame of the seafet data or None
        """

        records = []

        # Loop through each cycle
        for offset, extent, mapco2_timestamp in zip(
            self.cycle_offset, self.cycle_extent, self.df.index
        ):
            self.f.seek(offset)
            text = self.f.read(extent).decode('utf-8', errors='replace')

            df = seafet.process_cycle(text)
            if df is None:
                continue

            # Push the mapco2 time for this cycle into the dataframe
            # It will create duplicates, but this will be critical for the
            # data reduction phase.
            df['time'] = mapco2_timestamp

            records.append(df)

        if len(records) == 0:
            return None

        df = pd.concat(records, axis='rows')

        # reindex the dataframe, otherwise we get multiple index values
        df.index = list(range(len(df)))
        return df

    def parse_sami_sections(self):
        """
        Parse the raw text file for SAMI data

        Returns
        -------
        list of records, one for each cycle where met data is present
        """

        records = []

        # Loop through each cycle

        for offset, extent in zip(self.cycle_offset, self.cycle_extent):
            self.f.seek(offset)
            buffer = self.f.read(extent).decode('utf-8', errors='replace')
            sf = io.StringIO(buffer)
            d = self.parse_sami_section(sf)
            records.append(d)

        return records

    def parse_durafet_sections(self):
        """
        Parse the raw text file for all durafet cycles

        Returns
        -------
        list of records, one for each cycle where durafet data is present
        """

        records = []

        # Loop through each cycle

        for offset, extent in zip(self.cycle_offset, self.cycle_extent):
            self.f.seek(offset)
            buffer = self.f.read(extent).decode('utf-8', errors='replace')
            sf = io.StringIO(buffer)
            d = self.parse_durafet_cycle(sf)
            records.append(d)

        return records

    def parse_prawler_ctd_sections(self):
        """
        Parse the raw text file for all prawler ctd cycles

        Returns
        -------
        list of records, one for each cycle where prawler ctd data is present
        """

        records = []

        # Loop through each cycle

        for offset, extent in zip(self.cycle_offset, self.cycle_extent):
            self.f.seek(offset)
            buffer = self.f.read(extent).decode('utf-8', errors='replace')
            sf = io.StringIO(buffer)
            d = self.parse_prawler_ctd_cycle(sf)
            records.append(d)

        return records

    def parse_met_sections(self):
        """
        Parse the raw text file for MET data

        Returns
        -------
        list of records, one for each cycle where met data is present
        """

        records = []

        # Loop through each cycle

        for offset, extent in zip(self.cycle_offset, self.cycle_extent):
            self.f.seek(offset)
            buffer = self.f.read(extent).decode('utf-8', errors='replace')
            sf = io.StringIO(buffer)
            d = self.parse_met_cycle(sf)
            records.append(d)

        return records

    def process_seafet(self):
        """
        Parse seafet data and write to file
        """
        self.logger.info("Processing SEAFET...")

        records = self.parse_seafet_sections()

        if records is None:
            msg = "No SEAFET data was found."
            self.logger.warning(msg)
            return

        self.write_seafet(records)

    def process_sami(self):
        """
        Parse SAMI data and write to file
        """
        self.logger.info("Processing SAMI...")

        records = self.parse_sami_sections()
        self.write_sami(records)

    def process_durafet(self):
        """
        Parse DURAFET data and write to file
        """
        self.logger.info("Processing DURAFET...")

        records = self.parse_durafet_sections()
        self.write_durafet(records)

    def process_prawler_ctd(self):
        """
        Parse PRAWLER CTD data and write to file
        """
        self.logger.info("Processing PRAWLER CTD...")

        records = self.parse_prawler_ctd_sections()
        self.write_prawler_ctd(records)

    def process_met(self):
        """
        Parse MET data and write to file
        """
        self.logger.info("Processing MetSSTC...")

        records = self.parse_met_sections()
        self.write_met(records)

    def process_sbe16(self):
        """
        Parse SBE16 data and write to file
        """
        self.logger.info("Processing SBE16...")

        records = self.parse_sbe16_sections()
        self.write_sbe16(records)

    def find_and_discard_any_malformed_records(self, records):
        """
        A bad record might announce its presence by being None or by being an
        empty dictionary.  These need to be found and discarded.  The times
        corresponding to these bad records must also be eliminated.

        Returns
        -------
        ts : pandas.Series
            Good values of time retrieved from the mapco2 header
        records : list
            Good records
        """

        df = self.df.index.to_frame()
        df.index = [idx for idx in range(len(df))]

        # find any records that are explicitly None or are empty
        drop_index = [
            idx for idx, record in enumerate(records)
            if record is None or len(record) == 0
        ]

        # drop those items both from the dataframe of cycle header data and
        # from the mapco2 cycle data
        df = df.drop(index=drop_index)
        records = [
            record for idx, record in enumerate(records)
            if idx not in drop_index
        ]

        return df['time'], records

    def write_licor_records(self, records, pumpmode):
        """
        Write Licor data to netCDF file
        """

        ncfile = [file for file in core.licor.NCFILES if pumpmode in file][0]

        ts, records = self.find_and_discard_any_malformed_records(records)

        # Adjust the times from the hour base, not what the original value is.
        # For example, if the time is '2018-08-30T18:30:00' and the offset is
        # 31, then add 31 to 00.
        offsets = [record['offset'].item() for record in records]
        offsets = pd.Series(offsets, index=ts.index)

        ncfile = self.dst_dir / ncfile

        # update the timestamp according to the deltas that we found.  For
        # instance, epoff should (right now) be either 17 or 47 minutes past
        # the cycle header.
        #
        # Round to the hour.
        ts = ts.dt.floor('h')
        ts += pd.to_timedelta(offsets, 'minutes')

        # drop any non-monotonic times.  Do not drop the first.
        idx = (ts.diff().dt.total_seconds() > 0) | (ts.index == 0)
        ts = ts[idx]
        records = [
            record for dt_delta_positive, record in zip(idx, records)
            if dt_delta_positive
        ]

        dups = ts.duplicated()
        ts = ts.drop_duplicates(keep='last')
        records = [record for drop, record in zip(dups, records) if not drop]

        # check for the minimum number of measurements for an individual cycle
        for idx in range(len(records)):
            for param in ['li', 'o2', 'rh', 'rh temp']:

                # Sometimes a parameter is completely missing.  Just skip these
                # for now.  These datums are eventually represented as missing
                # data.
                if param not in records[idx]:
                    continue

                # sometimes a record is completely empty.  just skip these.
                if len(records[idx][param].shape) < 2:
                    continue
                if records[idx][param].size == 0:
                    continue

                num_measurements = records[idx][param].shape[1]
                if num_measurements < MIN_LICOR_MEASUREMENTS:
                    msg = (
                        f'Parameter {param} had {num_measurements} '
                        f'measurements at timestamp {ts[idx]}. The minimum is '
                        f'{MIN_LICOR_MEASUREMENTS}.'
                    )
                    self.logger.warning(msg)
                    warnings.warn(msg)

        global_attrs = {
            "data_source": 'LICOR',
            "pump_mode": pumpmode.replace('-', ' ')
        }

        self.write_raw_netcdf(
            ncfile, records, ts, global_attrs, vardefs['raw_licor']
        )

    def write_raw_seafet_netcdf(self, ncfile, df, global_attrs, vardefs):
        """
        Write the raw data netCDF file for seafet data.
        """

        # if no records, then do nothing
        if len(df) == 0:
            return

        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            nc.createDimension('time', 0)

            # there are two time variables, one for the mapco2 header and one
            # for the seafet records
            vardef = vardefs['time']
            ncvar = nc.createVariable('time', np.int64,
                                      dimensions=('time',),
                                      fill_value=vardef['fill_value'])
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            timedelta = df['time'] - self.time_base
            ncvar[:] = timedelta.dt.total_seconds()

            vardef = vardefs['seafet_time']
            ncvar = nc.createVariable('seafet_time', np.int64,
                                      dimensions=('time',),
                                      fill_value=vardef['fill_value'])
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            timedelta = df['seafet_time'] - self.time_base
            ncvar[:] = timedelta.dt.total_seconds()

            # the rest are pretty straightforward
            # don't bother with the first three, they are taken care of either
            # above or below
            # for varname in core.seafet.LONG_FRAME_COLUMNS[3:]:
            for varname in df.columns:

                if varname in ['header', 'seafet_time', 'time']:
                    # already did these
                    continue

                vardef = vardefs[varname]
                ncvar = nc.createVariable(
                    varname, vardef['datatype'], dimensions=('time',),
                    fill_value=vardef['fill_value']
                )
                for attrname, attrvalue in vardef['attributes'].items():
                    setattr(ncvar, attrname, attrvalue)

                ncvar[:] = df[varname]

            # lastly, fill in the global attributes
            for attr_name, attr_value in global_attrs.items():
                setattr(nc, attr_name, attr_value)

    def write_raw_prawler_ctd_netcdf(
        self, ncfile, records, ts, global_attrs, vardefs
    ):
        """
        The PRAWLER CTD data is pretty uniform, so we don't have to jump thru
        the hoops that we do for other sensors.
        """

        # if no records, then do nothing
        if len(records) == 0:
            msg = 'No PRAWLER CTD data detected, not writing any.'
            self.logger.info(msg)
            return

        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            nc.createDimension('time', 0)

            vardef = vardefs[core.TIME]
            ncvar = nc.createVariable(
                core.TIME, np.int64,
                dimensions=('time',), fill_value=vardef['fill_value']
            )
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            ncvar[:] = (ts - self.time_base).dt.total_seconds()

            # Just three data variables to write, so we will hard code this.

            # Can the maximum sample size for prawler ctd ever vary?
            max_sample_size = np.array([
                record['temperature'].shape[0]
                for record in records
            ]).max()

            nc.createDimension('max_sample_size', max_sample_size)

            # record the 3 variables
            for name in [
                'temperature',
                'pressure',
                'conductivity'
            ]:
                data = np.vstack([record[name] for record in records])

                metadata = vardefs[name]
                ncvar = nc.createVariable(
                    name, metadata['datatype'],
                    dimensions=('time', 'max_sample_size'),
                    fill_value=metadata['fill_value'],
                )

                for attrname, attrvalue in metadata['attributes'].items():
                    setattr(ncvar, attrname, attrvalue)

                ncvar[:] = data

            # lastly, fill in the global attributes
            for attr_name, attr_value in global_attrs.items():
                setattr(nc, attr_name, attr_value)

    def write_raw_sami_netcdf(
        self, ncfile, records, ts, global_attrs, vardefs
    ):

        # if no records, then do nothing
        if len(records) == 0:
            msg = 'No SAMI data detected, not writing any.'
            self.logger.info(msg)
            return

        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            nc.createDimension('time', 0)

            vardef = vardefs['time']
            ncvar = nc.createVariable('time', np.int64,
                                      dimensions=('time',),
                                      fill_value=vardef['fill_value'])
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            ncvar[:] = (ts - self.time_base).dt.total_seconds()

            # Just two data variables to write, so we will hard code this.  The
            # sami hex strings are a bit of a different animal than the numeric
            # data anyway.
            metadata = vardefs['hex_string']

            data = np.empty((len(records),), 'O')
            for j in range(len(records)):
                data[j] = records[j]['hex_string']

            # we will store the sami hex strings as VLEN strings since the
            # length can seemingly be either 455 or 465.
            metadata = vardefs['hex_string']
            ncvar = nc.createVariable('hex_string', str, dimensions=('time',))

            for attrname, attrvalue in metadata['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            ncvar[:] = data

            # and now for the sami time
            metadata = vardefs['sami_time']
            vardata = tuple(record['sami_time'] for record in records)
            s = pd.Series(vardata)

            # To be consistent with the rest of our time variables, convert
            # the data into seconds since the epoch.
            data = (s - self.time_base).dt.total_seconds()
            data = data.fillna(metadata['fill_value'])
            data = data.astype(metadata['datatype'])

            ncvar = nc.createVariable(
                'sami_time', metadata['datatype'],
                dimensions=('time',),
                fill_value=metadata['fill_value'],
            )

            for attrname, attrvalue in metadata['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            ncvar[:] = data

            # lastly, fill in the global attributes
            for attr_name, attr_value in global_attrs.items():
                setattr(nc, attr_name, attr_value)

    def write_raw_netcdf(self, ncfile, records, ts, global_attrs, vardefs):

        # It's possible there was no data.  If so, then do nothing.
        #
        # Look thru the variables in each record, look specifically for a
        # sample count variable.  If that item is 0 for each such sample count,
        # then don't record any data.
        if all(
            record[varname].item() == 0
            for record in records for varname in record
            if varname.endswith('_sample_count')
        ):
            self.logger.warning('No data was found, no data was written...')
            return

        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            nc.createDimension('time', 0)

            vardef = vardefs[core.TIME]
            ncvar = nc.createVariable(
                core.TIME, np.int64,
                dimensions=('time',),
                fill_value=vardef['fill_value']
            )
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            ncvar[:] = (ts - self.time_base).dt.total_seconds()

            # do not write the sample counts.  That information becomes
            # implicit when you look at the raw data in the netCDF file, i.e.
            # if a data record is [1, 2, nan, nan] then the sample count was
            # probably 2.
            #
            # offset is already being folded into the time variable,
            # so no need to store it again
            vars = set(
                var for record in records
                for var in record.keys()
                if var != 'offset' and not var.endswith('sample_count')
            )
            for varname in vars:
                self.logger.debug(f'Writing {varname} into {ncfile}')

                # We can't have spaces in the names.
                name = varname.replace(' ', '_')

                metadata = vardefs[name]

                # If a variable is missing from one record, insert an empty
                # array so that we can attempt to salvage it.
                for record in records:
                    if varname not in record:
                        if name.endswith('_sample_count'):
                            record[varname] = np.array([0])
                        else:
                            ndims = len(metadata['dimensions'])
                            shape = [0 for _ in range(ndims)]
                            record[varname] = np.zeros(shape)

                # If there is no data at all for this variable, then skip it,
                # because we don't have enough information to write it.
                if all(record[varname].size == 0 for record in records):
                    continue

                vardata = tuple(record[varname] for record in records)
                try:
                    data = np.concatenate(vardata)
                except ValueError:
                    # some of the records must have differing numbers of
                    # observations, we need to fill in the gaps
                    self.fill_in_missing_data(records, varname, metadata)
                    vardata = tuple(record[varname] for record in records)
                    data = np.concatenate(vardata)

                # create the dimension for the number of measurements per
                # cycle.  certain variables are just 1D though
                if not name.endswith('_sample_count'):

                    n_measurements_per_cycle = data.shape[1]
                    dimname = f"{name}_max_sample_size"
                    nc.createDimension(dimname, n_measurements_per_cycle)

                if varname == 'sstc':
                    # an additional dimension is needed.
                    nc.createDimension('num_sstc_params', data.shape[2])
                elif varname == 'gtd':
                    nc.createDimension('gtd_sample', 2)
                elif varname == 'li':
                    # raw LICOR
                    # an additional dimension is needed, length of 5?
                    nc.createDimension('num_li_vars', data.shape[2])

                ncvar = nc.createVariable(
                    name, metadata['datatype'],
                    dimensions=metadata['dimensions'],
                    fill_value=metadata['fill_value']
                )

                data = np.nan_to_num(data, nan=metadata['fill_value'])

                ncvar[:] = data

            for attr_name, attr_value in global_attrs.items():
                setattr(nc, attr_name, attr_value)

    def write_sbe16(self, records):
        """
        Write SBE16 data to netCDF file
        """
        ncfile = self.dst_dir / core.SBE16_NCFILE

        ts, records = self.find_and_discard_any_malformed_records(records)

        # SBE16 measurements start 6 minutes and 45 seconds after the beginning
        # of each cycle
        ts = ts.copy() + dt.timedelta(seconds=405)

        global_attrs = {'data_source': "SBE16"}
        self.write_raw_netcdf(
            ncfile, records, ts, global_attrs, vardefs['raw_sbe16']
        )

    def write_seafet(self, df):
        """
        Write SEAFET data to netCDF file
        """
        ncfile = self.dst_dir / core.SEAFET_NCFILE

        # not only should we identify the data_source as seafet, the seafet
        # header might be important
        global_attrs = {
            'data_source': 'SEAFET',
            'seafet_header': df.loc[0, 'header']
        }

        self.write_raw_seafet_netcdf(
            ncfile, df, global_attrs, vardefs['seafet']
        )

    def write_sami(self, records):
        """
        Write SAMI data to netCDF file
        """
        ncfile = self.dst_dir / core.SAMI_NCFILE

        ts, records = self.find_and_discard_any_malformed_records(records)

        global_attrs = {'data_source': 'SAMI'}

        self.write_raw_sami_netcdf(
            ncfile, records, ts, global_attrs, vardefs['raw_sami']
        )

    def write_met(self, records):
        """
        Write MET data to netCDF file
        """
        ncfile = self.dst_dir / core.MET_NCFILE

        ts, records = self.find_and_discard_any_malformed_records(records)

        global_attrs = {'data_source': 'MET'}
        self.write_raw_netcdf(
            ncfile, records, ts, global_attrs, vardefs['raw_met']
        )

    def write_durafet(self, records):
        """
        Write Durafet data to netCDF file
        """
        ncfile = self.dst_dir / core.DURAFET_NCFILE

        ts, records = self.find_and_discard_any_malformed_records(records)

        # if no records, then do nothing
        if len(records) == 0:
            msg = 'No DURAFET data detected, not writing any.'
            self.logger.info(msg)
            return

        durafet_vardefs = vardefs['raw_durafet']
        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            nc.createDimension('time', 0)

            # this is the mapco2 header time
            vardef = durafet_vardefs[core.TIME]
            ncvar = nc.createVariable(core.TIME, np.int64,
                                      dimensions=('time',),
                                      fill_value=vardef['fill_value'])
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            ncvar[:] = (ts - self.time_base).dt.total_seconds()

            # this is the time embedded in the durafet section
            vardef = durafet_vardefs['durafet_time']
            ncvar = nc.createVariable('durafet_time', np.int64,
                                      dimensions=('time',),
                                      fill_value=vardef['fill_value'])
            for attrname, attrvalue in vardef['attributes'].items():
                setattr(ncvar, attrname, attrvalue)

            # Assemble the durafet time into an array, take the offset since
            # the epoch.
            data = np.vstack([record['DURAFET_TIME'] for record in records])
            s = pd.Series((data - self.time_base).ravel())
            ncvar[:] = s.dt.total_seconds()

            # record the variables
            for name in [
                'temperature',
                'temperature_voltage',
                'pressure',
                'battery',
                'fet_int',
                'fet_ext',
                'isolated_power',
                'controller_temp',
                'ph_int',
                'ph_ext',
            ]:
                data = np.vstack([record[name.upper()] for record in records])

                metadata = durafet_vardefs[name]
                ncvar = nc.createVariable(
                    name, metadata['datatype'],
                    dimensions=('time', ), fill_value=metadata['fill_value'],
                )

                for attrname, attrvalue in metadata['attributes'].items():
                    setattr(ncvar, attrname, attrvalue)

                ncvar[:] = data

            # lastly, fill in the global attributes
            setattr(nc, 'data_source', 'DURAFET')

    def write_prawler_ctd(self, records):
        """
        Write Prawler CTD data to netCDF file
        """
        ncfile = self.dst_dir / core.PRAWLER_CTD_NCFILE

        ts, records = self.find_and_discard_any_malformed_records(records)

        global_attrs = {'data_source': 'PRAWLER CTD'}
        self.write_raw_prawler_ctd_netcdf(
            ncfile, records, ts, global_attrs, vardefs['raw_prawler_ctd']
        )

    def fill_in_missing_data(self, records, varname, metadata):

        # Ok, some data may not be the right size.
        shapes = [record[varname].shape for record in records]
        ndim = max(len(record[varname].shape) for record in records)

        if ndim == 2:
            maxshape = (
                1,
                max(shape[1] for shape in shapes if len(shape) == 2),
            )
        else:
            maxshape = (
                1,
                max(shape[1] for shape in shapes if len(shape) == 3),
                max(shape[2] for shape in shapes if len(shape) == 3),
            )

        for record in records:
            if record[varname].shape != maxshape:

                data = np.full(maxshape,
                               metadata['fill_value'],
                               dtype=record[varname].dtype)

                if record[varname].size == 0:
                    # No samples to be read?  Ok, then the entire buffer is
                    # just fill values, which we have already created.
                    pass
                elif record[varname].ndim > 2:
                    n = record[varname].shape[1]
                    data[0, :n, :] = record[varname]
                else:
                    n = record[varname].shape[1]
                    data[0, :n] = record[varname]

                record[varname] = data

    def parse_sami_section(self, f):
        """
        Read the entire sAMI section
        numeric array.

        The format of the data is

         Sami Data
        PH
        0000/00/00 00:00:00
        00000000000000000000000000000000000000000000000000000 ...
        00000000000000000000000000000000000000000000000000000 ...
        00000000000000000000000000000000000000000000000000000 ...
        00000000000000000000000000000000000000000000000000000 ...
        00000000000000000000000000000000000000000000000000000 ...
        00000000000000000000000000000000000000000000000000000 ...
        END PH

        Returns
        -------
        dictionary of data parsed out of the current section
        """

        d = {}

        # first we locate the sami banner lines
        h1_reached = h2_reached = False
        line = f.readline()
        while len(line) > 0:

            if line.startswith(' Sami Data'):
                h1_reached = True

            if line.startswith('PH') and h1_reached:
                h2_reached = True
                # Now we know that the next line will contain the SAMI date
                break

            line = f.readline()

        if not h2_reached:
            self.logger.debug('No sami data located in current cycle.')
            return d

        self.logger.debug("Detected sami banner...")

        # next line contains the date
        line = f.readline()
        try:
            d['sami_time'] = dateutil.parser.parse(line)
        except dateutil.parser.ParserError:
            d['sami_time'] = pd.NaT

        lines = []
        while True:
            line = f.readline()
            if len(line) == 0 or line.startswith('END PH'):
                # if the line length is zero, that's bad.  we probably have
                # a malformed sami section.
                break

            if line.startswith('^0A'):
                # garbage characters?
                line = line[4:]

            # strip off any trailing whitespace
            lines.append(line.strip())

        d['hex_string'] = ''.join(lines)

        return d

    def parse_durafet_cycle(self, f):
        """
        Read the entire durafet cycle, convert the raw values to a single
        numeric array.

        The format of the data is

        **************************************** Durafet Data pump time 0000
          2017/08/23 01:47:09 11.6 0.9 0.07 -0.9 5.7 25.6 25.2 -8.6 7.9 7.9

        Returns
        -------
        dictionary of data parsed out of the current section
        """

        d = {}

        # First we locate the durafet banner line.
        line = f.readline()
        while len(line) > 0:
            if m := xco2qc.regex.durafet_section_banner.match(line):
                break
            line = f.readline()

        if m is None:
            self.logger.debug('No durafet data located in current cycle.')
            return d

        # The next line should contain all the data
        line = f.readline()
        if m := xco2qc.regex.durafet_data.match(line):

            d['DURAFET_TIME'] = dt.datetime(
                int(m.group('year')), int(m.group('month')),
                int(m.group('day')), int(m.group('hour')),
                int(m.group('minute')), int(m.group('second'))
            )

            for varname in [
                'BATTERY', 'TEMPERATURE', 'FET_INT', 'FET_EXT',
                'ISOLATED_POWER', 'CONTROLLER_TEMP', 'TEMPERATURE_VOLTAGE',
                'PRESSURE', 'PH_EXT', 'PH_INT'
            ]:
                d[varname] = float(m.group(varname.lower()))

        else:
            self.logger.debug('No durafet data located in current cycle.')
            return d

        return d

    def parse_prawler_ctd_cycle(self, f):
        """
        Read the entire prawler ctd cycle, convert the raw values to a single
        numeric array.

        The format of the data is

        **************************************** CTD Data
        PRAWLER CTD Samples 15 17
            0.57, 20.0875, 4.07391
            0.57, 20.0968, 4.07434
            0.57, 20.0661, 4.07216
            0.57, 20.0595, 4.07172
            0.57, 20.0671, 4.07269
            0.57, 20.0816, 4.07330
            0.57, 20.0824, 4.07350
            0.57, 20.0916, 4.07390
            0.57, 20.0885, 4.07368
            0.57, 20.1004, 4.07460

        Returns
        -------
        dictionary of data parsed out of the current section
        """

        d = {}

        # First we locate the ctd banner line.
        line = f.readline()
        while len(line) > 0:
            if m := xco2qc.regex.ctd_section_banner.match(line):
                break
            line = f.readline()

        if m is None:
            self.logger.debug('No ctd data located in current cycle.')
            return d

        # The next line should identify as PRAWLER
        while len(line) > 0:
            if m := xco2qc.regex.prawler_ctd_cycle_header.match(line):
                break
            line = f.readline()

        if m is None:
            self.logger.debug('No prawler ctd data located in current cycle.')
            return d

        # Ok, we have encountered the PRAWLER CTD banner.  It appears that
        # the next 10 lines are the samples.
        buffer = []
        while True:

            line = f.readline()

            if len(line.strip()) == 0:
                # If we hit a line of whitespace, then we're done with
                # prawler ctd.
                break
            else:
                # accumulate the data until we're done.
                buffer.append(line.strip())

        s = '\n'.join(buffer)
        data = np.loadtxt(io.StringIO(s), dtype=np.float64, delimiter=',')

        d['pressure'] = data[:, 0]
        d['temperature'] = data[:, 1]
        d['conductivity'] = data[:, 2]

        return d

    def parse_met_cycle(self, f):
        """
        Read the entire Met section, convert the raw values to a single
        numeric array.

        The format of the data is

        **************************************** Met Data
        SSTC samples 03
        28.9359 05.58731 34.0722 28.9346 05.58719 34.0722
        28.9366 05.58737 34.0721
        Wind samples 0000

        Returns
        -------
        dictionary of data parsed out of the current section
        """

        d = {}

        # First we locate the met banner line.
        line = f.readline()
        while len(line) > 0:

            if m := xco2qc.regex.met_section_banner.match(line):
                break

            line = f.readline()

        if m is None:
            self.logger.debug('No met data located in current cycle.')
            return d

        # Ok, we have encountered the MET banner.  The next line
        # should be either SSTC or WIND sample count.
        self.logger.debug("Detected met banner...")

        while True:

            line = f.readline()
            if (m := xco2qc.regex.met_variable.match(line)) is None:
                self.logger.debug("Have reached end of met cycle.")
                break

            num_samples = int(m.group('num_samples'))

            mg = m.groupdict()
            if mg['sensor'] == 'SSTC':
                data = self.read_generic_met(f, 'SSTC', num_samples)
                d['sstc'] = data
                d['sstc_sample_count'] = np.array([num_samples])
            elif mg['sensor'] == 'Wind':
                if num_samples > 0:
                    msg = "We do not know how to handle Met Wind data."
                    raise RuntimeError(msg)

        return d

    def parse_sbe16_section(self, f):
        """
        Returns
        -------
        dictionary of data parsed out of the current section
        """

        d = {}

        while True:
            line = f.readline()
            self.logger.debug(line.strip())

            if m := xco2qc.regex.sbe16_regex.match(line):
                mg = m.groupdict()
                num_samples = int(mg['num_samples'])
                if mg['data_source'] == 'Pressure':
                    self.read_sbe16_pressure(f, d, num_samples)
                elif mg['data_source'].startswith('Channel'):
                    channel_num = int(mg['sub_channel'])
                    data = self.read_generic_sbe16_buffer(f, num_samples)
                    d[f"channel_{channel_num}"] = data
                    varname = f"channel_{channel_num}_sample_count"
                    d[varname] = np.array([num_samples])
                elif mg['data_source'] == 'Serial SBE38':
                    self.read_sbe16_sbe38(f, d, num_samples)
                elif mg['data_source'] == 'Serial SBE50':
                    self.read_sbe16_sbe50(f, d, num_samples)
                elif mg['data_source'] == 'Serial GTD':
                    self.read_sbe16_gtd(f, d, num_samples)
                elif mg['data_source'] == 'Serial dual GTD':
                    self.read_sbe16_dual_gtd(f, d, num_samples)
                elif mg['data_source'] == 'Serial optode':
                    self.read_sbe16_optode(f, d, num_samples)
                elif mg['data_source'].lower() == 'serial sbe63':
                    self.read_sbe16_sbe63(f, d, num_samples)
                elif mg['data_source'] == 'Wetlabs':
                    self.read_sbe16_wetlabs(f, d, num_samples)
                elif mg['data_source'] == 'Sound velocity':
                    self.read_sbe16_sound_velocity(f, d, num_samples)
                elif mg['data_source'] == 'Density':
                    data = self.read_generic_sbe16_buffer(f, num_samples)
                    d['density'] = data
                    d['density_sample_count'] = np.array([num_samples])
                elif mg['data_source'] == 'Voltage':
                    data = self.read_generic_sbe16_buffer(f, num_samples)
                    d['voltage'] = data
                    d['voltage_sample_count'] = np.array([num_samples])
                elif mg['data_source'] == 'Current':
                    data = self.read_generic_sbe16_buffer(f, num_samples)
                    d['current'] = data
                    d['current_sample_count'] = np.array([num_samples])

            elif xco2qc.regex.sami_section_regex.match(line):
                msg = (
                    'finished reading SBE16 data, start of SAMI detected'
                )
                self.logger.debug(msg)
                break

            elif len(line) == 0:
                self.logger.debug('EOF?')
                break

            else:
                pass

        return d

    def parse_licor_section(self, sf):
        """
        Parse the licor data from a single cycle.

        Returns
        -------
        dictionary of data parsed out of the current cycle section
        """

        # Initialize the dicts
        d = {}
        for pumpmode in core.licor.PUMP_MODES:
            d[pumpmode] = {}

        # Search for locations in the buffer where there is pump mode section.
        sf.seek(0)
        data = sf.read()
        bf = io.BytesIO(data.encode('utf-8'))

        offsets = []
        while True:
            pos = bf.tell()
            line = bf.readline().decode('utf-8')
            if len(line) == 0:
                break
            if m := xco2qc.regex.mapco2_pump_regex.match(line):  # noqa : F841
                offsets.append(pos)

        offsets = np.array(offsets)
        extents = np.zeros_like(offsets)
        extents[:-1] = np.diff(offsets)

        bf.seek(0, io.SEEK_END)
        extents[-1] = bf.tell() - offsets[-1]

        for offset, extent in zip(offsets, extents):
            bf.seek(offset)
            buffer = bf.read(extent)
            self.parse_licor_section_pump_mode(buffer.decode('utf-8'), d)

        return d

    def parse_licor_section_pump_mode(self, buffer, d):
        """
        Read the Li, O2, RH, and Rh temp data for a single pump mode, such
        as air-pump-off.
        """

        f = io.StringIO(buffer)

        line = f.readline()
        self.logger.debug(line.strip())

        # The current line should look something like
        #
        # ************************************* Zero cycle pump on 00

        m = xco2qc.regex.mapco2_pump_regex.match(line)

        self.logger.debug(line)
        g = m.groupdict()

        pumpmode = f"{g['mode'].lower()}-{g['action']}-{g['state']}"
        minutes_past_cycle_start = int(g['minutes_past_cycle_start'])

        d[pumpmode]['offset'] = np.array([minutes_past_cycle_start])

        while True:

            line = f.readline()
            self.logger.debug(line)

            # Current buffer should look something like
            #
            # Li samples 058

            if m := xco2qc.regex.other_sensor_regex.match(line):
                # Ok, we've moved to the next sensor section, we're done.
                break

            elif m := xco2qc.regex.mapco2_sensor_regex.match(line):
                num_samples = int(m.group('num_samples'))

                # we lower-case the sensor as this is used for the basis of the
                # variable names
                sensor = m.group('sensor').lower()

                if sensor == 'li':
                    data = self.read_li_section(f, num_samples)
                    d[pumpmode][sensor] = data
                    d[pumpmode]['li_sample_count'] = np.array([num_samples])
                elif sensor == 'o2':
                    data = self.read_o2_rh_temp_section(f, num_samples, sensor)
                    d[pumpmode][sensor] = data
                    d[pumpmode]['o2_sample_count'] = np.array([num_samples])
                elif sensor == 'rh':
                    data = self.read_o2_rh_temp_section(f, num_samples, sensor)
                    d[pumpmode][sensor] = data
                    d[pumpmode]['rh_sample_count'] = np.array([num_samples])
                elif sensor == 'rh temp':
                    data = self.read_o2_rh_temp_section(f, num_samples, sensor)
                    d[pumpmode][sensor] = data
                    d[pumpmode]['rh_temp_sample_count'] = np.array([num_samples])  # noqa : E501

            elif len(line) == 0:
                # EOF
                break

        # Check that we got a full set of data.  If the last cycle was
        # truncated, we should discard it.
        if len(d[pumpmode]) < 5:
            msg = (
                f"Missing at least part of the {pumpmode} section, "
                f"discarding..."
            )
            self.logger.debug(msg)
            raise TruncatedCycleError(msg)

    def process_cycle_headers(self):
        """
        Extract all the information from the "header" lines.  These look
        something like

        POSO 00000 00000 2014/07/17 18:00:01      hog 0146
        07/17/2014 17:56:34 3222.2660 N 06441.7162 W 0094 4.3 ...
        14.2 10.8 0.000000 0.000000 0000
        """
        self.logger.info("Processing cycle headers...")

        self.parse_cycle_headers()
        self.drop_cycle_duplicates()
        self.drop_cycles_outside_config_file_specs()
        self.check_monotonic()
        self.write_cycle_headers()

    def drop_cycles_outside_config_file_specs(self):
        """
        Drop any cycles that are outside of the time bounds specified by
        the configuration for this run.
        """
        df = self.df.reset_index()

        # Force the index to be monotonic increasing by one.
        df.index = range(len(self.df))

        # place the offsets and extents into the data frame in order to do
        # all the calculations in one shot
        df['cycle_offset'] = self.cycle_offset
        df['cycle_extent'] = self.cycle_extent

        # restrict the header cycles to the config file bounds
        start = self.config['QC']['start']  # noqa : F841
        stop = self.config['QC']['stop']  # noqa : F841
        df = df.query('time >= @start and time <= @stop')

        # extract the new cycle offsets and extents
        self.cycle_offset = df['cycle_offset']
        self.cycle_extent = df['cycle_extent']
        df = df.drop(labels=['cycle_offset', 'cycle_extent'], axis='columns')

        self.df = df.set_index('time')

    def check_monotonic(self):
        """
        The time must be monotonic increasing.
        """

        # Make sure it is monotonic!
        # Can't get pandas is_monotonic_increasing to work here...
        timestamp = self.df.reset_index()['time'].apply(
            lambda x: x.timestamp()
        ).values
        idx = np.nonzero(np.diff(timestamp) <= 0)[0]

        if len(idx) > 0:
            df = self.df.reset_index()
            msg = (
                f"The input file stops being monotonically increasing at "
                f"index {idx[0]}, going from {df['time'].iloc[idx[0]]} "
                f"to {df['time'].loc[idx[0] + 1]}.  "
                f"It must be manually edited."
            )
            raise RuntimeError(msg)

    def parse_cycle_headers(self):

        records = []
        cycle_offset = []

        while True:
            fpos = self.f.tell()
            try:
                line = self.f.readline().decode('utf-8')
            except UnicodeDecodeError:
                # definitely not a match
                continue
            if len(line) == 0:
                # End of file
                break

            if m1 := xco2qc.regex.header_line1_regex.match(line):
                line = self.f.readline().decode('utf-8')
                if m2 := xco2qc.regex.header_line2_regex.match(line):
                    line = self.f.readline().decode('utf-8')

                    # If line 1 and 2 match, that's good enough.  Go ahead and
                    # mark this as a valid cycle.
                    cycle_offset.append(fpos)

                    d = self.extract_header_line_1_items(m1)
                    d2 = self.extract_header_line_2_items(m2)
                    d.update(d2)

                    # We allow for the possibility of a corrupt third line.
                    m3 = xco2qc.regex.header_line3_regex.match(line)
                    d3 = self.extract_header_line_3_items(m3, d['ver_num'])
                    d.update(d3)

                    records.append(d)

        cycle_offset = np.array(cycle_offset)
        cycle_extent = np.zeros_like(cycle_offset)
        cycle_extent[:-1] = np.diff(cycle_offset)
        cycle_extent[-1] = self.inputfile.stat().st_size - cycle_offset[-1]

        self.cycle_offset = cycle_offset
        self.cycle_extent = cycle_extent

        df = pd.DataFrame(records).set_index('time')
        df = df.rename(mapper={'dtime': 'time'}, axis='columns')
        self.df = df

    def drop_cycle_duplicates(self):

        df = self.df
        cycle_offset = self.cycle_offset
        cycle_extent = self.cycle_extent

        # Detect and drop any records where we have duplicated time.
        # We also drop the location of the cycles that were duplicated.
        duplicated = df.index.duplicated()
        if any(duplicated):

            msg = (
                f"Duplicated times located and dropped, "
                f"{df.loc[duplicated].index}"
            )
            self.logger.warning(msg)

            df = df.loc[~duplicated]
            cycle_offset = np.array([
                offset for a_duplicate, offset in zip(duplicated, cycle_offset)
                if not a_duplicate
            ])

            cycle_extent = np.array([
                extent for a_duplicate, extent in zip(duplicated, cycle_extent)
                if not a_duplicate
            ])

        self.df = df
        self.cycle_offset = cycle_offset
        self.cycle_extent = cycle_extent

    def write_cycle_headers(self):
        """
        Write cycle header data to netCDF file.  The header information is
        currently being held in a time-indexed dataframe.
        """

        # Push the time index into the dataframe itself so that we can easily
        # write it to a netcdf variable.
        df = self.df.reset_index()

        ncfile = self.dst_dir / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile, mode='w', clobber=True) as nc:

            self.write_global_attributes(nc)

            nc.createDimension('time', 0)

            for varname in df.columns:
                self.logger.debug(f"Writing {varname} to {ncfile}")

                if varname in [
                    'site_id', 'system_number', 'ver_num', 'ver_date'
                ]:
                    # These are already taken care of as attributes.
                    continue

                metadata = vardefs['raw_cycle_header'][varname]

                ncvar = nc.createVariable(
                    varname,
                    metadata['datatype'],
                    dimensions=('time',),
                    fill_value=metadata['fill_value']
                )

                # Write the netCDF variable attributes
                for attrname, attrvalue in metadata['attributes'].items():
                    setattr(ncvar, attrname, attrvalue)

                if 'calendar' in metadata['attributes']:
                    # Convert time data into seconds since the epoch
                    data = (df[varname] - self.time_base).dt.total_seconds()

                    data = data.fillna(0)
                    data = data.astype(metadata['datatype'])
                    data[data == 0] = metadata['fill_value']

                elif 'categories' in metadata['attributes']:
                    # Convert the categorical data into numeric codes
                    categories = sorted(self.df[varname].unique())
                    cat_type = CategoricalDtype(categories=categories,
                                                ordered=True)
                    self.df[varname] = self.df[varname].astype(cat_type)
                    data = self.df[varname].cat.codes

                    # record the mapping in the attributes.
                    mapping = dict(zip(
                        self.df[varname].cat.codes, self.df[varname]
                    ))
                    codes = list(range(len(mapping)))
                    categories = " ".join([mapping[code] for code in mapping])
                    ncvar.categories = categories
                    ncvar.codes = codes

                else:
                    # Regular data
                    data = self.df[varname]
                    data = data.fillna(metadata['fill_value'])

                ncvar[:] = data

            nc.data_source = 'MAPCO2'

    def write_global_attributes(self, nc):
        """
        Create the netCDF file global attributes.
        """

        nc.firmware_version_number = self.df['ver_num'].iloc[0]
        nc.firmware_version_date = self.df['ver_date'].iloc[0].isoformat()  # noqa : E501

    def extract_header_line_1_items(self, m1):
        """
        Parameters
        ----------
        m1 : re.Match
            regular expression match from 1st header line

        Returns
        -------
        dictionary of items from header line 2
        """
        d = {}

        # Extract out items from line 1
        gd = m1.groupdict()

        d['mode'] = gd['header_mode']
        d['rand1'] = int(gd['rand1'])
        d['rand2'] = int(gd['rand2'])
        d['time'] = dateutil.parser.parse(gd['time'])
        d['site_id'] = gd['site_id']
        d['system_number'] = int(gd['system_number'])
        try:
            d['ver_num'] = float(gd['ver_num'])
        except TypeError:
            # Most likely because there was no ver_num
            d['ver_num'] = 3.18
        try:
            d['ver_date'] = dateutil.parser.parse(gd['ver_date'])
        except TypeError:
            d['ver_date'] = pd.NaT

        return d

    def extract_header_line_2_items(self, m):
        """
        Parameters
        ----------
        m1 : re.Match
            regular expression match from 1st header line

        The line that was matches looked something like what follows:

        10/19/2016 18:07:34 3328.2727 N 12231.9959 W 0155 1.7 \
            2016/10/19 12:26:23 2016/10/19 12:26:22     I 0030

        Returns
        -------
        dictionary of items from header line 2
        """

        d = {}

        gd = m.groupdict()
        try:
            d['gps_dtime'] = dateutil.parser.parse(gd['gps_dtime'])  # noqa : E501
        except dateutil.parser.ParserError:
            d['gps_dtime'] = pd.NaT

        deg = int(gd['raw_lat'][:2])
        min = float(gd['raw_lat'][2:])
        d['latitude'] = deg + min / 60
        if gd['NorS'] == 'S':
            d['latitude'] *= -1

        deg = int(gd['raw_lon'][:3])
        min = float(gd['raw_lon'][3:])
        d['longitude'] = deg + min / 60
        if gd['EorW'] == 'W':
            d['longitude'] *= -1

        d['gps_aqtime'] = int(gd['gps_aqtime'])

        d['gps_qf'] = float(gd['gps_qf'])

        try:
            d['sys_dtime2'] = dateutil.parser.parse(gd['sys_dtime2'])  # noqa : E501
        except (dateutil.parser.ParserError, TypeError):
            d['sys_dtime2'] = pd.NaT

        try:
            d['gps_dtime_ck'] = dateutil.parser.parse(gd['gps_dtime_ck'])  # noqa : E501
        except (dateutil.parser.ParserError, TypeError):
            d['gps_dtime_ck'] = pd.NaT

        if gd['in_out_flag'] is not None:
            d['in_out_flag'] = gd['in_out_flag']
            d['valve_pulse'] = int(gd['valve_pulse'])  # noqa : E501
        else:
            d['in_out_flag'] = ' '
            d['valve_pulse'] = '-1'

        return d

    def extract_header_line_3_items(self, m, version_number):
        """
        Parameters
        ----------
        m : re.Match
            regular expression match from 3rd header line
        version_number : int
            firmware version number

        Returns
        -------
        dictionary of items from header line 3
        """
        d = {}

        if m is None:
            # This is possible if the line is corrupt.
            d['battery_logic'] = np.nan
            d['battery_trans'] = np.nan
            d['zero_coefficient'] = np.nan
            d['span_coefficient'] = np.nan
            d['span2_coefficient'] = np.nan
            d['span_flag'] = np.nan
            d['zero_flag'] = np.nan
            return d

        gd = m.groupdict()

        d['battery_logic'] = float(gd['battery_logic'])  # noqa : E501
        d['battery_trans'] = float(gd['battery_trans'])
        d['zero_coefficient'] = float(gd['zero_coefficient'])  # noqa : E501
        d['span_coefficient'] = float(gd['span_coefficient'])  # noqa : E501

        if version_number >= 6.0:
            try:
                d['span2_coefficient'] = float(gd['span2_coefficient'])  # noqa : #501
            except TypeError:
                msg = (
                    f'No span2 coefficient even though the firmware version '
                    f'number is {version_number}.'
                )
                self.logger.warning(msg)
                d['span2_coefficient'] = np.nan
        else:
            d['span2_coefficient'] = np.nan

        # This seems to be hex, convert to integer.
        d['span_flag'] = int(gd['li_flag'][:2], 16)
        d['zero_flag'] = int(gd['li_flag'][2:], 16)

        return d

    def _read_generic_sbe16_text(self, f):
        """
        Read a generic buffer from the SBE16 section

        Returns
        -------
        text containing the SBE16 section
        """
        buffer = []
        while True:
            fpos = f.tell()
            line = f.readline()

            if m := xco2qc.regex.sbe16_regex.match(line):
                # Have moved out of current SBE data source section.
                # backup then break out
                f.seek(fpos)
                break
            elif m := xco2qc.regex.sami_section_regex.match(line):  # noqa : F841
                # have moved out of sbe16 section, now position at a sami
                # buffer.  backup then break out
                f.seek(fpos)
                break
            elif len(line) == 0:
                # EOF?
                break
            else:
                # accumulate the data until we're done.
                buffer.append(line.strip())

        return ' '.join(buffer)

    def read_generic_sbe16_buffer(self, f, num_samples, n_params=1):
        """
        Read a generic buffer from the SBE16 section

        Returns
        -------
        text containing the SBE16 section
        """
        text = self._read_generic_sbe16_text(f)
        data = self.read_mapco2_data_buffer(text, num_samples,
                                            n_params=n_params)

        return data

    def read_sbe16_sound_velocity(self, sf, d, num_samples):
        """
        Read the entire sbe sound velocity section, convert the raw values to a
        single numeric array.
        """
        if num_samples > 0:
            msg = "SBE16: sound velocity data currently unhandled"
            raise UnhandledDataStreamError(msg)

    def read_sbe16_sbe63(self, sf, d, num_samples):
        """
        Read the entire sbe sbe63 section, convert the raw values to a
        single numeric array.
        """
        data = self.read_generic_sbe16_buffer(sf, num_samples)
        d['sbe63'] = data

    def read_sbe16_optode(self, sf, d, num_samples):
        """
        Read the entire sbe optode section, convert the raw values to a
        single numeric array.
        """
        if num_samples == 0:
            data = np.array([])
        else:

            self.logger.debug("Check optode fill value")

            data = self.read_generic_sbe16_buffer(sf, num_samples)

        d['optode'] = data

    def read_sbe16_dual_gtd(self, sf, d, num_samples):
        """
        Read the entire sbe DUAL GTD section, convert the raw values to a
        single numeric array.
        """
        if num_samples > 0:
            msg = "SBE16 DUAL GTD:  GTD data currently unhandled"
            raise UnhandledDataStreamError(msg)

    def read_sbe16_gtd(self, sf, d, num_samples):
        """
        Read the entire sbe GTD section, convert the raw values to a
        single numeric array.
        """
        if num_samples == 0:
            data = np.array([])
        else:
            data = self.read_generic_sbe16_buffer(sf, num_samples, n_params=2)

            # GTD data has an extra dimension.
            data = data.reshape((1, num_samples, -1))

        d['gtd'] = data
        d['gtd_sample_count'] = np.array([num_samples])

    def read_sbe16_wetlabs(self, sf, d, num_samples):
        """
        We don't know how to interpret wetlabs data, so ignore it.
        """
        msg = (
            "we do not know how to interpret wetlabs data, so ignore it"
        )
        self.logger.debug(msg)
        return

    def read_sbe16_sbe50(self, sf, d, num_samples):
        """
        Read the entire sbe SBE50 section, convert the raw values to a
        single numeric array.
        """
        if num_samples > 0:
            msg = "SBE16:  We don't currently handle SBE50 data yet"
            raise UnhandledDataStreamError(msg)

    def read_sbe16_sbe38(self, f, d, num_samples):
        """
        Read the entire sbe SBE38 section, convert the raw values to a
        single numeric array.
        """
        if num_samples > 0:
            msg = "SBE16:  We don't currently handle SBE38 data yet"
            raise UnhandledDataStreamError(msg)

    def read_sbe16_pressure(self, f, d, num_samples):
        """
        Read the entire sbe pressure section, convert the raw values to a
        single numeric array.

        Parameters
        ----------
        f : file-like
            file pointer for raw text input file
        d : dict
            store the pressure here
        num_samples : int
            read this many values
        """
        if num_samples == 0:
            data = np.array([])
        else:
            data = self.read_generic_sbe16_buffer(f, num_samples)
        d['pressure'] = data
        d[f"{'pressure'}_sample_count"] = np.array([num_samples])

    def read_o2_rh_temp_section(self, f, num_samples, buffer_name):
        """
        Read the entire O2, RH, or Rh temp section, convert the raw values to a
        single numeric array.
        """
        # If rh_temp, then replace the space in the name.
        buffer_name = buffer_name.replace(' ', '_')

        lines = []
        while True:
            pos = f.tell()
            line = f.readline()

            if m := xco2qc.regex.mapco2_sensor_regex.match(line):  # noqa : F841
                # We've moved past the end of the current sensor section.
                f.seek(pos)
                break
            elif m := xco2qc.regex.other_sensor_regex.match(line):  # noqa : F841
                # We've moved past the end of the current sensor section.
                f.seek(pos)
                break
            elif len(line) == 0:
                self.logger.debug('EOF?')
                break
            else:
                # accumulate the LICOR data until we're done.
                lines.append(line.strip())

        msg = (
            f"LI-820 {buffer_name}:  "
            f"Read {len(lines)} lines of data, "
            f"expecting to find {num_samples} samples"
        )
        self.logger.debug(msg)

        s = ' '.join(lines)
        data = self.read_mapco2_data_buffer(s, num_samples, n_params=1)

        return data

    def read_generic_met(self, f, sensor_name, num_samples):
        """
        Read the entire SSTC/Wind section, convert the raw values to a single
        numeric array.

        At this point, we have matched a text line of either the sample count
        for SSTC or Wind, so we should be pointing at a line of sample data.
        """
        buffer = []
        while True:
            fpos = f.tell()
            line = f.readline()

            if m := xco2qc.regex.met_variable.match(line):  # noqa : F841
                # We've moved past the end of the SSTC/WIND section.
                self.logger.debug(f'finished reading {sensor_name} data')
                f.seek(fpos)
                break
            elif m := xco2qc.regex.other_sensor_regex.match(line):  # noqa : F841
                # We've moved past the end of the SSTC section.
                # Maybe we are in SBE16 now?
                self.logger.debug(f'finished reading {sensor_name} data')
                f.seek(fpos)
                break
            elif len(line) == 0:
                # We've moved to end-of-file
                break
            else:
                # accumulate the data until we're done.
                buffer.append(line.strip())

        msg = (
            f"{sensor_name}:  "
            f"Read {len(buffer)} lines of data, "
            f"expecting to find {num_samples} samples"
        )
        self.logger.debug(msg)

        # Join into a single string, read into a 1D array, and reshape back
        # to a num_samples x 5 array
        s = ' '.join(buffer)
        data = np.fromstring(
            s, dtype=np.float64, count=num_samples * 3, sep=' '
        )
        data = data.reshape((1, num_samples, 3))

        return data

    def read_mapco2_data_buffer(self, s, num_samples, n_params=5):
        """
        Read data from string derived from licor data stream.  This was
        originally a one-liner using np.fromstring, but that issues a warning
        about a potential future exception being raised when the specified
        number of samples cannot be read.

        Parameters
        ----------
        s : str
            All data reported in the raw file for a particular pump mode for
            a particular cycle.
        num_samples : int
            Number of values expected.  In case of corruption, the data will
            be padded with a fill value.
        n_params : int
            Number of parameters measured in a sample.  The Li datastream has
            5, but O2, RH, and Rh_temp have just 1.

        Returns
        -------
        ndarray
            Data read from the string.
        """
        if num_samples < 1:
            # If we don't do this, the code that follows issues annoying
            # warnings.
            return np.zeros((1, 0), dtype=np.int32)

        try:
            data = np.loadtxt(io.StringIO(s), dtype=np.float64)
        except ValueError:
            # Usually this happens when the data string has been corrupted
            # towards the end.
            #
            # Find the largest part of the string that can actually be read.
            lst = s.split()
            s2 = ' '.join(lst)

            data_read_ok = False
            while not data_read_ok:
                try:
                    data = np.loadtxt(io.StringIO(s2), dtype=np.float64)
                except ValueError:
                    # cut off another item from the end
                    lst = s2.split()
                    s2 = ' '.join(lst[:-1])
                else:
                    # Ok, we have successfully read the corrupt data.
                    # Break out of this loop.
                    data_read_ok = True

        if data.size == 1:
            # don't allow for scalars
            data = np.array([data[()]])

        if len(data) < num_samples * n_params:
            data2 = np.full((num_samples * n_params,), np.nan,
                            dtype=np.float64)
            data2[:len(data)] = data
            data = data2
        elif len(data) > num_samples * n_params:
            data = data[:num_samples * n_params]

        if n_params == 1:
            # This case for O2, RH, and Rh_temp
            data = data.reshape((1, num_samples))
        else:
            # This case for the Li buffer
            data = data.reshape((1, num_samples, n_params))
        return data

    def read_li_section(self, f, num_samples):
        """
        Read the entire Li section, convert the raw values to a single
        numeric array.

        The format of the data is

        xco2 temp press raw1 raw2  xco2 temp press raw1 raw2
        xco2 temp press raw1 raw2  xco2 temp press raw1 raw2
        xco2 temp press raw1 raw2  xco2 temp press raw1 raw2
        .
        .
        .

        Returns
        -------
        ndarray of size (2*n) x 5 where n = number of rows of text in the Li
        section
        """
        buffer = []
        while True:
            pos = f.tell()
            line = f.readline()

            m = xco2qc.regex.mapco2_sensor_regex.match(line)
            if m is not None:
                # We're done.
                # We've moved past the end of the licor section.  Save the
                # file position at the start of this line for subsequent
                # processing.
                f.seek(pos)
                break
            elif len(line) == 0:
                # Truncated buffer?  Trouble.
                msg = f'Possible truncated Li buffer at {self.f.tell()}'
                self.logger.warning(msg)
                break
            else:
                # accumulate the LICOR data until we're done.
                buffer.append(line.strip())

        msg = (
            f"LICOR:  "
            f"Read {len(buffer)} lines of data, "
            f"expecting to find {num_samples} samples"
        )
        self.logger.debug(msg)

        # Join into a single string, read into a 1D array, and reshape back
        # to a num_samples x 5 array
        s = ' '.join(buffer)
        if num_samples < 1:
            data = np.array([])
        else:
            data = self.read_mapco2_data_buffer(s, num_samples)

        return data
