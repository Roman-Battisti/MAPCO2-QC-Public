# standard library imports
import pathlib

# 3rd party library imports
import numpy as np
import pandas as pd
import netCDF4
from IPython.display import display, HTML

# local imports
from xco2qc import core


class QCStatisticsCore(object):
    """
    Attributes
    ----------
    df : pandas.DataFrame
        the counts of the QC flags for each specified file/variable
    tslen : int
        length of the time series
    """

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass

    def run(self):

        self.get_qc_statistics()
        self.display_qc_statistics()

    def get_qc_statistics(self):
        """
        Retrieve the counts of how many times all the QC flag bits were set.

        Returns
        -------
        pandas.Series where the flag meaning is the index and the counts
        constitute the values
        """

        lst = []

        for config in self.inputs:
            ncfile = config['ncfile']
            variable = config['variable']

            if not ncfile.exists():
                # There might not be any sami data.
                continue

            with netCDF4.Dataset(ncfile) as nc:
                var = nc[variable]
                qc = var[:]

                flag_masks = var.flag_masks
                flag_meanings = var.flag_meanings

            self.tslen = len(qc)

            counts = np.zeros((len(flag_masks),), dtype=np.uint16)
            counts[0] = (qc == core.quality.GOOD).sum().item()
            for idx in range(1, len(flag_masks)):
                x = np.bitwise_and(qc, flag_masks[idx])
                counts[idx] = len(x[x > 0])

            flag_meanings = flag_meanings.split()

            # construct a column name
            # if we have a netCDF file, try to use the pump mode attribute
            # instead of the filename itself
            try:
                with netCDF4.Dataset(ncfile) as nc:
                    name = f"{nc.pump_mode.upper()} {variable}"
            except Exception:
                name = f"{ncfile.name} {variable}"

            s = pd.Series(counts, index=flag_meanings, name=name)
            lst.append(s)

        self.df = pd.concat(lst, axis='columns')

    def display_qc_statistics(self):
        display(self.df)
        display(HTML(f'<p>Time series length:  {self.tslen}</p>'))


class XCO2QCStatistics(QCStatisticsCore):
    """
    """

    def __init__(self, ncfiles=None):
        """
        Parameters
        ----------
        input_arg : list of dicts or str
            If a string, then it must be a netCDF file and we assume what the
            netCDF variable will be.  If a list of dicts, then we check the
            specified variable in the specified file.
        """

        if isinstance(ncfiles, pathlib.Path) and ncfiles.is_dir():
            # We were given a directory.  Look for the pump-mode netCDF files
            # under this directory.
            reduced_dir = ncfiles
            self.inputs = [
                {
                    'ncfile': reduced_dir / core.licor.APOFF_NCFILE,
                    'variable': 'xco2_wet_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.EPOFF_NCFILE,
                    'variable': 'xco2_wet_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.SPOSTCAL_NCFILE,
                    'variable': 'xco2_wet_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.SPOFF_NCFILE,
                    'variable': 'xco2_wet_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.ZPOFF_NCFILE,
                    'variable': 'xco2_wet_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.ZPOSTCAL_NCFILE,
                    'variable': 'xco2_wet_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.APOFF_NCFILE,
                    'variable': 'pressure_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.EPOFF_NCFILE,
                    'variable': 'pressure_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.APOFF_NCFILE,
                    'variable': 'rh_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.EPOFF_NCFILE,
                    'variable': 'rh_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.APOFF_NCFILE,
                    'variable': 'rh_temp_qc'
                },
                {
                    'ncfile': reduced_dir / core.licor.EPOFF_NCFILE,
                    'variable': 'rh_temp_qc'
                },
                {
                    'ncfile': reduced_dir / core.SAMI_NCFILE,
                    'variable': 'ph_qc'
                },
            ]

        elif (
            isinstance(ncfiles, str)
            or (
                isinstance(ncfiles, pathlib.Path)
                and not ncfiles.is_dir()
                and ncfiles.exists()
            )
        ):
            # We were passed a string that corresponds to a file.
            # This is likely going to be the socat netCDF file.
            self.inputs = [
                {
                    'ncfile': ncfiles,
                    'variable': 'xCO2_air_qc',
                },
                {
                    'ncfile': ncfiles,
                    'variable': 'xco2_air_wet_qc',
                },
                {
                    'ncfile': ncfiles,
                    'variable': 'xCO2_sw_qc',
                },
                {
                    'ncfile': ncfiles,
                    'variable': 'xco2_sw_wet_qc',
                },
            ]

        else:
            self.inputs = ncfiles

        # force each netcdf filename to be a path.  That makes it easier to
        # manipulate it later on.
        for config in self.inputs:
            config['ncfile'] = pathlib.Path(config['ncfile'])


class PH_QCStatistics(QCStatisticsCore):
    """
    Display PH QC statistics for the PH data.
    """

    def __init__(self, ncfile):
        """
        Parameters
        ----------
        ncfile : str or path
            Path to netCDF file with PH
        """
        self.inputs = [{'ncfile': ncfile, 'variable': 'pH_sw_qc'}]

        # force each netcdf filename to be a path.  That makes it easier to
        # manipulate it later on.
        for config in self.inputs:
            config['ncfile'] = pathlib.Path(config['ncfile'])
