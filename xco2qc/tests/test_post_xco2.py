"""
This is the test suite for post XCO2 calculation scenarios.
"""

# standard library imports
import importlib.resources as ir

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.data_reduction import XCO2Reduce
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, calculate_post_xco2=True,
        licor_version='820 v1'
    ):

        # Run the processing up until the xco2 processing
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p:
                p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p:
                p.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(
                self.reduced_path,
                calculate_post_xco2=calculate_post_xco2,
                licor_version=licor_version
            ) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Process reduced LICOR data to produce post xCO2 @ RH
        (xCO2 wet), post xCO2 dry, pCO2, and updated span coefficient.

        EXPECTED RESULT:  The xCO2 is verified against VBA results.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # verify the calculated xCO2
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            actual = ds['post_xco2_wet'].values
            expected = np.array([
                np.nan, np.nan, 402.1558, 401.2424, 400.535, 399.9703
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['post_xco2_dry'].values
            expected = np.array([
                np.nan, np.nan, 402.7490, 401.7101, 401.0184, 400.4656
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['vapor_pressure'].values
            expected = np.array([
                np.nan, np.nan, 1.47286, 1.164336, 1.204243, 1.23694
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:

            index = pd.DatetimeIndex(
                data=[
                    '2013-11-05 15:00:00', '2013-11-05 18:00:00',
                    '2013-11-05 18:47:00', '2013-11-05 19:17:00',
                    '2013-11-05 19:47:00', '2013-11-05 20:17:00'
                ],
                name='time'
            )

            actual = ds['post_xco2_wet'].to_pandas()
            expected = pd.Series(
                index=index,
                data=[np.nan, np.nan, 377.4918, 370.7789, 369.4921, 365.9608],
                name='post_xco2_wet'
            )
            pd.testing.assert_series_equal(actual, expected, rtol=1e-4)

            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['post_xco2_dry'].to_pandas()
            expected = pd.Series(
                index=index,
                data=[np.nan, np.nan, 378.1909, 371.3655, 370.0922, 366.5613],
                name='post_xco2_dry'
            )
            pd.testing.assert_series_equal(actual, expected, rtol=1e-4)

            actual = ds['vapor_pressure'].to_pandas()
            expected = pd.Series(
                index=index,
                data=[np.nan, np.nan, 1.848418, 1.579811, 1.621606, 1.638268],
                name='vapor_pressure'
            )
            pd.testing.assert_series_equal(actual, expected, rtol=1e-4)

        # Verify the updated span coefficients.  The first two values are bad
        # because of missing temperature.
        ncfile = self.reduced_path / core.licor.SPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['updated_span_coefficient'][:]
            expected = np.array([0.907177, 0.904932, 0.903997, 0.903674])
            np.testing.assert_allclose(actual[2:], expected, rtol=1e-4)

            actual = nc['updated_span_coefficient_qc'][:]
            expected = np.array([
                core.quality.BAD_TEMPERATURE, core.quality.BAD_TEMPERATURE,
                core.quality.GOOD, core.quality.GOOD,
                core.quality.GOOD, core.quality.GOOD,
            ])
            np.testing.assert_allclose(actual, expected)

    def test__post_xco2_with_loss_of_span(self):
        """
        SCENARIO:  Process reduced LICOR data to produce post xCO2 @ RH
        (xCO2 wet), post xCO2 dry, pCO2, and updated span coefficient.
        NOTE: not obvious from code or raw file, but the last two span coefficients
        (of 4) are considered bad by the program.

        EXPECTED RESULT:  The xCO2 is verified against VBA results.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.loss_of_span.txt'
        )

        # Verify the updated span coefficients.  The first two values are bad
        # because of missing temperature, the last two could be construed as
        # bad because of loss of span, but we do want to impute there as well.
        ncfile = self.reduced_path / core.licor.SPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['updated_span_coefficient'][:]
            expected = np.array([0, 0, 0.907211, 0.904663, 0.903602, 0.903235])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = nc['updated_span_coefficient_qc'][:]
            expected = np.array([
                core.quality.BAD_TEMPERATURE, core.quality.BAD_TEMPERATURE,
                core.quality.GOOD, core.quality.GOOD,
                core.quality.GOOD, core.quality.GOOD,
            ])
            np.testing.assert_allclose(actual, expected)

        # verify the calculated xCO2.  Just the last four points are good.
        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            actual = ds['post_xco2_wet'].values
            expected = np.array([377.5397, 370.6461, 369.291, 365.7518])
            np.testing.assert_allclose(actual[2:], expected, rtol=1e-4)

        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['post_xco2_wet'][:]
            expected = np.array([377.5397, 370.6461, 369.291, 365.7518])
            np.testing.assert_allclose(actual[2:], expected, rtol=1e-4)

            # The QC should not be masked, i.e. no fill value
            actual = nc['post_xco2_wet_qc'][:]
            self.assertEqual(actual.mask.sum(), 0)

            # two missing values should be transferred over from pre to post
            expected = np.array([
                core.quality.MISSING_DATA, core.quality.MISSING_DATA,
                core.quality.GOOD, core.quality.GOOD,
                core.quality.GOOD, core.quality.GOOD,
            ])
            np.testing.assert_allclose(actual, expected)

            actual = nc['post_xco2_dry'][:]
            expected = np.array([378.2388, 371.2326, 369.9878, 366.4347])
            np.testing.assert_allclose(actual[2:], expected, rtol=1e-4)

            # The QC should not be masked, i.e. no fill value
            actual = nc['post_xco2_dry_qc'][:]
            self.assertEqual(actual.mask.sum(), 0)

            actual = nc['post_xco2_dry_qc'][:]
            expected = np.array([
                core.quality.MISSING_DATA, core.quality.MISSING_DATA,
                core.quality.GOOD, core.quality.GOOD,
                core.quality.GOOD, core.quality.GOOD,
            ])
            np.testing.assert_allclose(actual, expected)

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['post_xco2_wet'][:]
            expected = np.array([402.2169, 401.0595, 400.3338, 399.7355])
            np.testing.assert_allclose(actual[2:], expected, rtol=1e-3)

            actual = nc['post_xco2_dry'][:]
            expected = np.array([402.8102, 401.6720, 400.9032, 400.3232])
            np.testing.assert_allclose(actual[2:], expected, rtol=1e-3)

    def test_v2_post_xco2(self):
        """
        SCENARIO:  Process reduced LICOR data to produce orig xCO2 where we
        have v2 Licor.  STRATUS is such an example.

        EXPECTED RESULT:  The post (original) xCO2 is verified against VBA.
        The licor version number is recorded as an attribute.
        """
        self._processing_pipeline(
            'tests.data.mapco2.stratus',
            '0156_dp11_20180410_20190424.4.txt',
            licor_version='820 v2'
        )

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['post_xco2_wet'][:]
            expected = np.array([402.7276, 402.8909, 402.9832, 402.0384])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            self.assertEqual(nc['post_xco2_wet'].licor_version, 2)

            actual = nc['post_xco2_dry'][:]
            expected = np.array([404.5008, 404.7110, 404.7959, 404.0724])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

    def test_process_twice(self):
        """
        SCENARIO:  Run the xco2 processing twice.

        EXPECTED RESULT:  The xCO2 is verified against VBA results.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with PostXCO2Calc(self.reduced_path) as p2:
            p2.run()

        # verify the calculated xCO2
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['post_xco2_wet'][:]
            expected = np.array([
                np.nan, np.nan, 402.1558, 401.2424, 400.535, 399.9703,
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = nc['post_xco2_dry'][:]
            expected = np.array([
                np.nan, np.nan, 402.7490, 401.7101, 401.0184, 400.4656
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = nc['vapor_pressure'][:]
            expected = np.array([
                np.nan, np.nan, 1.47286, 1.164336, 1.204243, 1.23694
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['post_xco2_wet'][:]
            expected = np.array([
                np.nan, np.nan, 377.4918, 370.7789, 369.4921, 365.9608
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = nc['post_xco2_dry'][:]
            expected = np.array([
                np.nan, np.nan, 378.1909, 371.3655, 370.0922, 366.5613
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = nc['vapor_pressure'][:]
            expected = np.array([
                np.nan, np.nan, 1.848418, 1.579811, 1.621606, 1.638268
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

        ncfile = self.reduced_path / core.licor.SPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['updated_span_coefficient'][:]
            expected = np.array([
                np.nan, np.nan, 0.907177, 0.904932, 0.903997, 0.903674
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

    def test_decline_post_xco2(self):
        """
        SCENARIO:  The user declines to calculate post xco2.  This might happen
        if the regression is really bad.

        EXPECTED RESULT:  No post xco2 datasets are produced.  Vapor pressure,
        however, is processed.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            calculate_post_xco2=False
        )

        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            self.assertNotIn('post_xco2_wet', nc.variables.keys())
            self.assertIn('vapor_pressure', nc.variables.keys())


class TestSuiteSailDrone(test_core.TestSuite):

    def _processing_pipeline(self, module, filename, **kwargs):

        # Run the processing up until the xco2 processing
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            input_dir = inputfile.parents[0]

            with RawTextToRawNC(
                input_dir, dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path, verbosity='warning') as p2:
                p2.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Process reduced LICOR data to produce post xCO2 @ RH
        (xCO2 wet), post xCO2 dry, pCO2, and updated span coefficient.

        EXPECTED RESULT:  The xCO2 is verified against VBA results.
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        with PostXCO2Calc(self.reduced_path, calculate_post_xco2=True) as p:
            p.run()

        # verify the calculated xCO2
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['post_xco2_wet'][:]
            expected = np.array([398.9342, 399.02, 399.054902])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

    def test_new_coefficients(self):
        """
        SCENARIO:  Process reduced LICOR data to produce post xCO2 @ RH
        (xCO2 wet), post xCO2 dry, pCO2, and updated span coefficient, but
        change the licor coefficients.

        EXPECTED RESULT:  The xCO2 is verified.
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        with PostXCO2Calc(self.reduced_path, calculate_post_xco2=True) as p:
            p.config['licor_v830_coefficients']['a1'] = 0
            p.config['licor_v830_coefficients']['a2'] = 0
            p.config['licor_v830_coefficients']['a3'] = 1
            p.config['licor_v830_coefficients']['a4'] = 1
            p.run()

        # verify the calculated xCO2
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['post_xco2_wet'][:]
            expected = np.array([21.5436, 21.5498, 21.5506])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)
