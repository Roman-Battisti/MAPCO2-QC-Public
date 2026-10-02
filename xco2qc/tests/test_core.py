"""
This is NOT a test suite, it is the test suite core that is to be subclassed
by all of the "real" test suites.
"""

# standard library tests
import contextlib
import datetime as dt
import importlib.resources as ir
import os
import pathlib
import shutil
import tempfile
import unittest

# 3rd party library imports
import matplotlib.pyplot as plt
import yaml

# local imports
import xco2qc.core.data


@contextlib.contextmanager
def chdir(dirname=None):
    """
    This context manager restores the value of the current working directory
    (cwd) after the enclosed code block completes or raises an exception.  If a
    directory name is supplied to the context manager then the cwd is changed
    prior to running the code block.

    Use this to run a test from a location outside of the test suite.

    Shamelessly modified from
    http://www.astropython.org/snippet/2009/10/chdir-context-manager
    """
    curdir = pathlib.Path.cwd()
    try:
        if dirname is not None:
            os.chdir(dirname)
        yield
    finally:
        os.chdir(curdir)


class TestSuite(unittest.TestCase):
    """
    Common functionality for all test suites.
    """

    def setUp(self):

        # Create a temporary directory hierarchy for various artifacts
        #
        # root
        #  |
        #  +----- log.txt
        #  |
        #  +----- config.yml
        #  |
        #  +----- raw
        #  |        |
        #  |        +---------- "raw" *.nc
        #  |
        #  +----- reduced
        #  |        |
        #  |        +---------- netCDF files are "averaged" from the raw
        #  |
        #  +----- merge_path
        #           |
        #           +---------- merge.nc
        #
        # The root directory has the log file, the config file (we run the
        # application in this directory), and a netcdf subdirectory that will
        # contain the output data files.
        self.root = pathlib.Path(tempfile.mkdtemp())

        # Write all the raw netcdf files here.
        self.raw_dir = tempfile.mkdtemp(dir=self.root)
        self.raw_path = pathlib.Path(self.raw_dir)

        # Write all the data reduction files here.
        self.reduced_dir = tempfile.mkdtemp(dir=self.root)
        self.reduced_path = pathlib.Path(self.reduced_dir)

        # Write all the diagnostics plots here.
        self.diagnostics_plot_dir = tempfile.mkdtemp(dir=self.root)
        self.diagnostics_plot_path = pathlib.Path(self.diagnostics_plot_dir)

        # Write the merged netCDF file here.
        self.merge_dir = tempfile.mkdtemp(dir=self.root)
        self.merge_path = pathlib.Path(self.merge_dir)
        self.merge_ncfile = self.merge_path / 'merge.nc'

        # Write the trimmed netCDF file here.
        self.trimmed_dir = tempfile.mkdtemp(dir=self.root)
        self.trimmed_path = pathlib.Path(self.trimmed_dir)
        self.trimmed_ncfile = self.trimmed_path / 'trimmed.nc'

        # This config path is a file that we will populate each time.  Use this
        # to control how the application runs.
        self.config_file = self.root / 'config.yml'

        # By default, this sends logs to a file in classic format.
        self.logfile = self.root / 'log.txt'

        # Load the default configuration.  We may write this out to the
        # root config_file, or might not.
        with ir.as_file(ir.files(xco2qc.core.data).joinpath('default_qc_config.yml')) as path:
            with path.open() as f:
                self.config = yaml.safe_load(f)

        self.socat_xml_file = self.root  # / 'socat.xml'
        self.socat_csv_file = self.root  # / 'socat.csv'

        self.socat_qf_log = self.merge_path / 'qflog.csv'

    def tearDown(self):
        shutil.rmtree(self.root)

        plt.close('all')

    def _write_config_file(self):

        if isinstance(self.config['QC']['start'], dt.datetime):
            self.config['QC']['start'] = self.config['QC']['start'].isoformat()
        if isinstance(self.config['QC']['stop'], dt.datetime):
            self.config['QC']['stop'] = self.config['QC']['stop'].isoformat()
        with self.config_file.open('wt') as f:
            yaml.dump(self.config, f)

    def get_qc_mask_varname(self, ds, varname):
        """
        Retrieve the name of the quality variable associated with this netCDF
        data variable.

        Parameters
        ----------
        ds : xarray.Dataset
        varname : str
            name of netCDF data variable
        """
        try:
            ancillary = ds[varname].ancillary_variables
        except AttributeError:
            # no ancillary variables, therefore no QC variable
            return None

        # by the CF convention, ancillary_variables is a space-delimited text
        # string of all the variables associated with the current variable
        for qcvarname in ancillary.split():

            if ds[qcvarname].standard_name == 'status_flag':
                return qcvarname

        # If we get through the loop, then there is no qc mask variable
        return None
