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
from xco2qc.pre_xco2_processing import PreXCO2Calc
from . import test_core


class TestSuite(test_core.TestSuite):

    def __processing_chain(self, module, filename, **kwargs):

        # Run the processing up until the xco2 processing
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p2:
                p2.run()

    def test__pre_xco2_span2(self):
        """
        SCENARIO:  Process reduced LICOR data to produce xCO2 where the span2
        coefficient is not zero.

        EXPECTED RESULT:  The pre (original) xCO2 is verified against VBA.
        """
        self.__processing_chain(
            'tests.data.mapco2.stratus',
            '0156_dp11_20180410_20190424.4.txt'
        )

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['xco2_wet'][:]
            expected = np.array([402.72544, 403.04175, 402.82737, 401.99053])
            np.testing.assert_allclose(actual, expected)

            actual = nc['xco2_dry'][:]
            expected = np.array([404.49866, 404.86249, 404.6796, 404.02434])
            np.testing.assert_allclose(actual, expected)

    def test__pre_xco2(self):
        """
        SCENARIO:  Process reduced LICOR data to produce xCO2.

        EXPECTED RESULT:  The pre (original) xCO2 is verified against VBA.
        """
        self.__processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # verify the calculated xCO2
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['xco2_wet']
            expected = np.array([402.2116, 401.1142, 400.4746, 400.1147])
            np.testing.assert_allclose(actual[2:], expected, rtol=1e-3)

            actual = ds['xco2_dry']
            expected = np.array([402.804854, 401.5931, 400.9587, 400.6103])
            np.testing.assert_allclose(actual[2:], expected, rtol=1e-3)


class TestSuiteSailDrone(test_core.TestSuite):

    def _processing_chain(self, module, filename, **kwargs):

        # Run the processing up until the xco2 processing
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path, verbosity='warning') as p2:
                p2.run()

    def test_smoke(self):
        """
        SCENARIO:  Process reduced LICOR data.

        EXPECTED RESULT:  The xco2_dry is present.
        """
        self._processing_chain(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            self.assertIn('xco2_dry', ds)
