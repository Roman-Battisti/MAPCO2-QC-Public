# Standard library imports
from contextlib import ExitStack
import datetime as dt
import pathlib

# 3rd party library imports
import netCDF4
import numpy as np

# Local imports
from . import core


class NetCDFWriter(core.MapCO2core):
    """
    Attributes
    ----------
    src_ncfile : path
        Read from this netCDF file.  If the dst_ncfile is not provided,
        then we will be writing to the source file as well as reading it.
    dst_ncfile : path or None
        netCDF file to be written, if provided
    """

    def __init__(self, src_ncfile, dst_ncfile=None, verbosity=None):
        """
        Parameters
        ----------
        src_ncfile : str or path
            source netCDF file
        dst_ncfile : str or path
            netCDF file to be written
        verbosity : str
            logging level
        """
        self.src_ncfile = pathlib.Path(src_ncfile)
        src_dir = self.src_ncfile.parents[0]
        if dst_ncfile is not None:
            self.dst_ncfile = pathlib.Path(dst_ncfile)
        else:
            self.dst_ncfile = None

        super().__init__(
            src_dir=src_dir, verbosity=verbosity, logger_name='netcdf-writer'
        )

        # all time variables should have the same common base
        self.time_base = dt.datetime(1970, 1, 1).replace(tzinfo=dt.timezone.utc)  # noqa : E501
        self.common_time_var_units = "seconds since 1970-01-01T00:00:00"

        if not self.src_ncfile.exists():
            # The source netcdf file does not exist, so we must be creating it
            # and writing to it.
            self.dst_ncfile = self.src_ncfile

        elif self.dst_ncfile is None:
            # The source netCDF file exists, but no target netCDF file was
            # given.  So we read AND write to the source file.
            self.dst_ncfile = self.src_ncfile

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass

    def initialize_netcdf_definitions(self):
        """
        Write out everything that we can to the netCDF file before processing
        any data variables.
        """
        with ExitStack() as cm:

            # safely acquire netcdf file resources
            self.src_nc = cm.enter_context(netCDF4.Dataset(self.src_ncfile))
            self.dst_nc = cm.enter_context(
                netCDF4.Dataset(self.dst_ncfile, mode='w')
            )

            self.write_global_attributes()
            self.define_dimensions()
            self.define_coordinate_variables()

    def define_coordinate_variables(self):
        """
        Define the variables that depend upon dimensions by the same name.
        """
        time = self.dst_nc.createVariable(
            core.TIME, np.int64, dimensions=(core.TIME,)
        )
        time.long_name = core.TIME
        time.standard_name = core.TIME
        time.units = self.common_time_var_units
        time.calendar = 'gregorian'

    def write_coordinate_variables(self):
        """
        Write the variables that depend upon dimensions by the same name.

        This information should be copied over from the source netCDF file.
        """

        # Write the coordinate variables
        # The time data is just copyied over as-is.
        self.dst_nc[core.TIME][:] = self.src_nc[core.TIME][:]

    def define_dimensions(self):
        """
        Define the netCDF dimensions.  Just these two for now.
        """
        self.dst_nc.createDimension(core.TIME, size=0)

    def write_global_attributes(self):
        """
        Create the netCDF file global attributes.
        """
        if self.src_nc is not None:
            # If the source file is netCDF, copy over all the global
            # attributes.
            for attr_name in self.src_nc.ncattrs():
                value = getattr(self.src_nc, attr_name)
                setattr(self.dst_nc, attr_name, value)

    def define_netcdf_variable(self, varname):
        """
        Parameters
        -------
        reduced_data : ndarray
            1D array of a geophysical quantity
        qc : ndarray
            Quality array corresponding to the reduced data
        """
        if varname in self.dst_nc.variables:
            msg = f"{varname} already exists, so we will not re-create it"
            self.logger.warning(msg)
            return

        metadata = self.nc_variable_defs[varname]

        # Special case for zero pump xco2 variables, the valid_range extends
        # into the negative
        try:
            if metadata['attributes']['standard_name'].startswith('mole_concentration_of_carbon_dioxide_in_') and 'zero' in self.dst_nc.pump_mode:  # noqa : E501
                metadata['attributes']['valid_range'] = [-100, 700]
        except KeyError:
            pass

        v = self.dst_nc.createVariable(varname, metadata['datatype'],
                                       dimensions=(core.TIME,),
                                       fill_value=metadata['fill_value'])
        for attname, attvalue in metadata['attributes'].items():
            setattr(v, attname, attvalue)

        # Define the QC variable if it is appropriate to do so.
        qc_mask_varname = self.get_qc_mask_varname(v)
        if qc_mask_varname is not None:
            metadata = self.nc_variable_defs[qc_mask_varname]
            v = self.dst_nc.createVariable(
                qc_mask_varname, metadata['datatype'],
                dimensions=(core.TIME,),
                fill_value=metadata['fill_value']
            )

            # Set the QC variable attributes
            for attname, attvalue in metadata['attributes'].items():
                setattr(v, attname, attvalue)

    def get_qc_mask_varname(self, ncvar):
        """
        Retrieve the name of the quality variable associated with this netCDF
        data variable.

        Parameters
        ----------
        ncvar : netCDF4.variable
        """
        try:
            ancillary = ncvar.ancillary_variables
        except AttributeError:
            # no ancillary variables, therefore no QC variable
            return None

        # by the CF convention, ancillary_variables is a space-delimited text
        # string of all the variables associated with the current variable
        for qcvarname in ancillary.split():

            # we want the ancillary variable that has the attribute
            # standard_name "status_flag"
            metadata = self.nc_variable_defs[qcvarname]

            if metadata['attributes']['standard_name'] == 'status_flag':
                return qcvarname

        # If we get through the loop, then there is no qc mask variable
        return None

    def write_netcdf_variable(self, varname, data, qc='auto'):
        """
        Parameters
        -------
        reduced_data : ndarray
            1D array of a geophysical quantity
        qc : ndarray or 'auto'
            If an ndarray, these are quality flags corresponding to the reduced
            data.  If 'auto', then fill the QC variable (if it exists) with
            default (GOOD?) values (basically we assume it is all good).
        """
        self.dst_nc[varname][:] = data

        # Define and write the QC variable if it exists
        qcvarname = self.get_qc_mask_varname(self.dst_nc[varname])
        if qcvarname is None:
            return

        # If quality information is not provided, then we must assume that it
        # is all good.
        if isinstance(qc, str) and qc == 'auto':
            qc = np.full(data.shape, core.quality.GOOD, np.uint32)

        self.dst_nc[qcvarname][:] = qc
