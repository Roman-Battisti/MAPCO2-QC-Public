"""
Before creating the SOCAT products (XML and CSV files), we need to translate
the QC bitmasks into SOCAT quality flags.
"""

# standard library imports
from contextlib import ExitStack
import pathlib

# 3rd party library
import netCDF4
import numpy as np
import xarray as xr

# local imports
import xco2qc.core
from xco2qc.netcdf import NetCDFWriter


class SocatNetCDFWriter(NetCDFWriter):
    """
    This allows us to more easily write back to the merge netCDF file.

    Attributes
    ----------
    """
    def __init__(self, src_ncfile, initial_span_cal=None):
        super().__init__(src_ncfile=src_ncfile)

        self.nc_variable_defs = xco2qc.core.vardefs.data_dict['socat'].copy()


class SocatQC(xco2qc.core.MapCO2core):
    """
    Attributes
    ----------
    ncfile : path
        Path to the trimmed netCDF file.  Before computing the socat products,
        we create the SOCAT QC variables.
    df : pandas.Dataframe
        corresponding to the merge netCDF file
    """
    def __init__(self, *, ncfile=None, verbosity=None):
        self.ncfile = pathlib.Path(ncfile)
        super().__init__(
            src_dir=self.ncfile.parents[0],
            verbosity=verbosity, logger_name='socat-qc'
        )

    def run(self):

        self.logger.info('Creating SOCAT products...')

        self.derive_socat_quality_flags()

        self.logger.info('Finished creating SOCAT products...')

    def derive_socat_quality_flags(self):
        """
        Derive the SOCAT quality flags from our existing flag masks.  The
        SOCAT quality flags will be made part of the permanent record in the
        netCDF file, meaning there will be two quality variables for the two
        xCO2 wet variables.  Nothing wrong with that.
        """

        with xr.open_dataset(self.ncfile) as ds:
            df = ds.to_dataframe().reset_index()

        # Setup the list of quality variable pairs.  Sometimes we have PH.
        # Sometimes we have CHL/NTU.
        qc_pairs = [
            ('xco2_sw_socat_qc', 'xCO2_sw_qc'),
            ('xco2_air_socat_qc', 'xCO2_air_qc'),
            ('pH_sw_socat_qc', 'pH_sw_qc'),
            ('chl_nighttime_socat_qc', 'chl_nighttime_qc'),
            ('ntu_socat_qc', 'ntu_qc'),
            ('dissolved_oxygen_socat_qc', 'dissolved_oxygen_qc')
        ]

        # Transform the existing quality flags to socat.
        for socat_flag, mask_flag in qc_pairs:
            try:
                df[socat_flag] = self.transform_to_socat_quality(df[mask_flag])
            except KeyError:
                # We don't always have the mask QC variable, such is the case
                # with sami qc
                continue

        # Write the socat quality flags back to the netCDF file as part of the
        # permanent record.  This means we keep two different quality flags
        # for these two xCO2 variables, although the socat flags are derived
        # from the existing flag masks.
        with SocatNetCDFWriter(src_ncfile=self.ncfile) as ncw:

            with ExitStack() as cm:

                # Safely acquire netCDF resources
                ncw.dst_nc = cm.enter_context(
                    netCDF4.Dataset(self.ncfile, mode='r+')
                )

                for socat_flag, _ in qc_pairs:
                    try:
                        data = df[socat_flag]
                    except KeyError:
                        # the socat flags are not always there.  think about ph
                        pass
                    else:
                        ncw.define_netcdf_variable(socat_flag)
                        ncw.write_netcdf_variable(socat_flag, data)

        # And finally, update the CF attribute that ties the socat qc variable
        # to the data variable.  Easier to just do this with raw netCDF4.
        socat_pairs = [
            ('xco2_sw_wet', 'xco2_sw_socat_qc'),
            ('xco2_air_wet', 'xco2_air_socat_qc'),
            ('chl_nighttime', 'chl_nighttime_socat_qc'),
            ('dissolved_oxygen', 'dissolved_oxygen_socat_qc'),
            ('ntu', 'ntu_socat_qc'),
            ('pH_sw', 'pH_sw_socat_qc')
        ]

        with netCDF4.Dataset(self.ncfile, mode='r+') as nc:

            for data_varname, socat_qc_varname in socat_pairs:

                try:
                    attvalue = nc[data_varname].ancillary_variables
                except IndexError:
                    # the data varname wasn't present.  that might happen with
                    # ph
                    pass
                else:
                    attvalue += f" {socat_qc_varname}"
                    nc[data_varname].ancillary_variables = attvalue

    def transform_to_socat_quality(self, s):
        """
        SOCAT quality flags are

            2 : good
            3 : questionable
            4 : bad
            5 : missing

        This is obviously much less fine-grained than our quality flags.

        Parameters
        ----------
        s : pandas.Series
            series of quality flags

        Returns
        -------
        pandas series of SOCAT QC values
        """
        s = s.astype(np.uint32)
        qc = s.copy()

        # Our QUALITY_GOOD directly translates to SOCAT "good".
        qc[s == xco2qc.core.quality.GOOD] = xco2qc.core.quality.SOCAT_GOOD

        # missing data is obviously bad, but just checking for equality will
        # not work because a datum could have other troublesome flags in its
        # mask
        idx = np.bitwise_and(s, xco2qc.core.quality.MISSING_DATA)
        qc[idx > 0] = xco2qc.core.quality.SOCAT_MISSING

        # Anything manually flagged or out of range counts as "bad"
        idx = np.bitwise_and(
            s,
            np.bitwise_or(
                xco2qc.core.quality.MANUALLY_FLAGGED,
                xco2qc.core.quality.OUT_OF_RANGE
            )
        )
        qc[idx > 0] = xco2qc.core.quality.SOCAT_BAD

        # Anything else is questionable.
        idx = ~qc.isin([
            xco2qc.core.quality.SOCAT_GOOD,
            xco2qc.core.quality.SOCAT_BAD,
            xco2qc.core.quality.SOCAT_MISSING
        ])
        qc[idx] = xco2qc.core.quality.SOCAT_QUESTIONABLE
        
        # catch CHL daytime and change them to flag 5
        if s.name == "chl_nighttime_qc":
            idx = np.bitwise_and(s, xco2qc.core.quality.DAYTIME) == xco2qc.core.quality.DAYTIME
            qc[idx] = xco2qc.core.quality.SOCAT_MISSING
        
        return qc
