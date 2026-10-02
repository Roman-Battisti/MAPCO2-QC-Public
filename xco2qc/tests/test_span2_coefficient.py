# standard library imports
import importlib.resources as ir

# 3rd party library imports
import netCDF4
import numpy as np
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.span2_coefficient import CheckSpan2Coefficient, FixSpan2Coefficient
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(self, module, filename):
        """
        Shortcut for running just raw processing.
        """

        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
            ) as p0:
                p0.run()

    def test_nan(self):
        """
        SCENARIO:  The cycle header netCDF file has all NaN for the span2
        coefficient, which does not signify to replace the data.

        EXPECTED RESULT:  The zeros_detected flag is False.
        The different_values_detected_flag is False.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh', 'dp09_0014_20131105_20140802.met.txt',
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with CheckSpan2Coefficient(ncfile) as p:
            p.run()
            self.assertFalse(p.zeros_detected)
            self.assertFalse(p.different_values_detected)

    def test_zero_span(self):
        """
        SCENARIO:  The cycle header netCDF file has all zeros for the span2
        coefficient, which does signify to replace the data.

        EXPECTED RESULT:  The zero flag is True.  The different_values flag
        is False.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh', 'dp09_0014_20131105_20140802.met.txt',
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE

        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['span2_coefficient'][:] = 0

        with CheckSpan2Coefficient(ncfile) as p:
            p.run()
            self.assertTrue(p.zeros_detected)
            self.assertFalse(p.different_values_detected)

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with FixSpan2Coefficient(ncfile, span2=-0.2) as p:
            p.run()

        with xr.open_dataset(ncfile) as ds:
            data = ds['span2_coefficient'].values

            np.testing.assert_equal(data, np.full((6,), -0.2))

    def test_same_nonzero_number(self):
        """
        SCENARIO:  The cycle header netCDF file has the same non-zero number
        for the span2 coefficient.

        EXPECTED RESULT:  The zero_detected flag is False.  The
        different_values flag is False.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh', 'dp09_0014_20131105_20140802.met.txt',
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE

        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['span2_coefficient'][:] = 1

        with CheckSpan2Coefficient(ncfile) as p:
            p.run()
            self.assertFalse(p.zeros_detected)
            self.assertFalse(p.different_values_detected)

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with FixSpan2Coefficient(ncfile, span2=None) as p:
            p.run()

        with xr.open_dataset(ncfile) as ds:
            data = ds['span2_coefficient'].values

            np.testing.assert_equal(data, np.full((6,), 1))

            p.run()

    def test_all_different_non_zero(self):
        """
        SCENARIO:  The cycle header netCDF file has the different non-zero
        numbers for the span2 coefficient.

        EXPECTED RESULT:  The zero_detected flag is False.  The
        different_values flag is True.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh', 'dp09_0014_20131105_20140802.met.txt',
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE

        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['span2_coefficient'][:] = np.array([1, 2, 3, 4, 5, 6])

        with CheckSpan2Coefficient(ncfile) as p:
            p.run()
            self.assertFalse(p.zeros_detected)
            self.assertTrue(p.different_values_detected)
