"""
Test suite for QCing external SAMI data.
"""

# standard library imports
import importlib.resources as ir

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc.external_sami import ImportExternalSAMI
from xco2qc.data_reduction import XCO2Reduce
from xco2qc import core
from xco2qc.qc import QCChecker
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_outlier(self):
        """
        SCENARIO:  Read a QC'd sami netCDF file derived from external CSV
        data source.  The CSV flag indicates that the 2nd ph datum comes from
        data with at least one outlier.

        EXPECTED RESULTS:  The 2nd QC variable datum indicates an outlier.  The
        QC variable mask_values attribute contains the outlier definition.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.stratus'
            ).joinpath(
            'sami_stratus_P0042_dp11_20180410_20190410_out.txt'
        )) as inputfile:
            with ImportExternalSAMI(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.process_sami()

            with QCChecker(self.reduced_path, num_points_eachside=1) as p:
                p.check_external_sami()

            ncfile = self.reduced_path / core.EXTERNAL_SAMI_NCFILE
            with xr.open_dataset(ncfile, mask_and_scale=False) as ds:

                # verify the flag values
                actual = ds['ph_qc'].to_series()
                actual = np.bitwise_and(
                    actual, core.quality.EXTERNAL_SAMI_OUTLIER
                )

                index = pd.Series(
                    pd.to_datetime([
                        '2018-05-01T12:03:31',
                        '2018-05-01T15:03:31',
                        '2018-05-01T18:03:31',
                    ]),
                    name='time'
                )
                expected = pd.Series(
                    [0, core.quality.EXTERNAL_SAMI_OUTLIER, 0],
                    index=index, dtype=np.uint32, name='ph_qc'
                )
                pd.testing.assert_series_equal(actual, expected)

                # verify the attributes
                actual = ds['ph_qc'].flag_masks
                expected = [
                    core.quality.GOOD,
                    core.quality.MISSING_DATA,
                    core.quality.OUT_OF_RANGE,
                    core.quality.SPIKE_DETECTED,
                    core.quality.MANUALLY_FLAGGED,
                    core.quality.BAD_SSTC,
                    core.quality.EXTERNAL_SAMI_OUTLIER,
                    core.quality.EXTERNAL_SAMI_PUMP,
                    core.quality.EXTERNAL_SAMI_SATURATION,
                    core.quality.EXTERNAL_SAMI_BLANK,
                ]
                np.testing.assert_array_equal(actual, expected)

    def test_pump(self):
        """
        SCENARIO:  Read a QC'd sami netCDF file derived from external CSV
        data source.  The CSV flag indicates that the 2nd ph datum had a pump
        issue.

        EXPECTED RESULTS:  The 2nd QC variable datum indicates a pump issue.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.stratus'
            ).joinpath(
            'sami_stratus_P0042_dp11_20180410_20190410_out.txt'
        )) as inputfile:
            with ImportExternalSAMI(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.process_sami()

            # change the external flag data
            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                nc['external_flag'][:] = np.array([0, 100, 0])

            with QCChecker(self.reduced_path, num_points_eachside=1) as p:
                p.check_external_sami()

            ncfile = self.reduced_path / core.EXTERNAL_SAMI_NCFILE
            with xr.open_dataset(ncfile, mask_and_scale=False) as ds:

                # verify the flag values
                actual = ds['ph_qc'].to_series()
                actual = np.bitwise_and(
                    actual, core.quality.EXTERNAL_SAMI_PUMP
                )

                index = pd.Series(
                    pd.to_datetime([
                        '2018-05-01T12:03:31',
                        '2018-05-01T15:03:31',
                        '2018-05-01T18:03:31',
                    ]),
                    name='time'
                )
                expected = pd.Series(
                    [0, core.quality.EXTERNAL_SAMI_PUMP, 0],
                    index=index, dtype=np.uint32, name='ph_qc'
                )
                pd.testing.assert_series_equal(actual, expected)

    def test_saturation(self):
        """
        SCENARIO:  Read a QC'd sami netCDF file derived from external CSV
        data source.  The CSV flag indicates that the 2nd ph datum had a
        saturation issue.

        EXPECTED RESULTS:  The 2nd QC variable datum indicates a saturation
        issue.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.stratus'
            ).joinpath(
            'sami_stratus_P0042_dp11_20180410_20190410_out.txt'
        )) as inputfile:
            with ImportExternalSAMI(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.process_sami()

            # change the external flag data
            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                nc['external_flag'][:] = np.array([0, 10, 0])

            with QCChecker(self.reduced_path, num_points_eachside=1) as p:
                p.check_external_sami()

            ncfile = self.reduced_path / core.EXTERNAL_SAMI_NCFILE
            with xr.open_dataset(ncfile, mask_and_scale=False) as ds:

                # verify the flag values
                actual = ds['ph_qc'].to_series()
                actual = np.bitwise_and(
                    actual, core.quality.EXTERNAL_SAMI_SATURATION
                )

                index = pd.Series(
                    pd.to_datetime([
                        '2018-05-01T12:03:31',
                        '2018-05-01T15:03:31',
                        '2018-05-01T18:03:31',
                    ]),
                    name='time'
                )
                expected = pd.Series(
                    [0, core.quality.EXTERNAL_SAMI_SATURATION, 0],
                    index=index, dtype=np.uint32, name='ph_qc'
                )
                pd.testing.assert_series_equal(actual, expected)

    def test_blank(self):
        """
        SCENARIO:  Read a QC'd sami netCDF file derived from external CSV
        data source.  The CSV flag indicates that the 2nd ph datum had a blank
        issue.

        EXPECTED RESULTS:  The 2nd QC variable datum indicates a blank issue.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.stratus'
            ).joinpath(
            'sami_stratus_P0042_dp11_20180410_20190410_out.txt'
        )) as inputfile:
            with ImportExternalSAMI(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.process_sami()

            # change the external flag data
            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                nc['external_flag'][:] = np.array([0, 1, 0])

            with QCChecker(self.reduced_path, num_points_eachside=1) as p:
                p.check_external_sami()

            ncfile = self.reduced_path / core.EXTERNAL_SAMI_NCFILE
            with xr.open_dataset(ncfile, mask_and_scale=False) as ds:

                # verify the flag values
                actual = ds['ph_qc'].to_series()
                actual = np.bitwise_and(
                    actual, core.quality.EXTERNAL_SAMI_BLANK
                )

                index = pd.Series(
                    pd.to_datetime([
                        '2018-05-01T12:03:31',
                        '2018-05-01T15:03:31',
                        '2018-05-01T18:03:31',
                    ]),
                    name='time'
                )
                expected = pd.Series(
                    [
                        0,
                        core.quality.EXTERNAL_SAMI_BLANK,
                        0
                    ],
                    index=index, dtype=np.uint32, name='ph_qc'
                )
                pd.testing.assert_series_equal(actual, expected)

    def test_multiple_conditions(self):
        """
        SCENARIO:  Read a QC'd sami netCDF file derived from external CSV
        data source.  The CSV flag indicates that the 2nd ph datum had a pump
        issue and an outlier issue.

        EXPECTED RESULTS:  The 2nd QC variable datum indicates a pump issue
        and an outlier issue.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.stratus'
            ).joinpath(
            'sami_stratus_P0042_dp11_20180410_20190410_out.txt'
        )) as inputfile:
            with ImportExternalSAMI(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.process_sami()

            # change the external flag data
            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                nc['external_flag'][:] = np.array([0, 1100, 0])

            with QCChecker(self.reduced_path, num_points_eachside=1) as p:
                p.check_external_sami()

            ncfile = self.reduced_path / core.EXTERNAL_SAMI_NCFILE
            with xr.open_dataset(ncfile, mask_and_scale=False) as ds:

                # verify the outlier flag value
                actual = ds['ph_qc'].to_series()
                actual = np.bitwise_and(
                    actual, core.quality.EXTERNAL_SAMI_OUTLIER
                )

                index = pd.Series(
                    pd.to_datetime([
                        '2018-05-01T12:03:31',
                        '2018-05-01T15:03:31',
                        '2018-05-01T18:03:31',
                    ]),
                    name='time'
                )
                expected = pd.Series(
                    [0, core.quality.EXTERNAL_SAMI_OUTLIER, 0],
                    index=index, dtype=np.uint32, name='ph_qc'
                )
                pd.testing.assert_series_equal(actual, expected)

                # verify the outlier pump value
                actual = ds['ph_qc'].to_series()
                actual = np.bitwise_and(
                    actual, core.quality.EXTERNAL_SAMI_PUMP
                )

                expected = pd.Series(
                    [
                        0,
                        core.quality.EXTERNAL_SAMI_PUMP,
                        0,
                    ],
                    index=index, dtype=np.uint32, name='ph_qc'
                )
                pd.testing.assert_series_equal(actual, expected)
