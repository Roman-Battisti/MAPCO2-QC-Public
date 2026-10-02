# standard library imports
import importlib.resources as ir
import io
import pathlib

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd
import tempfile
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.external_historical import ImportHistorical
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import LicorProcessor, XCO2Reduce
from xco2qc.validation_data import ValidationData
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, deployment_number=None, verbosity='critical',
        historical_file=None
    ):
        """
        Shortcut for running just raw processing.
        """

        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity=verbosity,
                deployment_number=deployment_number
            ) as p0:
                p0.run()

        if historical_file is not None:
            with ImportHistorical(historical_file, self.raw_path) as p:
                p.run()

    def test_prawler_smoke(self):
        """
        SCENARIO:  We have prawler CTD data

        EXPECTED RESULT:  salinity is computed
        """
        self._processing_pipeline(
            'tests.data.mapco2.asv', 'pco2asv_sd1006.3.full.txt'
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        ncfile = self.reduced_path / core.PRAWLER_CTD_NCFILE
        with xr.open_dataset(ncfile) as ds:
            df = ds.to_dataframe()
            df['salinity']

    def test_seafet_smoke(self):
        """
        SCENARIO:  A raw file has seafet data with 3 cycles.  Each cycle has 6
        measurements.

        EXPECTED RESULT:  The reduced file has 3 averaged measurements, one for
        each cycle.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1',
            '0108_dp11_20181113_20190509.txt'
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        ncfile = self.reduced_path / core.SEAFET_NCFILE
        with xr.open_dataset(ncfile) as ds:
            df = ds.to_dataframe()

            self.assertEqual(len(df), 3)

    def test_bad_output_directory(self):
        """
        SCENARIO:  Attempt to write to a directory where a config file is not
        found in the parent directory.

        EXPECTED RESULT:  RuntimeError
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )
        with tempfile.TemporaryDirectory() as outputdir:
            with self.assertRaises(RuntimeError):
                with XCO2Reduce(self.raw_path, outputdir) as p:
                    p.run()

    def test__nh__licor__median(self):
        """
        SCENARIO:  Process an NH file to reduced status, use median processing.

        EXPECTED RESULT:  The reduced netCDF file has xCO2, temperature,
        pressure, raw1 and raw2 items.  Each variable has an associated qc
        variable.  The quality is all good.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        src_nc_file = self.raw_path / core.licor.APOFF_NCFILE
        dst_nc_file = self.reduced_path / core.licor.APOFF_NCFILE

        with LicorProcessor(
            src_nc_file, dst_nc_file,
            reduce=core.REDUCE_MEDIAN
        ) as p:
            p.run()

        with netCDF4.Dataset(dst_nc_file) as nc:

            # compare the temperature
            # the first two points are masked
            actual = nc['temperature'][:]
            expected = np.array([np.nan, np.nan, 13.85, 14.34, 14.52, 14.55])
            np.testing.assert_allclose(actual, expected)

            # compare the xCO2
            actual = nc['xco2_wet'][:]
            expected = np.array([
                np.nan, np.nan, 402.1, 401.27, 400.42, 400.21
            ])
            np.testing.assert_allclose(actual, expected)

            # compare the pressure
            actual = nc['pressure'][:]
            expected = np.array([
                np.nan, np.nan, 102.86, 102.85, 102.81, 102.78
            ])
            np.testing.assert_allclose(actual, expected)

            # compare the raw1 counts
            actual = nc['raw_reference'][:]
            expected = np.array([
                np.nan, np.nan, 2634566, 2634088, 2633955, 2634003
            ])
            np.testing.assert_allclose(actual, expected)

            # compare the raw2 counts
            actual = nc['raw_sample'][:]
            expected = np.array([
                np.nan, np.nan, 2040253, 2039740, 2039428, 2039399
            ])
            np.testing.assert_allclose(actual, expected)

            qc_vars = [
                'xco2_wet_qc', 'temperature_qc', 'pressure_qc',
                'raw_reference_qc', 'raw_sample_qc'
            ]
            expected = [
                core.quality.MISSING_DATA,
                core.quality.MISSING_DATA,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
            ]
            for qc_var in qc_vars:
                actual = nc[qc_var][:]
                np.testing.assert_allclose(actual, expected)

    def test__nh__licor__mean(self):
        """
        SCENARIO:  Process an NH file to reduced status.

        EXPECTED RESULT:  The reduced netCDF file has xCO2, temperature,
        pressure, raw1 and raw2 items.  Each variable has an associated qc
        variable.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        expected_qc = np.array([
            core.quality.MISSING_DATA,
            core.quality.MISSING_DATA,
            core.quality.GOOD,
            core.quality.GOOD,
            core.quality.GOOD,
            core.quality.GOOD,
        ])

        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # The first two cycles are DEPL and have no data, so ignore them.
            # Make sure we pick up on that in the QC though.

            # compare the temperature
            actual = nc['temperature'][2:]
            expected = np.array([13.851403, 14.336667, 14.519299, 14.548596])
            np.testing.assert_allclose(actual, expected)

            actual = nc['temperature_qc'][:]
            np.testing.assert_allclose(actual, expected_qc)

            # compare the xCO2
            actual = nc['xco2_wet'][2:]
            expected = np.array([402.2116, 401.1142, 400.4746, 400.1147])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = nc['xco2_wet_qc'][:]
            np.testing.assert_allclose(actual, expected_qc)

            # compare the pressure
            actual = nc['pressure'][2:]
            expected = np.array([102.861755, 102.841576, 102.80193, 102.7807])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = nc['pressure_qc'][:]
            np.testing.assert_allclose(actual, expected_qc)

            # compare the raw1 counts
            actual = nc['raw_reference'][2:]
            expected = np.array([2634567.2, 2634067.8, 2633956, 2634016.2])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = nc['raw_reference_qc'][:]
            np.testing.assert_allclose(actual, expected_qc)

            # compare the raw2 counts
            actual = nc['raw_sample'][2:]
            expected = np.array([2040265, 2039698.4, 2039480.4, 2039411.4])
            np.testing.assert_allclose(actual, expected)

            actual = nc['raw_sample_qc'][:]
            np.testing.assert_allclose(actual, expected_qc)

        ncfile = self.reduced_path / core.licor.ZPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # the xCO2 is out of range with non-zero mode xco2 values, but
            # we allow for that.  No NaNs, though.
            actual = nc['xco2_wet'][2:]
            self.assertEqual(actual.mask.sum(), 0)

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # compare the battery trans
            actual = nc['battery_logic'][:]
            expected = np.array([14.1, 14.2, 14.1, 14.1, 14.1, 14.2])
            np.testing.assert_allclose(actual, expected)

            # compare the battery logic
            actual = nc['battery_trans'][:]
            expected = np.array([[13.2, 13.2, 14.1, 14.1, 14.1, 14.1]])
            np.testing.assert_allclose(actual[~actual.mask], expected)

    def test__nh__header_diagnostic_variables_carried_over(self):
        """
        SCENARIO:  Process an NH file to reduced status.

        EXPECTED RESULT:  The header diagnostic variables are carried
        over to reduced status.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            for varname in [
                'zero_coefficient',
                'span_coefficient',
                'latitude', 'longitude'
            ]:
                self.assertIn(varname, nc.variables.keys())

    def test_nh_met_smoke(self):
        """
        SCENARIO:  Process an NH file to reduced status.

        EXPECTED RESULT:  After the met processing is finished, there
        will be additional variables sst, conductivity, and salinity.
        Since this has both met and sami data, a MET CSV file is produced.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            deployment_number=9
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        dst_nc_file = self.reduced_path / core.MET_NCFILE
        with netCDF4.Dataset(dst_nc_file) as nc:

            # verify the met temperature variable
            # expected median = np.array([11.461 , 11.3879, 11.3506])
            expected = np.array([11.45957, 11.38863, 11.35007])
            actual = nc['SST'][:]
            actual = actual[~actual.mask]
            np.testing.assert_allclose(actual, expected, rtol=1e-6)

            # verify the met conductivity variable
            # expected median = np.array([3.66089, 3.65498, 3.65243])
            expected = np.array([3.66045, 3.65499, 3.65233])
            actual = nc['conductivity'][:]
            actual = actual[~actual.mask]
            np.testing.assert_allclose(actual, expected, rtol=1e-6)

            # verify the met salinity variable
            # expected median = np.array([32.175 , 32.1805, 32.1885])
            expected = np.array([32.172268, 32.180565, 32.188133])
            actual = nc['SSS'][:]
            actual = actual[~actual.mask]
            np.testing.assert_allclose(actual, expected)

        csvfile = pathlib.Path(self.reduced_path, 'met.csv')
        df = pd.read_csv(csvfile)
        self.assertIn('SSS', df.columns)

    def test_smoke(self):
        """
        SCENARIO:  Process all raw netCDF to reduced status for the NH site.
        Add historical data.

        EXPECTED RESULT:  Results verified against VBA results for APOFF and
        SBE16.  Verify that the historical data exists in the data reduction
        phase.
        """
        with ir.as_file(ir.files(
            'tests.data.external.nh'
            ).joinpath(
            'historical.4.txt'
        )) as ifile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.txt',
                deployment_number=9,
                historical_file=ifile
            )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        # verify the licor variables
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            for variable in [
                'xco2_wet', 'temperature',
                'pressure',
                'raw_reference', 'raw_sample'
            ]:
                self.assertIn(variable, nc.variables.keys())

        ncfile = self.reduced_path / core.MET_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            for variable in [
                'SST', 'conductivity', 'SSS'
            ]:
                self.assertIn(variable, nc.variables.keys())

        ncfile = self.reduced_path / core.SAMI_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            for variable in [
                'ph', 'temperature',
                'slope', 'r2'
            ]:
                self.assertIn(variable, nc.variables.keys())

        ncfile = self.reduced_path / core.HISTORICAL_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            for variable in ['SST', 'SSS', 'pH_sw']:
                self.assertIn(variable, nc.variables)

    def test_validation_data(self):
        """
        SCENARIO:  Validation data is imported and then data reduction is
        done.

        EXPECTED RESULT:  Validation data is verified in the data reduction
        area.
        """
        with ir.as_file(ir.files(
            'tests.data.external.nh'
            ).joinpath(
            'historical.4.txt'
        )) as ifile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.txt',
                deployment_number=9,
                historical_file=ifile
            )

        text = (
                "time,dissolved_oxygen\n"
                "1950-02-10 09:18:00,100\n"
                "1950-02-10 12:30:00,200\n"
        )
        inputfile = io.StringIO(text)

        with ValidationData(inputfile, self.raw_path) as p:
            p.run()

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        ncfile = self.reduced_path / 'validation.nc'
        self.assertTrue(ncfile.exists())

    def test_corrupt_sami_record(self):
        """
        SCENARIO:  Process a laparguera  file that has a corrupt sami record.
        The first record is uninitialized, the 2nd is corrupt, the 3rd is fine.
        However, the salinity is bad everywhere.

        EXPECTED RESULT:  All three values are nan.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            '0143_dp12_20180609_20190906.corrupt_sami_record.txt'
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        ncfile = self.reduced_path / core.SAMI_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['ph'].values
            expected = np.array([np.nan, np.nan, np.nan])
            np.testing.assert_allclose(actual, expected)

            actual = ds['ph_qc'].values
            expected = np.array([
                core.quality.MISSING_DATA,
                core.quality.BAD_SSTC,
                core.quality.BAD_SSTC
            ])
            np.testing.assert_allclose(actual, expected)

    def test_vba_sami(self):
        """
        SCENARIO:  Process an NH file that has the VBA test sami data.

        EXPECTED RESULT:  Results verified against VBA results.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.new_sami.txt'
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        ncfile = self.reduced_path / core.SAMI_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['ph'].values
            expected = np.array([np.nan, 8.0201, 8.0201, 8.0201])
            np.testing.assert_allclose(actual, expected, 1e-4)

            # first salinity value is NaN
            actual = ds['ph_qc'].values
            expected = np.full((4,), core.quality.GOOD)
            expected[0] = core.quality.BAD_SSTC
            np.testing.assert_array_equal(actual, expected)

            actual = ds['temperature'].values
            expected = np.array([8.8229, 8.8229, 8.8229, 8.8229])
            np.testing.assert_allclose(actual, expected, 1e-4)

            actual = ds['slope'].values
            expected = np.array([np.nan, -763.34, -763.34, -763.34])
            np.testing.assert_allclose(actual, expected, 1e-4)

            actual = ds['r2'].values
            expected = np.array([np.nan, 0.9879, 0.9879, 0.9879])
            np.testing.assert_allclose(actual, expected, 1e-4)

            actual = ds['battery'].values
            expected = np.full((4,), 10.2114)
            np.testing.assert_allclose(actual, expected, 1e-4)

            actual = ds['sami_time'].to_series().values
            expected = np.full((4,), np.datetime64('2012-06-28T06:04:59'))
            np.testing.assert_array_equal(actual, expected)

    def test__path_output_directory_does_not_exist(self):
        """
        SCENARIO:  Process all raw netCDF to reduced, but supply a
        destination directory that is not at the same directory level as the
        raw directory.

        EXPECTED RESULT:  RuntimeError
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # The root directory exists, but the 'level1' subdirectory does not,
        # and neither does 'level1/sub'
        dest_path = self.raw_path / 'level1/sub'

        with self.assertRaises(RuntimeError):
            with XCO2Reduce(self.raw_path, dest_path) as p:
                p.run()

    def test_alawai__no_met_no_sbe(self):
        """
        SCENARIO:  Process all raw netCDF to reduced status.  This example has
        no met buffer.  The SBE16 buffer is present in the raw text file, but
        has no samples.

        EXPECTED RESULT:  Only reduced LICOR files and the cycle headers file
        should be produced.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'dp3_0027_20101207_20120206.txt',
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        for ncfile in self.reduced_path.glob('*.nc'):
            with netCDF4.Dataset(ncfile) as nc:
                self.assertNotEqual(nc.data_source, 'SBE16', ncfile)
                self.assertNotEqual(nc.data_source, 'MET', ncfile)

    def test_string_output_directory_does_not_exist(self):
        """
        SCENARIO:  Process all raw netCDF to reduced status, but supply a
        destination directory as a string that does not exist at the same
        directory level.

        EXPECTED RESULT:  RuntimeError
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # The root directory exists, but the 'level1' subdirectory does not,
        # and neither does 'level1/sub'
        dest_path = self.raw_path / 'level1/sub'
        dest_path_str = str(dest_path)

        with self.assertRaises(RuntimeError):
            with XCO2Reduce(self.raw_path, dest_path_str) as p:
                p.run()

    def test__ndbcwa__no_sbe16(self):
        """
        SCENARIO:  Process reduced netCDF when we have no SBE16 data at all.
        There is, however, met data.
        file.

        EXPECTED RESULT:  There will be a met reduced file.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.ndbcwa'
            ).joinpath(
            'dp11_0005_20150610_20160619.txt'
        )) as inputfile:
            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:
                p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p:
                p.run()

        ncfile = self.reduced_path / core.MET_NCFILE
        self.assertTrue(ncfile.exists())

    def test_oxygen(self):
        """
        SCENARIO:  The reduced data should include oxygen.

        EXPECTED RESULT:  The presence of O2, RH, and Rh_temp is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.o2-zpon-samples.txt'
        )

        src_nc_file = self.raw_path / core.licor.ZPON_NCFILE
        dst_nc_file = self.reduced_path / core.licor.ZPON_NCFILE

        with LicorProcessor(src_nc_file, dst_nc_file) as o:
            o.run()

        with netCDF4.Dataset(dst_nc_file) as nc:

            self.assertIn('o2', nc.variables.keys())
            self.assertIn('rh', nc.variables.keys())
            self.assertIn('rh_temp', nc.variables.keys())

    def test__licor_coordinate_variables(self):
        """
        SCENARIO:  Process an NH file to reduced status.  The coordinate
        variables were not being written.

        EXPECTED RESULT:  The coordinate variables are verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.missing_one_met_cycle.txt',
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        dst_ncfile = self.reduced_path / core.licor.SPOSTCAL_NCFILE

        ds = xr.open_dataset(dst_ncfile)

        expected = np.array([
            '2013-11-05T19:05:00',
            '2013-11-05T19:35:00',
            '2013-11-05T20:05:00'], dtype='datetime64[ns]')
        np.testing.assert_array_equal(ds[core.TIME].values, expected)

    def test_unrecognized_reduction_method(self):
        """
        SCENARIO:  An unrecognized reduction method identifier is given.  It
        should normally indicate either median or mean.

        EXPECTED RESULT:  An exception is issued.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.nh'
            ).joinpath(
            'dp09_0014_20131105_20140802.missing_one_met_cycle.txt'
        )) as inputfile:
            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:
                p.run()

            with self.assertRaises(RuntimeError):
                with XCO2Reduce(
                    self.raw_path,
                    self.reduced_path,
                    mapco2_licor_reduce=2
                ) as p:
                    p.run()
