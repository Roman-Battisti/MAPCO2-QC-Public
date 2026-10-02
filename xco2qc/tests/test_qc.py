"""
This test suite verifies that the QC module reproduces the same behavior as the
VBA QC module.  For the most part, this means that log messages are produced
when a condition violates thresholds.  In addition, we may validate quality
flags.
"""
# standard library imports
import importlib.resources as ir
import logging
import sys
import unittest

# 3rd party library imports
import netCDF4
import numpy as np
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.validation_data import ValidationData
import xco2qc.utilities
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, calculate_post_xco2=True, sbe16_mapping=False,
        external_sami=None, external_validation=None
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:
                p.run()

            if external_validation is not None:
                path = ir.files(module).joinpath(external_validation)
                with ValidationData(
                    path, self.raw_path, verbosity='INFO'
                ) as p:
                    p.run()

            with XCO2Reduce(
                self.raw_path, self.reduced_path, sbe16_mapping=sbe16_mapping
            ) as p:
                p.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(
                self.reduced_path, calculate_post_xco2=calculate_post_xco2
            ) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Run through the plots.

        EXPECTED RESULTS:  No errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(self.reduced_path, num_points_eachside=1) as p:
            p.run()

    def test__epoff__temperature__out_of_range(self):
        """
        SCENARIO:  epoff temperature is out of range

        EXPECTED RESULT:  The quality variable is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # replace the temperature
        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            data = np.array([np.nan, np.nan, 13.5, 14, 50.2, 14.3])
            nc['temperature'][:] = data

        with QCChecker(self.reduced_path, initial_span_cal=0) as o:
            o.check_valid_range()

        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            var = nc['temperature_qc']
            qc = var[:][:]

            actual = np.bitwise_and(qc, core.quality.OUT_OF_RANGE)

            # Only the last 4 values are strictly out of range.
            expected = np.array([
                core.quality.OUT_OF_RANGE, core.quality.OUT_OF_RANGE,
                0, 0,
                core.quality.OUT_OF_RANGE,
                0
            ])
            np.testing.assert_allclose(actual, expected)

    def test__xco2__span_out_of_range__flagging(self):
        """
        SCENARIO:  This is part d in the VBA QC procedure.  The default
        span value is not correct for this test file, so the xco2 is
        not in the span range.

        EXPECTED RESULT:  Logs messages are emitted.  The quality variable
        is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(self.reduced_path, initial_span_cal=0) as o:
            with self.assertLogs(o.logger, level=logging.WARNING):
                o.check_spoff_spostcal_xco2_in_span_range()

        for stem in [core.licor.SPOFF_NCFILE, core.licor.SPOSTCAL_NCFILE]:
            ncfile = self.reduced_path / stem

            with netCDF4.Dataset(ncfile) as nc:

                var = nc['xco2_wet_qc']
                xco2qc = var[:]

                actual = np.bitwise_and(xco2qc, core.quality.OUT_OF_SPAN_RANGE)

                # Only the last 4 values are strictly out of range.
                expected = np.array([
                    0,
                    0,
                    core.quality.OUT_OF_SPAN_RANGE,
                    core.quality.OUT_OF_SPAN_RANGE,
                    core.quality.OUT_OF_SPAN_RANGE,
                    core.quality.OUT_OF_SPAN_RANGE,
                ])
                np.testing.assert_allclose(actual, expected)

                # Those spots with bad QC should not have the GOOD flag set.
                actual = np.bitwise_and(xco2qc, core.quality.GOOD)
                expected = np.array([0, 0, 0, 0, 0, 0])
                np.testing.assert_allclose(actual, expected)

        # rerun with a more reasonable value.  no data should be out of span
        # range now
        with QCChecker(self.reduced_path, initial_span_cal=490) as o:
            o.check_spoff_spostcal_xco2_in_span_range()

        for stem in [core.licor.SPOFF_NCFILE, core.licor.SPOSTCAL_NCFILE]:
            ncfile = self.reduced_path / stem

            with netCDF4.Dataset(ncfile) as nc:

                var = nc['xco2_wet_qc']
                actual = var[:]
                actual = np.bitwise_and(actual, core.quality.OUT_OF_SPAN_RANGE)
                expected = np.full(actual.shape, 0)
                np.testing.assert_allclose(actual, expected)

    def test_seafet_ph_out_of_range(self):
        """
        SCENARIO:  A seafet PH variable has the 3rd value out of range.

        EXPECTED RESULT:  the seafet PH QC has its respective out of range flag
        flipped
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1.depl_11',
            'mapco2_cce1_0108_dp11_20181113_20190509.txt'
        )

        ncfile = self.reduced_path / core.SEAFET_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['ph'][:] = np.array([8, 8, 12, 8, 8, 8, 8, 8])

        with QCChecker(self.reduced_path) as p:
            p.check_valid_range()

        with netCDF4.Dataset(ncfile) as nc:

            var = nc['ph_qc']
            qc_data = var[:]

            actual = np.bitwise_and(qc_data, core.quality.OUT_OF_RANGE)
            expected = [
                0,
                0,
                core.quality.OUT_OF_RANGE,
                0,
                0,
                0,
                0,
                0,
            ]
            np.testing.assert_allclose(actual, expected)

            # that out of range point should not have the GOOD flag along
            # with it
            actual = np.bitwise_and(qc_data, core.quality.GOOD)
            expected = [
                core.quality.GOOD,
                core.quality.GOOD,
                0,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
            ]
            np.testing.assert_allclose(actual, expected)

    def test_sami_ph_out_of_range(self):
        """
        SCENARIO:  A sami PH variable has the 3rd value out of range.

        EXPECTED RESULT:  the sami PH QC has its respective out of range flag
        flipped
        """
        self._processing_pipeline(
            'tests.data.mapco2.stratus', '0156_dp11_20180410_20190424.4.txt'
        )

        ncfile = self.reduced_path / core.SAMI_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['ph'][:] = np.array([8, 8, 12, 8])

        with QCChecker(self.reduced_path) as p:
            p.check_valid_range()

        with netCDF4.Dataset(ncfile) as nc:

            var = nc['ph_qc']
            qc_data = var[:]

            actual = np.bitwise_and(qc_data, core.quality.OUT_OF_RANGE)
            expected = [
                0,
                0,
                core.quality.OUT_OF_RANGE,
                0,
            ]
            np.testing.assert_allclose(actual, expected)

            # that out of range point should not have the GOOD flag along
            # with it
            actual = np.bitwise_and(qc_data, core.quality.GOOD)
            expected = [
                core.quality.GOOD,
                core.quality.GOOD,
                0,
                core.quality.GOOD,
            ]
            np.testing.assert_allclose(actual, expected)

    def test_durafet_ph(self):
        """
        SCENARIO:  We have an out of range PH data point from a durafet sensor.

        EXPECTED RESULT:  The QC flags are all good except for that one point.
        """
        self._processing_pipeline(
            'tests.data.mapco2.asv', 'pco2asv_sd1006.3.full.txt'
        )

        ncfile = self.reduced_path / core.DURAFET_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['ph_int'][:] = np.array([7.4, 7.5, 7.9])

        with QCChecker(self.reduced_path) as p:
            p.check_valid_range()

        with netCDF4.Dataset(ncfile) as nc:

            var = nc['ph_int_qc']
            actual = var[:]
            actual = np.bitwise_and(actual, core.quality.OUT_OF_RANGE)
            expected = [
                core.quality.OUT_OF_RANGE, 0, 0
            ]
            np.testing.assert_allclose(actual.data, expected)

    def test__xco2__spostcal_span_in_range__parameter__flagging(self):
        """
        SCENARIO:  Standard level 2 processing for SPOFF and SPOSTCAL.
        This is part d in the VBA QC procedure.  A non-default span value is
        provided via parameter that results in 3 of 4 values being in
        range.

        EXPECTED RESULT:  The xCO2_wet_qc variable shows the first two values
        as missing, the next value out of span range, but the remaining three
        being ok.
        """
        # This is not quite enough to snare the first xco2 value, but it will
        # get the next three.
        initial_span_cal = 486

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(
            self.reduced_path, initial_span_cal=initial_span_cal
        ) as p:
            p.check_spoff_spostcal_xco2_in_span_range()

        ncfile = self.reduced_path / core.licor.SPOSTCAL_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            var = nc['xco2_wet_qc']
            actual = var[:]
            actual = np.bitwise_and(actual, core.quality.OUT_OF_SPAN_RANGE)
            expected = [
                0,
                0,
                core.quality.OUT_OF_SPAN_RANGE,
                0,
                0,
                0,
            ]
            np.testing.assert_allclose(actual, expected)

    def test__xco2__spostcal_span_in_range__param__flagging(self):
        """
        SCENARIO:  Standard level 2 processing for SPOFF and SPOSTCAL.
        This is part d in the VBA QC procedure.  A non-default span value is
        provided that results in 3 of 4 values being in range.  The range is
        supplied via parameter.

        EXPECTED RESULT:  The xCO2_wet_qc variable shows the first two values
        as missing, the next value out of span range, but the remaining three
        being ok.
        """

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(
            self.reduced_path,
            ppm_below_span_cal=10,
            ppm_above_span_cal=10,
            initial_span_cal=486,
        ) as o:
            o.check_spoff_spostcal_xco2_in_span_range()

        ncfile = self.reduced_path / core.licor.SPOSTCAL_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            var = nc['xco2_wet_qc']
            actual = var[:]
            actual = np.bitwise_and(actual, core.quality.OUT_OF_SPAN_RANGE)
            expected = [
                0,
                0,
                core.quality.OUT_OF_SPAN_RANGE,
                0,
                0,
                0,
            ]
            np.testing.assert_allclose(actual, expected)

    def test__xco2__spostcal_span_in_range__flagging(self):
        """
        SCENARIO:  Standard level 2 processing for SPOFF and SPOSTCAL.
        This is part d in the VBA QC procedure.  A non-default span value is
        provided that results in 3 of 4 values being in range.

        EXPECTED RESULT:  The xCO2_wet_qc variable shows the first value as
        missing, the next out of span range, but the remaining three being ok.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # This is not quite enough to snare the first xco2 value, but it will
        # get the next three.
        with QCChecker(self.reduced_path, initial_span_cal=486) as o:
            with self.assertLogs(o.logger, level=logging.WARNING):
                o.check_spoff_spostcal_xco2_in_span_range()

        ncfile = self.reduced_path / core.licor.SPOSTCAL_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            var = nc['xco2_wet_qc']
            actual = var[:]
            actual = np.bitwise_and(actual, core.quality.OUT_OF_SPAN_RANGE)
            expected = [
                0,
                0,
                core.quality.OUT_OF_SPAN_RANGE,
                0,
                0,
                0
            ]
            np.testing.assert_allclose(actual, expected)

    def test_loss_of_span(self):
        """
        SCENARIO:  Loss of span has been recorded.

        EXPECTED RESULT:  Log messages are emitted.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.loss_of_span.txt'
        )

        with QCChecker(self.reduced_path) as o:
            with self.assertLogs(o.logger, level=logging.WARNING):
                o.check_loss_of_span()

    def test_xco2_in_zpoff(self):
        """
        SCENARIO:  Standard level 2 processing for ZPOFF.  Alter the bounds
        for xCO2 ppm below zero to flag the first data point, which would
        otherwise report as -4.8.

        EXPECTED RESULT:  The xCO2 matches VBA results.  The ZPOFF valid range
        is set properly.
        """

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        ppm_below_zero, ppm_above_zero = 3, 3
        with QCChecker(
            self.reduced_path,
            ppm_above_zero=ppm_above_zero,
            ppm_below_zero=ppm_below_zero
        ) as o:
            o.check_zpoff_xco2_range()

        ncfile = self.reduced_path / core.licor.ZPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # Even though a data point may be flagged in the qc variable, don't
            # allow that to change the data variable itself.
            # The spike detection had been changing the data.
            xco2_var = nc['xco2_wet']
            actual = xco2_var[:]
            expected = np.array([np.nan, -0.91, -0.61, -0.59])
            np.testing.assert_allclose(actual, expected, rtol=1e-2)

            actual = nc['xco2_wet_qc'][:]
            actual = np.bitwise_and(actual, core.quality.OUT_OF_RANGE)
            expected = np.full((4,), 0)
            expected[0] = core.quality.OUT_OF_RANGE
            np.testing.assert_allclose(actual, expected)

            # Verify the valid range.
            actual = xco2_var.valid_range
            expected = [-ppm_below_zero, ppm_above_zero]
            np.testing.assert_allclose(actual, expected)

    def test_xco2_in_zpoff__via_parameter(self):
        """
        SCENARIO:  Standard level 2 processing for ZPOFF.  Alter the bounds
        for xCO2 ppm below zero to flag the first data point, which would
        otherwise report as -4.8.  Do this via a parameter, not the
        configuration file.

        EXPECTED RESULT:  The xCO2 matches VBA results.  The ZPOFF valid range
        is set properly.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        ppm_below_zero, ppm_above_zero = 0.90, 3
        with QCChecker(
            self.reduced_path,
            ppm_below_zero=ppm_below_zero,
            ppm_above_zero=ppm_above_zero
        ) as p:
            p.check_zpoff_xco2_range()

        ncfile = self.reduced_path / core.licor.ZPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # Even though a data point may be flagged in the qc variable, don't
            # allow that to change the data variable itself.
            # The spike detection had been changing the data.
            xco2_var = nc['xco2_wet']
            actual = xco2_var[:]
            expected = np.array([np.nan, np.nan, -0.61, -0.59])
            np.testing.assert_allclose(actual, expected, rtol=1e-2)

            actual = nc['xco2_wet_qc'][:]
            actual = np.bitwise_and(actual, core.quality.OUT_OF_RANGE)
            expected = np.array([
                core.quality.OUT_OF_RANGE, core.quality.OUT_OF_RANGE, 0, 0
            ])

            np.testing.assert_allclose(actual, expected)

            # Verify the valid range.
            actual = xco2_var.valid_range
            expected = [-1 * ppm_below_zero, ppm_above_zero]
            np.testing.assert_allclose(actual, expected)

        # Go again with a different PPM that should trip one value.
        ppm_below_zero = 4
        with QCChecker(
            self.reduced_path,
            ppm_below_zero=ppm_below_zero,
            ppm_above_zero=ppm_above_zero
        ) as p:
            p.check_zpoff_xco2_range()

        ncfile = self.reduced_path / core.licor.ZPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['xco2_wet_qc'][:]
            actual = np.bitwise_and(actual, core.quality.OUT_OF_RANGE)
            expected = np.array([
                core.quality.OUT_OF_RANGE, 0, 0, 0
            ])
            np.testing.assert_allclose(actual, expected)

    def test_xco2_in_zpostcal(self):
        """
        SCENARIO:  Standard level 2 processing for ZPOSTCAL.

        EXPECTED RESULT:  The ZPOFF valid range is set properly and the QC
        is all good.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        with QCChecker(self.reduced_path) as o:
            o.check_zpostcal_xco2_range()

        ncfile = self.reduced_path / core.licor.ZPOSTCAL_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['xco2_wet_qc'][:]
            expected = np.array([0, 0, 0, 0])
            np.testing.assert_allclose(
                np.bitwise_and(actual, core.quality.OUT_OF_RANGE),
                expected
            )

            # Verify the valid range.
            actual = nc['xco2_wet'].valid_range
            expected = [
                -self.config['QC']['ppm_below_zero'],
                self.config['QC']['ppm_above_zero']
            ]
            np.testing.assert_allclose(actual, expected)

    def test_EPOFF_xco2_wet_all_ok(self):
        """
        SCENARIO:  Standard level 2 processing for EPOFF.  The xco2 is within
        thresholds.

        EXPECTED RESULT:  No logs are emitted.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with self.assertRaises(AssertionError):

            # A bit of a hack.  assertLogs is what throws the assertion
            # error (since it expects logs to be emitted), not the
            # application itself.
            with QCChecker(
                self.reduced_path, verbosity='INFO', num_points_eachside=1
            ) as o:
                with self.assertLogs(o.logger, level=logging.WARNING):
                    o.check_epoff_xco2_stddev()

    def test_whots_dp13(self):
        """
        SCENARIO:  Run whots dp13

        EXPECTED RESULT:  No errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots.dp13', 'mapco2.txt',
            external_validation='bottle.csv'
        )

        with QCChecker(
            self.reduced_path,
            verbosity='INFO'
        ) as o:
            o.run()

    def test_APOFF_xco2_stddev_window_size_is_floating_point(self):
        """
        SCENARIO:  The xco2 STD is out of range for the specified STD
        in exactly one spot.  APOFF only.  The STD range is specified via
        parameter.

        EXPECTED RESULT:  We do not error out due to the floating point window
        size.  The quality is all good except for the first two points
        (missing data).
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        with QCChecker(
            self.reduced_path,
            num_points_eachside=8.0,
            verbosity='INFO'
        ) as o:
            o.check_apoff_xco2_stddev()

            ncfile = self.reduced_path / core.licor.APOFF_NCFILE
            with netCDF4.Dataset(ncfile) as nc:
                actual = nc['xco2_wet_qc'][:]

                expected = np.full((50,), core.quality.GOOD)
                expected[:2] = core.quality.MISSING_DATA

            np.testing.assert_allclose(actual, expected)

    def test_APOFF_xco2_stddev_out_of_range_via_parameter(self):
        """
        SCENARIO:  The xco2 STD is out of range for the specified STD
        in exactly one spot.  APOFF only.  The STD range is specified via
        parameter.

        EXPECTED RESULT:  The quality flag QUALITY_RAW_STDDEV_OUT_OF_RANGE is
        set accordingly.
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        with QCChecker(
            self.reduced_path,
            max_air_xco2_std=0.51,
            num_points_eachside=1,
            verbosity='INFO'
        ) as o:
            o.check_apoff_xco2_stddev()

            ncfile = self.reduced_path / core.licor.APOFF_NCFILE
            with netCDF4.Dataset(ncfile) as nc:
                qc = nc['xco2_wet_qc'][:]

                # restrict ourselves to only checking for bad raw std values
                actual = np.bitwise_and(
                    qc, core.quality.RAW_STDDEV_OUT_OF_RANGE
                )

                expected = np.full((50,), 0)
                expected[6] = core.quality.RAW_STDDEV_OUT_OF_RANGE

                np.testing.assert_allclose(actual, expected)

                # The RAW_STDDEV_OUT_OF_RANGE item is present in the metadata
                self.assertIn(
                    'trend_stddev_out_of_range',
                    nc['xco2_wet_qc'].flag_meanings
                )

    def test_EPOFF_xco2_stddev_out_of_range__via_parameter(self):
        """
        SCENARIO:  The xco2 STD is out of range for the specified STD
        in exactly one spot.  EPOFF only.  Specified via parameter, not the
        configuration file.

        EXPECTED RESULT:  The quality flag QUALITY_RAW_STDDEV_OUT_OF_RANGE is
        set accordingly.
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        with QCChecker(
            self.reduced_path,
            max_equil_xco2_std=0.64,
            num_points_eachside=1,
            verbosity='INFO'
        ) as o:
            o.check_epoff_xco2_stddev()

            ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
            with netCDF4.Dataset(ncfile) as nc:
                actual = nc['xco2_wet_qc'][:]

                # restrict ourselves to only checking for bad raw std values
                actual = np.bitwise_and(
                    actual, core.quality.RAW_STDDEV_OUT_OF_RANGE
                )

                expected = np.full((50,), 0)
                expected[33] = core.quality.RAW_STDDEV_OUT_OF_RANGE

            np.testing.assert_allclose(actual, expected)

    def test_EPOFF_xco2_wet__raw_std_exceeds_bounds(self):
        """
        SCENARIO:  Standard level 2 processing for EPOFF.  The standard
        deviation at the raw level exceeds thresholds.

        EXPECTED RESULT:  Logs are emitted at the warning level.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # alter the stddev here rather that create a whole new set of inputs
        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile, 'r+') as nc:
            nc['xco2_wet_stddev'][:] = np.array([0.1, 25.0, 0.1, 0.1])

        with QCChecker(
            self.reduced_path, verbosity='INFO', num_points_eachside=1
        ) as o:
            with self.assertLogs(o.logger, level=logging.WARNING):
                o.check_epoff_xco2_stddev()

    def test_EPOFF_xco2_wet__trend_exceeds_bounds__parameter(self):
        """
        SCENARIO:  Standard level 2 processing for EPOFF.  The windowed
        standard deviation (trend) exceeds thresholds.  The threshold is
        supplied via parameter.

        EXPECTED RESULT:  The quality flags are set.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            num_points_eachside=1,
            xco2_trend_std=0.6
        ) as o:
            o.check_epoff_xco2_stddev()

        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['xco2_wet_qc'][:]
            actual = np.bitwise_and(
                actual, core.quality.TREND_STDDEV_OUT_OF_RANGE
            )

            expected = np.full((6,), 0)
            expected[-1] = core.quality.TREND_STDDEV_OUT_OF_RANGE

            np.testing.assert_allclose(actual, expected)

    def test_EPOFF_xco2_wet__trend_exceeds_bounds__config_file(self):
        """
        SCENARIO:  Standard level 2 processing for EPOFF.  The windowed
        standard deviation (trend) exceeds thresholds.  The threshold is
        supplied via config file

        EXPECTED RESULT:  Logs are emitted at the warning level.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # This xco2_trend_std value is an extremely low threshold.
        with QCChecker(
            self.reduced_path,
            num_points_eachside=1,
            xco2_trend_std=0.01,
            verbosity='INFO'
        ) as o:
            with self.assertLogs(o.logger, level=logging.WARNING):
                o.check_epoff_xco2_stddev()

    def test_APOFF_SPOFF_EPOFF_pressure_differences_ok(self):
        """
        SCENARIO:  The pressure differences between APOFF, SPOFF, and EPOFF
        are within bounds.

        EXPECTED RESULT:  No logs are emitted.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with self.assertRaises(AssertionError):

            # A bit of a hack.  assertLogs is what throws the assertion
            # error (since it expects logs to be emitted), not the
            # application itself.  The assertion error is only issued if
            # NO logs are emitted, which is what we want.

            with QCChecker(self.reduced_path, verbosity='INFO') as o:
                with self.assertLogs(o.logger, level=logging.WARNING):
                    o.check_apoff_spoff_epoff_pressure_differences()

    def test_APOFF_pressure_differences_against_EPOFF_SPOFF_parameter(self):
        """
        SCENARIO:  APOFF has a spike in pressure data that exceeds bounds as
        compared to EPOFF and SPOFF.  The maximum allowed value is passed as
        a parameter.

        EXPECTED RESULT:  The proper quality flags are recorded.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc1:  # noqa : E501
            apress = nc1['pressure'][:]

            nc_spoff = self.reduced_path / core.licor.SPOFF_NCFILE
            with netCDF4.Dataset(nc_spoff) as nc2:
                spress = nc2['pressure'][:]

            max_pressoff_diff = 0.4
            apress[2] = spress[2] - max_pressoff_diff * 2

            nc1['pressure'][:] = apress

        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            max_pressoff_diff=max_pressoff_diff
        ) as o:
            with self.assertLogs('xco2qc.qc', level=logging.WARNING):
                o.check_apoff_spoff_epoff_pressure_differences()

        # Verify that QC flags are properly recorded.
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['pressure_qc'][:]
            actual = np.bitwise_and(
                actual,
                core.quality.EXCESS_PRESSURE_OFF_DIFFERENCE
            )
            expected = np.array([
                0,
                0,
                core.quality.EXCESS_PRESSURE_OFF_DIFFERENCE,
                0,
                0,
                0
            ])

            np.testing.assert_allclose(actual, expected)

    def test_APOFF_pressure_differences_against_EPOFF_SPOFF_config_file(self):
        """
        SCENARIO:  APOFF has a spike in pressure data that exceeds bounds as
        compared to EPOFF and SPOFF.

        EXPECTED RESULT:  Log messages are emitted at the WARNING level and
        the proper quality flags are recorded.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc1:  # noqa : E501
            apress = nc1['pressure'][:]

            nc_spoff = self.reduced_path / core.licor.SPOFF_NCFILE
            with netCDF4.Dataset(nc_spoff) as nc2:
                spress = nc2['pressure'][:]

            # force the difference at one data point to be at least twice the
            # threshold
            max_pressoff_diff = 4
            apress[2] = spress[2] - max_pressoff_diff * 2

            nc1['pressure'][:] = apress

        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            max_pressoff_diff=max_pressoff_diff
        ) as o:
            with self.assertLogs('xco2qc.qc', level=logging.WARNING):
                o.check_apoff_spoff_epoff_pressure_differences()

        # Verify that QC flags are properly recorded.
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['pressure_qc'][:]
            actual = np.bitwise_and(
                actual,
                core.quality.EXCESS_PRESSURE_OFF_DIFFERENCE
            )
            expected = np.array([
                0,
                0,
                core.quality.EXCESS_PRESSURE_OFF_DIFFERENCE,
                0,
                0,
                0
            ])

            np.testing.assert_allclose(actual, expected)

    def test_EPOFF_EPONN_pressure_differences_ok(self):
        """
        SCENARIO:  EPOFF and EPON pressure differences are within bounds.

        EXPECTED RESULT:  No logs are emitted.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # For this particular dataset, the pressure differences ARE significant
        # so set the epoff pressure half-way into the expected range, where it
        # is expected to be.
        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc1:  # noqa : E501
            ncfile1 = self.reduced_path / core.licor.EPON_NCFILE
            with netCDF4.Dataset(ncfile1) as nc2:
                press2 = nc2['pressure'][:]

            equil_diff_range_lower, equil_diff_range_higher = 6, 8
            delta = (equil_diff_range_higher + equil_diff_range_lower) / 2
            press1 = press2 + delta
            nc1['pressure'][:] = press1

        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            equil_diff_range_lower=equil_diff_range_lower,
            equil_diff_range_higher=equil_diff_range_higher
        ) as qc:

            # A bit of a hack.  assertLogs is what throws the assertion
            # error (since it expects logs to be emitted), not the
            # application itself.
            with self.assertRaises(AssertionError):
                with self.assertLogs(qc.logger, level=logging.WARNING):
                    qc.check_epoff_epon_pressure_differences()

        # Verify that QC flags are properly recorded.
        for path in [core.licor.EPON_NCFILE, core.licor.EPOFF_NCFILE]:
            ncfile = self.reduced_path / path
            with netCDF4.Dataset(ncfile) as nc:
                actual = nc['pressure_qc'][:]
                actual = np.bitwise_and(
                    actual, core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE
                )
                expected = np.full(actual.shape, 0)

                np.testing.assert_allclose(actual, expected)

    def test_SPOFF_SPONN_pressure_differences_not_ok_specified_parameter(self):
        """
        SCENARIO:  SPOFF and SPON pressure differences are not within bounds
        specified via a parameter.

        EXPECTED RESULT:  QC is good
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.reduced_path / core.licor.SPOFF_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc1:  # noqa : E501
            ncfile1 = self.reduced_path / core.licor.SPON_NCFILE
            with netCDF4.Dataset(ncfile1) as nc2:
                press2 = nc2['pressure'][:]

            span_diff_range_lower = 3.5
            span_diff_range_higher = 4.5

            delta = span_diff_range_lower - 1
            press1 = press2 + delta
            nc1['pressure'][:] = press1

        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            span_diff_range_lower=span_diff_range_lower,
            span_diff_range_higher=span_diff_range_higher,
        ) as qc:
            qc.check_spoff_spon_pressure_differences()

        # Verify that QC flags are properly recorded.
        for path in [core.licor.SPON_NCFILE, core.licor.SPOFF_NCFILE]:
            ncfile = self.reduced_path / path
            with netCDF4.Dataset(ncfile) as nc:
                actual = nc['pressure_qc'][:]

                # the 1st two values are missing, let's handle them separately
                expected = np.array([
                    core.quality.MISSING_DATA,
                    core.quality.MISSING_DATA,
                ])
                np.testing.assert_allclose(actual[:2], expected)

                # now look at the remaining
                actual = np.bitwise_and(
                    actual, core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE
                )

                expected = np.array([
                    0,
                    0,
                    core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE,
                ])

                np.testing.assert_allclose(actual, expected)

    def test_SPOFF_SPONN_pressure_differences_ok_specified_via_parameter(self):
        """
        SCENARIO:  SPOFF and SPON pressure differences are within bounds
        specified via a parameter.

        EXPECTED RESULT:  QC is good
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.reduced_path / core.licor.SPOFF_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc1:  # noqa : E501
            ncfile1 = self.reduced_path / core.licor.SPON_NCFILE

            with netCDF4.Dataset(ncfile1) as nc2:
                press2 = nc2['pressure'][:]

            span_diff_range_lower = 3.5
            span_diff_range_higher = 4.5
            delta = span_diff_range_lower + (
                span_diff_range_higher - span_diff_range_lower
            ) / 2
            press1 = press2 + delta

            nc1['pressure'][:] = press1

        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            span_diff_range_lower=span_diff_range_lower,
            span_diff_range_higher=span_diff_range_higher,
        ) as qc:
            qc.check_spoff_spon_pressure_differences()

        # Verify that QC flags are properly recorded.
        for path in [core.licor.SPON_NCFILE, core.licor.SPOFF_NCFILE]:
            ncfile = self.reduced_path / path
            with netCDF4.Dataset(ncfile) as nc:
                actual = nc['pressure_qc'][:]
                actual = np.bitwise_and(
                    actual, core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE
                )

                expected = np.full(actual.shape, 0)

                np.testing.assert_allclose(actual, expected)

    def test_EPOFF_EPONN_pressure_differences_ok_specified_via_parameter(self):
        """
        SCENARIO:  EPOFF and EPON pressure differences are within bounds
        specified via parameter.

        EXPECTED RESULT:  No logs are emitted.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # For this particular dataset, the pressure differences ARE significant
        # so set the epoff pressure half-way into the expected range, where it
        # is expected to be.
        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc1:  # noqa : E501
            ncfile1 = self.reduced_path / core.licor.EPON_NCFILE

            with netCDF4.Dataset(ncfile1) as nc2:
                press2 = nc2['pressure'][:]

            equil_diff_range_lower = 8
            equil_diff_range_higher = 9
            delta = equil_diff_range_lower + (
                equil_diff_range_higher - equil_diff_range_lower
            ) / 2
            press1 = press2 + delta
            nc1['pressure'][:] = press1

        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            equil_diff_range_lower=equil_diff_range_lower,
            equil_diff_range_higher=equil_diff_range_higher,
        ) as qc:
            qc.check_epoff_epon_pressure_differences()

        # Verify that QC flags are properly recorded.
        for path in [core.licor.EPON_NCFILE, core.licor.EPOFF_NCFILE]:
            ncfile = self.reduced_path / path
            with netCDF4.Dataset(ncfile) as nc:
                actual = nc['pressure_qc'][:]
                actual = np.bitwise_and(
                    actual, core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE
                )
                expected = np.full(actual.shape, 0)

                np.testing.assert_allclose(actual, expected)

    def test_EPOFF_EPONN_pressure_differences_not_ok__parameter(self):
        """
        SCENARIO:  EPOFF and EPON pressure differences are not within bounds
        specified via parameter.

        EXPECTED RESULT:  No logs are emitted.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        equil_diff_range_lower = 10
        equil_diff_range_higher = 12

        # For this particular dataset, the pressure differences ARE significant
        # so set the epoff pressure half-way into the expected range, where it
        # is expected to be.
        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc1:  # noqa : E501
            ncfile1 = self.reduced_path / core.licor.EPON_NCFILE
            with netCDF4.Dataset(ncfile1) as nc2:
                press2 = nc2['pressure'][:]
            press1 = press2 + equil_diff_range_higher * 2
            nc1['pressure'][:] = press1

        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            equil_diff_range_lower=equil_diff_range_lower,
            equil_diff_range_higher=equil_diff_range_higher,
        ) as qc:
            qc.check_epoff_epon_pressure_differences()

        # Verify that QC flags are properly recorded.
        for path in [core.licor.EPON_NCFILE, core.licor.EPOFF_NCFILE]:
            ncfile = self.reduced_path / path
            with netCDF4.Dataset(ncfile) as nc:
                actual = nc['pressure_qc'][:]
                actual = np.bitwise_and(
                    actual, core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE
                )

                expected = np.array([
                    0,
                    0,
                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE,
                ])

                np.testing.assert_allclose(actual, expected)

        # Rerun the test with a higher pressure difference allowed.  It should
        # clear the flags.
        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            equil_diff_range_lower=equil_diff_range_lower,
            equil_diff_range_higher=25,
        ) as qc:
            qc.check_epoff_epon_pressure_differences()

        for path in [core.licor.EPON_NCFILE, core.licor.EPOFF_NCFILE]:
            ncfile = self.reduced_path / path
            with netCDF4.Dataset(ncfile) as nc:
                actual = nc['pressure_qc'][:]
                actual = np.bitwise_and(
                    actual, core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE
                )

                expected = np.full(actual.shape, 0)

                np.testing.assert_allclose(actual, expected)

    def test_APOFF_APON_pressure_differences_not_by_default(self):
        """
        SCENARIO:  APOFF and APON pressure differences normally would not be ok
        but we pass in a larger difference range than the default.

        EXPECTED RESULT:  No bad quality flags are recorded.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(
            self.reduced_path,
            verbosity='INFO',
            air_diff_range_lower=6,
            air_diff_range_higher=9,
        ) as qc:
            qc.check_apoff_apon_pressure_differences()

        # Verify that QC flags are properly recorded.
        # AIR_PUMP_PRESSURE_DIFFERENCE should not have been recorded.
        for stem in [core.licor.APOFF_NCFILE, core.licor.APON_NCFILE]:
            with netCDF4.Dataset(self.reduced_path / stem) as nc:
                actual = nc['pressure_qc'][:]
                actual = np.bitwise_and(
                    actual,
                    core.quality.AIR_PUMP_PRESSURE_DIFFERENCE
                )
                expected = np.full(actual.shape, 0)
            np.testing.assert_allclose(actual, expected)

    def test_APOFF_APON_pressure_differences_out_of_bounds(self):
        """
        SCENARIO:  APOFF and APON pressure differences are too large.

        EXPECTED RESULT:  Logs are emitted at the warning level.  The proper
        QC flags are recorded.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # Modify the apoff data to be out of range.
        apon_ncfile = self.reduced_path / core.licor.APON_NCFILE
        apoff_ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(apon_ncfile) as nc1:

            apon_press = nc1['pressure'][:]

            air_diff_range_higher, air_diff_range_lower = 4, 2

            with netCDF4.Dataset(apoff_ncfile, mode='r+') as nc2:
                press = apon_press + air_diff_range_higher * 2
                nc2['pressure'][:] = press

        with QCChecker(
            self.reduced_path,
            air_diff_range_higher=air_diff_range_higher,
            air_diff_range_lower=air_diff_range_lower,
            verbosity='INFO'
        ) as qc:
            with self.assertLogs(qc.logger, level=logging.WARNING):
                qc.check_apoff_apon_pressure_differences()

        # Verify that QC flags are properly recorded.
        for stem in [core.licor.APOFF_NCFILE, core.licor.APON_NCFILE]:
            with netCDF4.Dataset(self.reduced_path / stem) as nc:
                actual = nc['pressure_qc'][:]

                # Only look for QUALITY_AIR_PUMP_PRESSURE_DIFFERENCE
                actual = np.bitwise_and(
                    actual,
                    core.quality.AIR_PUMP_PRESSURE_DIFFERENCE
                )
                expected = [
                    0,
                    0,
                    core.quality.AIR_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.AIR_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.AIR_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.AIR_PUMP_PRESSURE_DIFFERENCE,
                ]

            np.testing.assert_allclose(actual, expected)

    def test_SPOFF_SPON_pressure_differences_out_of_bounds(self):
        """
        SCENARIO:  EPOFF and EPON pressure differences are too large.

        EXPECTED RESULT:  Logs are emitted at the warning level.  The proper
        QC flags are recorded.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # Modify the spoff data to be out of range.
        spon_ncfile = self.reduced_path / core.licor.SPON_NCFILE
        spoff_ncfile = self.reduced_path / core.licor.SPOFF_NCFILE
        with netCDF4.Dataset(spon_ncfile) as nc1:

            spon_press = nc1['pressure'][:]

            span_diff_range_higher, span_diff_range_lower = 2, 1

            with netCDF4.Dataset(spoff_ncfile, mode='r+') as nc2:
                press = spon_press + span_diff_range_higher * 2
                nc2['pressure'][:] = press

        with QCChecker(
            self.reduced_path,
            span_diff_range_higher=span_diff_range_higher,
            span_diff_range_lower=span_diff_range_lower,
            verbosity='INFO'
        ) as qc:
            with self.assertLogs(qc.logger, level=logging.WARNING):
                qc.check_spoff_spon_pressure_differences()

        # Verify that QC flags are properly recorded.
        for stem in [core.licor.SPOFF_NCFILE, core.licor.SPON_NCFILE]:
            with netCDF4.Dataset(self.reduced_path / stem) as nc:
                actual = nc['pressure_qc'][:]
                actual = np.bitwise_and(
                    actual,
                    core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE
                )
                expected = [
                    0,
                    0,
                    core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.SPAN_PUMP_PRESSURE_DIFFERENCE
                ]

            np.testing.assert_allclose(actual, expected)

    def test_EPOFF_EPON_pressure_differences_out_of_bounds(self):
        """
        SCENARIO:  EPOFF and EPON pressure differences are too large.

        EXPECTED RESULT:  Logs are emitted at the warning level.  The proper
        QC flags are recorded.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # Modify the epoff data to be out of range.
        epon_ncfile = self.reduced_path / core.licor.EPON_NCFILE
        epoff_ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(epon_ncfile) as nc1:

            epon_press = nc1['pressure'][:]

            equil_diff_range_higher, equil_diff_range_lower = 2, 1
            with netCDF4.Dataset(epoff_ncfile, mode='r+') as nc2:
                press = epon_press + equil_diff_range_higher * 2
                nc2['pressure'][:] = press

        with QCChecker(
            self.reduced_path,
            equil_diff_range_higher=equil_diff_range_higher,
            equil_diff_range_lower=equil_diff_range_lower,
            verbosity='INFO'
        ) as qc:
            with self.assertLogs(qc.logger, level=logging.WARNING):
                qc.check_epoff_epon_pressure_differences()

        # Verify that QC flags are properly recorded.
        for stem in [core.licor.EPOFF_NCFILE, core.licor.EPON_NCFILE]:
            with netCDF4.Dataset(self.reduced_path / stem) as nc:
                actual = nc['pressure_qc'][:]
                actual = np.bitwise_and(
                    actual,
                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE
                )
                expected = [
                    0,
                    0,
                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE,
                    core.quality.EQUILIBRATOR_PUMP_PRESSURE_DIFFERENCE
                ]

            np.testing.assert_allclose(actual, expected)

    def test__salinity__valid_range(self):
        """
        SCENARIO:  QC an NH dataset.  The sst, conductivity, and salinity
        variables each have a data point outside the valid range.
        The bad point is the 2nd of 3.

        EXPECTED RESULT:  The OUT_OF_RANGE quality bit is set.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.salinity_out_of_range.txt'
        )

        with QCChecker(self.reduced_path) as o:
            o.check_valid_range()

        ncfile = self.reduced_path / core.MET_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            expected = np.array([
                0, core.quality.OUT_OF_RANGE, 0,
            ])

            for var in [
                'conductivity', 'SSS', 'SST'
            ]:

                qc_var = xco2qc.utilities.get_qc_mask_varname(nc, var)
                data = nc[qc_var][:]

                actual = np.bitwise_and(data, core.quality.OUT_OF_RANGE)
                np.testing.assert_allclose(actual[3:], expected)

        # Now manually fix the bad salinity value and run the QC again.  The
        # out of range flag should be cleared.
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            data = nc['SSS'][:]
            data[4] = 33
            nc['SSS'][:] = data

        with QCChecker(self.reduced_path) as o:
            o.check_valid_range()

        with netCDF4.Dataset(ncfile) as nc:

            expected = np.array([0, 0, 0])

            data = nc['SSS_qc'][:]

            actual = np.bitwise_and(data, core.quality.OUT_OF_RANGE)
            np.testing.assert_allclose(actual[3:], expected)

    def test__nh__licor(self):
        """
        SCENARIO:  QC an NH file.

        EXPECTED RESULT:  The reduced netCDF file has xCO2, temperature,
        pressure, raw1 and raw2 items.  Each variable has an associated qc
        variable.  Data is missing from the DEPL cycles, but otherwise quality
        is good.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(self.reduced_path) as o:
            o.check_valid_range()

        dst_nc_file = self.reduced_path / core.licor.APOFF_NCFILE

        with netCDF4.Dataset(dst_nc_file) as nc:

            qc_vars = [
                'xco2_wet_qc', 'xco2_dry_qc',
                'temperature_qc', 'pressure_qc',
                'raw_reference_qc', 'raw_sample_qc',
            ]
            expected = [
                core.quality.MISSING_DATA,
                core.quality.MISSING_DATA,
                0,
                0,
                0,
                0
            ]
            for qc_var in qc_vars:
                actual = nc[qc_var][:]
                actual = np.bitwise_and(actual, core.quality.MISSING_DATA)
                np.testing.assert_allclose(actual, expected, err_msg=qc_var)

    def test_spike_detection(self):
        """
        SCENARIO:  QC a WHOTS file.  The salinity has a spike.  There is a
        single instance of the span flag indicating a problem, but that does
        not signal a spike.

        EXPECTED RESULT:  The QC flag for spikes is set.
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        # Force the salinity spike at the 25th position.
        ncfile = self.reduced_path / core.MET_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:

            data = np.array([
                24.0033, 24.0015, 24.0004, 24.0012, 24.0075,
                24.0014, 24.0071, 24.0006, 24.0069, 24.0031,
                24.0034, 24.0098, 24.0010, 24.0010, 24.0041,
                24.0099, 24.0079, 24.0062, 24.0018, 24.0000,
                24.0087, 24.0054, 24.0064, 24.0043, 24.0022,
                24.0098, 24.0067, 24.0019, 24.0036, 24.0071,
                24.0011, 24.0004, 24.0053, 24.0071, 24.0017,
                24.0051, 24.0075, 24.0077, 24.0027, 24.0042,
                24.0029, 24.0096, 24.0054, 24.0038, 24.0003,
                24.0031, 24.0000, 24.0002, 24.0022, 24.0020
            ])
            data[25] = 35
            nc['SSS'][:] = data

        with QCChecker(self.reduced_path, spike_detection=True) as o:
            o.check_spike_detection()

        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['SSS_qc'][:]

        # We just want to look if the spike was detected.
        actual = np.bitwise_and(actual, core.quality.SPIKE_DETECTED)

        expected = np.full((50,), 0)
        expected[25] = core.quality.SPIKE_DETECTED

        err_msg = f"{data}"
        np.testing.assert_allclose(actual, expected, err_msg=err_msg)

    def test_spike_detection_turned_off(self):
        """
        SCENARIO:  QC a WHOTS file.  The salinity has a spike, but spike
        detection has been explicitly disabled.

        EXPECTED RESULT:  The QC flag for spikes is not set.
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        # Force the salinity spike at the 25th position.
        ncfile = self.reduced_path / core.MET_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            data = np.full((50,), 34.0)
            data[25] = 38
            nc['SSS'][:] = data

        with QCChecker(self.reduced_path, spike_detection=False) as o:
            o.check_spike_detection()

        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['SSS_qc'][:]

        # We just want to look if the spike was detected.  It should not.
        actual = np.bitwise_and(actual, core.quality.SPIKE_DETECTED)

        expected = np.full((50,), 0)

        np.testing.assert_allclose(actual, expected)

    @unittest.skipIf(sys.version_info.minor < 10, 'Uses >=v3.10 features')
    def test_spoff_relative_humidity_standard_deviation_ok(self):
        """
        SCENARIO:  QC an NH dataset.  The RH standard deviation in SPOFF is
        within bounds.

        EXPECTED RESULT:  The EXCESS_RH_STDDEV quality bit is not set.  No logs
        are emitted at the WARNING level.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        with QCChecker(self.reduced_path) as qc:
            with self.assertNoLogs(qc.logger, level=logging.WARNING):
                qc.check_rh_stddev()

        ncfile = self.reduced_path / core.licor.SPOFF_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['rh_qc'][:]
            expected = np.full(actual.shape, core.quality.GOOD)

            np.testing.assert_allclose(actual, expected)

    def test_apoff_relative_humidity_standard_deviation_exceeded(self):
        """
        SCENARIO:  QC an NH dataset.  The RH standard deviation in APOFF is
        outside of bounds.

        EXPECTED RESULT:  The EXCESS_RH_STDDEV quality bit is set.  Logs are
        emitted at the WARNING level.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(self.reduced_path, max_rh_std=0.001) as qc:
            with self.assertLogs(qc.logger, level=logging.WARNING):
                qc.check_rh_stddev()

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['rh_qc'][:]
            expected = np.full((4,), core.quality.EXCESS_RH_STDDEV)

            np.testing.assert_allclose(actual[2:], expected)

    def test_apoff_relative_humidity_stddev_exceeded__parameter(self):
        """
        SCENARIO:  QC an NH dataset.  The RH standard deviation in APOFF is
        outside of bounds as specified by a parameter.

        EXPECTED RESULT:  The EXCESS_RH_STDDEV quality bit is set.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(self.reduced_path, max_rh_std=0.001) as qc:
            qc.check_rh_stddev()

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['rh_qc'][:]
            expected = np.full((4,), core.quality.EXCESS_RH_STDDEV)

            np.testing.assert_allclose(actual[2:], expected)

    def test_apoff_rh_stddev_exceeded(self):
        """
        SCENARIO:  QC an NH dataset.  The RH standard deviation in APOFF is
        outside of bounds on the 3rd and 4th datums, ok for the 5th and 6th,
        and has missing data at 1st, and 2nd datums.

        EXPECTED RESULT:  The MISSING_DATA flag is set on 1st and 2nd datums.
        The OUT_OF_RANGE flag is set on the 3rd and 4th datums.  Quality is
        good elsewhere.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(self.reduced_path, max_rh_std=0.07) as qc:
            with self.assertLogs(qc.logger, level=logging.WARNING):
                qc.check_rh_stddev()

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            # check the MISSING_DATA flag
            actual = nc['rh_qc'][:]
            expected = np.array([
                core.quality.MISSING_DATA,
                core.quality.MISSING_DATA,
                0,
                0,
                0,
                0,
            ])
            np.testing.assert_allclose(
                np.bitwise_and(actual, core.quality.MISSING_DATA),
                expected
            )

            # check the STDDEV flag
            actual = nc['rh_qc'][:]
            expected = np.array([
                0,
                0,
                core.quality.EXCESS_RH_STDDEV,
                core.quality.EXCESS_RH_STDDEV,
                0,
                0,
            ])
            np.testing.assert_allclose(
                np.bitwise_and(actual, core.quality.EXCESS_RH_STDDEV),
                expected
            )

    def test_apoff_rh_temp_standard_deviation_ok(self):
        """
        SCENARIO:  QC an NH dataset.  The RH temp standard deviations in APOFF
        is within bounds.

        EXPECTED RESULT:  The EXCESS_RH_TEMP_STDDEV quality bit is not set.
        No warnings are emitted when running the RH temp stddev check.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(self.reduced_path) as qc:
            with self.assertRaises(AssertionError):
                with self.assertLogs(qc.logger, level=logging.WARNING):
                    qc.check_rh_temp_stddev()

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['rh_temp_qc'][:]

            # The first two cycles are all missing data
            expected = np.array([
                core.quality.MISSING_DATA,
                core.quality.MISSING_DATA,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
            ])

            np.testing.assert_allclose(actual, expected)

    def test_apoff_rh_temp_stddev_exceeded__via_parameter(self):
        """
        SCENARIO:  QC an NH dataset.  The RH temp standard deviations in APOFF
        are outside of bounds for all but the 2nd value.  The value is
        specified via a parameter.

        EXPECTED RESULT:  The EXCESS_RH_TEMP_STDDEV quality bit is set.
        """

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(self.reduced_path, max_rh_temp_std=0.015) as qc:
            qc.check_rh_temp_stddev()

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['rh_temp_qc'][:]
            expected = np.full((4,), core.quality.EXCESS_RH_TEMP_STDDEV)
            expected[1] = core.quality.GOOD

            np.testing.assert_allclose(actual[2:], expected)

    def test_apoff_rh_temp_standard_deviation_exceeded(self):
        """
        SCENARIO:  QC an NH dataset.  The RH temp standard deviations in APOFF
        are outside of bounds for all but the 2nd value.  The threshold is
        retrieved from the configuration file.

        EXPECTED RESULT:  The EXCESS_RH_TEMP_STDDEV quality bit is set.  Logs
        are emitted at the WARNING level.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with QCChecker(self.reduced_path, max_rh_temp_std=0.015) as qc:
            with self.assertLogs(qc.logger, level=logging.WARNING):
                qc.check_rh_temp_stddev()

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE

        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['rh_temp_qc'][:]
            expected = np.full((4,), core.quality.EXCESS_RH_TEMP_STDDEV)
            expected[1] = core.quality.GOOD

            np.testing.assert_allclose(actual[2:], expected)

    def test_no_post_xco2(self):
        """
        SCENARIO:  A decision was made not to calculate post xco2.

        EXPECTED RESULT:  The QC process runs without errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            calculate_post_xco2=False
        )

        with QCChecker(self.reduced_path, num_points_eachside=1) as p:
            p.run()

    def test_aanderaa_o2_with_missing_salinity(self):
        """
        SCENARIO:  Aanderaa o2 data, but one salinity point was missing.

        EXPECTED RESULT:  The BAD_SSTC flag is present.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        # insert the missing salinity flag
        ncfile = self.reduced_path / core.MET_NCFILE
        with netCDF4.Dataset(ncfile, 'r+') as nc:
            nc['SSS_qc'][:] = np.array([
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.MISSING_DATA,
                core.quality.GOOD,
            ])

        with QCChecker(self.reduced_path, num_points_eachside=1) as p:
            p.run()

        ncfile = self.reduced_path / core.SBE16_NCFILE
        with xr.open_dataset(ncfile) as ds:
            expected = np.array([
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.BAD_SSTC,
                core.quality.GOOD,
            ])
            actual = ds['o2_qc'].values
            np.testing.assert_allclose(actual, expected)

    def test_sbe16_mapping_but_no_aanderaa(self):
        """
        SCENARIO:  We have channel 0 and channel 1 data, but that's it.  This
        means no o2 data.

        EXPECTED RESULT:  No errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots.depl12',
            'mapco2_whots_0132_dp12_20180922__20191011.txt',
            sbe16_mapping=True
        )

        with QCChecker(self.reduced_path, num_points_eachside=1) as p:
            p.run()

        ncfile = self.reduced_path / core.SBE16_NCFILE
        with xr.open_dataset(ncfile) as ds:
            self.assertNotIn('o2', ds)
