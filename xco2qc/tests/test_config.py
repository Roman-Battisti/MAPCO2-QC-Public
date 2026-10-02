# standard library tests
import datetime as dt
import importlib.resources as ir
import pathlib
import shutil
import tempfile

# 3rd party library imports
import numpy as np
import xarray as xr
import yaml

# local imports
import xco2qc.aux_sensor_gui
import xco2qc.core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from . import test_core


class TestSuiteExpectingException(test_core.TestSuite):
    """
    Tests for loading the YAML configuration file when an error is expected.
    """

    def _run_configuration_expecting_failure(
        self, expected_exception=xco2qc.core.InvalidMapCO2ConfigFile
    ):

        with self.config_file.open('wt') as f:
            yaml.dump(self.config, f)

        with ir.as_file(ir.files(
            'tests.data.mapco2.ndbcwa'
            ).joinpath(
            'dp01_0003_20060621_20070518.all_good.txt'
        )) as inputfile:
            with test_core.chdir(self.root):
                with self.assertRaises(expected_exception):
                    obj = RawTextToRawNC(inputfile,
                                         dst_dir=self.raw_path)
                    obj.run()

    def test__invalid_config_file__no_start_date(self):
        """
        SCENARIO:  The configuration file is missing a start date.

        EXPECTED RESULTS:  An exception is raised.
        """
        del self.config['QC']['start']

        self._run_configuration_expecting_failure()

    def test__invalid_config_file__no_end_date(self):
        """
        SCENARIO:  The configuration file is missing an end date.

        EXPECTED RESULTS:  An exception is raised.
        """
        del self.config['QC']['stop']

        self._run_configuration_expecting_failure()

    def test__invalid_config_file__initial_span_cal(self):
        """
        SCENARIO:  The configuration file is missing an initial_span_cal key.

        EXPECTED RESULTS:  An exception is raised.
        """
        del self.config['QC']['initial_span_cal']

        self._run_configuration_expecting_failure()


class TestSuiteCopyConfig(test_core.TestSuite):

    def test_smoke(self):
        """
        Scenario:  the config file is found in the directory for the source
        mapco2 file.

        Expected result:  the config file is copied to the root of the output
        directory tree.  The new chl_scale_factor should persist.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.ndbcwa'
            ).joinpath(
            'dp01_0003_20060621_20070518.all_good.txt'
        )) as inputfile:

            new_src_dir = tempfile.TemporaryDirectory()
            new_src_path = pathlib.Path(new_src_dir.name)
            new_inputfile_path = new_src_path / inputfile.name

            shutil.copyfile(inputfile, new_inputfile_path)

        # change a config file setting from the default value so that we can
        # verify it, then write it into the source directory
        self.config['QC']['chl_scale_factor'] = 20

        new_config_file = new_src_path / 'config.yml'
        with new_config_file.open('wt') as f:
            yaml.dump(self.config, f)

        # now run the conversion, the config file should be copied
        with RawTextToRawNC(
            new_inputfile_path, dst_dir=self.raw_path
        ) as o:
            o.run()

            self.assertEqual(o.config['QC']['chl_scale_factor'], 20)

        with xco2qc.aux_sensor_gui.AuxSensorGui(
            src_dir=self.raw_path, dst_dir=self.reduced_path
        ) as gui:
            gui.run()

            kwargs = gui.gather_kwargs()

            self.assertEqual(kwargs['chl_scale_factor'], [20])

        with XCO2Reduce(
            self.raw_path, self.reduced_path,
            chl_scale_factor=kwargs['chl_scale_factor'],
            sbe16_mapping=True
        ) as p1:
            p1.run()

            self.assertEqual(p1.config['QC']['chl_scale_factor'], 20)

        root = self.raw_path.parents[0]
        new_config_file = root / 'config.yml'
        with new_config_file.open() as f:
            d = yaml.safe_load(f)
            self.assertEqual(d['QC']['chl_scale_factor'], 20)

    def test_bad_split_time(self):
        """
        Scenario:  the config file is found in the directory for the source
        mapco2 file.  the split time is invalid

        Expected result:  RuntimeError
        """

        self.config['QC']['instrument_time_split'] = 'bad time'

        root = self.raw_path.parents[0]
        new_config_file = root / 'config.yml'
        with new_config_file.open('wt') as f:
            yaml.dump(self.config, f)

        with self.assertRaises(RuntimeError):
            xco2qc.core.MapCO2core(dst_dir=self.raw_path)

    def test_good_split_time(self):
        """
        Scenario:  the config file is found in the directory for the source
        mapco2 file.  the split time is valid

        Expected result:  the split time is verified
        """
        expected = dt.datetime(2007, 1, 1)
        self.config['QC']['instrument_time_split'] = expected

        root = self.raw_path.parents[0]
        new_config_file = root / 'config.yml'
        with new_config_file.open('wt') as f:
            yaml.dump(self.config, f)

        o = xco2qc.core.MapCO2core(dst_dir=self.raw_path)
        actual = o.config['QC']['instrument_time_split']
        self.assertEqual(actual, expected)

    def test_current_directory(self):
        """
        Scenario:  the config file is found in the current directory

        Expected result:  no errors
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.ndbcwa'
            ).joinpath(
            'dp01_0003_20060621_20070518.all_good.txt'
        )) as inputfile:

            new_src_dir = tempfile.TemporaryDirectory()
            new_src_path = pathlib.Path(new_src_dir.name)

            # change a config file setting from the default value so that we
            # can verify it, then write it into the source directory
            self.config['QC']['chl_scale_factor'] = 20

            new_config_file = new_src_path / 'mapco2.yml'
            with new_config_file.open('wt') as f:
                yaml.dump(self.config, f)

            with test_core.chdir(new_src_path):

                # now run the conversion, the new config file should be read
                with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as o:
                    o.run()

                    self.assertEqual(o.config['QC']['chl_scale_factor'], 20)


class TestSuite(test_core.TestSuite):

    def test_chl_ntu_oxygen_settings(self):
        """
        Scenario:  read the default configuration file

        Expected results:  chl, ntu, and oxygen settings are verified
        """
        self.assertEqual(self.config['QC']['chl_scale_factor'], 10)
        self.assertEqual(self.config['QC']['chl_dark_count'], 0.06)
        self.assertEqual(self.config['QC']['ntu_scale_factor'], 5)
        self.assertEqual(self.config['QC']['ntu_dark_count'], 0.06)
        self.assertEqual(self.config['QC']['chl_global_conversion'], 1)
        self.assertEqual(self.config['QC']['o2_salinity_setting'], 0)

    def test_no_config_file_exists(self):
        """
        SCENARIO:  No configuration file exists.

        EXPECTED RESULTS:  As no start and end times for the deployment are
        available, no cycles (except DEPL) are trimmed off of the raw netcdf
        files.  Manually scanning the raw text file shows that the cycle times
        range from 2006/6/19 23:05:30 to 2006/06/20 21:00:00.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.ndbcwa',
            ).joinpath(
            'dp01_0003_20060621_20070518.all_good.txt'
        )) as inputfile:
            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as o:
                o.run()

        ncfile = self.raw_path / xco2qc.core.MET_NCFILE
        ds = xr.open_dataset(ncfile)
        actual = ds[xco2qc.core.TIME].values

        expected = np.array([
            '2006-06-19T23:05:30',
            '2006-06-19T23:35:30',
            '2006-06-20T00:05:30',
            '2006-06-20T00:35:30',
            '2006-06-20T03:00:00',
            '2006-06-20T06:00:00',
            '2006-06-20T09:00:00',
            '2006-06-20T12:00:00',
            '2006-06-20T15:00:00',
            '2006-06-20T18:00:00',
            '2006-06-20T21:00:00',
        ], dtype='datetime64[ns]')

        np.testing.assert_array_equal(actual, expected)

    def test_config_file__1st_last_cycle_outside_config_file_bounds(self):
        """
        SCENARIO:  The configuration file specifies a time frame that excludes
        the first and last cycle.

        See TestSuite.test_no_config_file_exists for details on a test run
        under the same conditions except for the time frame condition.

        EXPECTED RESULTS:  The time variable does not show those 1st and last
        cycles.
        """
        self.config['QC']['start'] = dt.datetime(2006, 6, 19, 23, 10, 0)
        self.config['QC']['stop'] = dt.datetime(2006, 6, 20, 20, 0, 0)

        self._write_config_file()

        with ir.as_file(ir.files(
            'tests.data.mapco2.ndbcwa'
            ).joinpath(
            'dp01_0003_20060621_20070518.all_good.txt'
        )) as inputfile:
            with test_core.chdir(self.root):
                with RawTextToRawNC(
                    inputfile, dst_dir=self.raw_path
                ) as obj:
                    obj.run()

        ncfile = self.raw_path / xco2qc.core.MET_NCFILE
        ds = xr.open_dataset(ncfile)
        actual = ds[xco2qc.core.TIME].values

        expected = np.array([
            '2006-06-19T23:35:30',
            '2006-06-20T00:05:30',
            '2006-06-20T00:35:30',
            '2006-06-20T03:00:00',
            '2006-06-20T06:00:00',
            '2006-06-20T09:00:00',
            '2006-06-20T12:00:00',
            '2006-06-20T15:00:00',
            '2006-06-20T18:00:00',
        ], dtype='datetime64[ns]')

        np.testing.assert_array_equal(actual, expected)

    def test_config_file__channel_mapping(self):
        """
        SCENARIO:  The configuration file specifies an alternative channel
        mapping.

        EXPECTED RESULTS:  The mappings are verified from the mapping gui.
        """
        self.config['QC']['chl_channel'] = 1
        self.config['QC']['ntu_channel'] = 2
        self.config['QC']['o2_channel'] = 3
        self.config['QC']['o2_temp_channel'] = 4

        self._write_config_file()

        with ir.as_file(ir.files(
            'tests.data.mapco2.ndbcwa'
            ).joinpath(
            'dp01_0003_20060621_20070518.all_good.txt'
        )) as inputfile:
            with test_core.chdir(self.root):
                with RawTextToRawNC(
                    inputfile, dst_dir=self.raw_path
                ) as obj:
                    obj.run()

                with xco2qc.aux_sensor_gui.AuxSensorGui(
                    src_dir=self.raw_path, dst_dir=self.reduced_path
                ) as gui:
                    gui.run()

                    kwargs = gui.gather_kwargs()

        self.assertEqual(kwargs['chl_channel'], 1)
        self.assertEqual(kwargs['ntu_channel'], 2)
        self.assertEqual(kwargs['o2_channel'], 3)
        self.assertEqual(kwargs['o2_temp_channel'], 4)
