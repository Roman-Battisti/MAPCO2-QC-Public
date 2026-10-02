# standard library imports
import datetime as dt
import importlib.resources as ir

# 3rd party library imports
import numpy as np
import xarray as xr
import yaml

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, deployment_number=None, verbosity='critical'
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

    def test_sbe16_with_no_deployment_number(self):
        """
        SCENARIO:  Process an NH file to reduced status.  The deployment number
        is embedded in the full filename, but we don't want to rely upon that.
        We pretend we do not know the deployment number.

        EXPECTED RESULT:  The reduced SBE16 file is not created.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

        ncfile = self.reduced_path / core.SBE16_NCFILE
        self.assertFalse(ncfile.exists())

    def test__nh__no_sbe16_channel_mapping(self):
        """
        SCENARIO:  Process an NH file to reduced status.  We have the
        deployment number, but there is still no channel mapping.

        EXPECTED RESULT:  No reduced sbe16 netCDF file is produced.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            deployment_number=14
        )

        with XCO2Reduce(
            self.raw_path, self.reduced_path, sbe16_mapping=False
        ) as p1:
            p1.run()

        ncfile = self.reduced_path / core.SBE16_NCFILE
        self.assertFalse(ncfile.exists())

    def test_sbe16_with_non_integer_deployment(self):
        """
        SCENARIO:  Process a laparguera  file.  The deployment
        for this site is not an integer.

        EXPECTED RESULT:  Does not error out.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            deployment_number='12a'
        )

        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()

    def test_smoke(self):
        """
        SCENARIO:  Process a laparguera  file.  We have the channel mapping
        for this site.

        EXPECTED RESULT:  The chl, ntu, o2, and o2 temp are verified.  Verify
        that the save config.yml file matches the chl params.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            deployment_number=12
        )

        with XCO2Reduce(
            self.raw_path, self.reduced_path,
            chl_scale_factor=[9],
            chl_dark_count=[0.065],
            ntu_scale_factor=[5],
            ntu_dark_count=[0.076],
            chl_global_conversion=1,
            o2_salinity_setting=[0],
            sbe16_mapping=True
        ) as p1:
            p1.run()

        ncfile = self.reduced_path / core.SBE16_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['chl'].values
            expected = np.array([0.3591, 0.35055, 0.3285, 0.30555])
            np.testing.assert_allclose(actual, expected)

            # 1st and 4th values are nighttime.
            actual = ds['chl_nighttime'].values
            expected = np.array([np.nan, 0.35055, 0.3285, np.nan])
            np.testing.assert_allclose(actual, expected)

            actual = ds['chl_nighttime_qc'].values
            expected = np.array([
                core.quality.DAYTIME, core.quality.GOOD,
                core.quality.GOOD, core.quality.DAYTIME,
            ])
            np.testing.assert_allclose(actual, expected)

            # make sure it has the daytime flag attribute
            self.assertIn(
                core.quality.DAYTIME,
                ds['chl_nighttime_qc'].flag_masks
            )
            self.assertIn(
                "daytime",
                ds['chl_nighttime_qc'].flag_meanings
            )

            actual = ds['ntu'].values
            expected = np.array([3.1625, 3.2925, 3.269, 3.351])
            np.testing.assert_allclose(actual, expected)

            actual = ds['o2'].values
            expected = np.array([188.1965, 186.4967, 185.3627, 184.0634])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['o2_temp'].values
            expected = np.array([29.5105, 29.4835, 29.4268, 29.4034])
            np.testing.assert_allclose(actual, expected)

            # There's only one observation for the variables here, so the
            # stddevs is all zero.
            for variable in [
                'chl_stddev', 'ntu_stddev', 'o2_temp_stddev', 'o2_stddev'
            ]:
                actual = ds[variable].values
                expected = np.zeros((len(actual),))
                np.testing.assert_equal(actual, expected)

            # and the regular variables...
            actual = ds['current'].values
            expected = np.array([206.6, 198.4, 196.1, 189.7])
            np.testing.assert_allclose(actual, expected)

            actual = ds['density'].values
            expected = np.array([22.9135, 22.9251, 22.9481, 22.9459])
            np.testing.assert_allclose(actual, expected)

            with open(self.config_file) as f:
                d = yaml.safe_load(f)
                self.assertEqual(d['QC']['chl_dark_count'], [0.065])

    def test_time_split(self):
        """
        SCENARIO:  Process a laparguera  file.  We have the channel mapping
        for this site.  Specify a time split.  The NTU scale factor is doubled
        in the 2nd half of the deployment.

        EXPECTED RESULT:  The chl, ntu, o2, and o2 temp are verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            deployment_number=12
        )

        with XCO2Reduce(
            self.raw_path, self.reduced_path,
            chl_scale_factor=[9, 9],
            chl_dark_count=[0.065, 0.065],
            ntu_scale_factor=[5, 10],
            ntu_dark_count=[0.076, 0.076],
            chl_global_conversion=1,
            o2_salinity_setting=[0, 0],
            instrument_time_split=dt.datetime(2019, 6, 10, 4, 30),
            sbe16_mapping=True
        ) as p1:
            p1.run()

        ncfile = self.reduced_path / core.SBE16_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['chl'].values
            expected = np.array([0.3591, 0.35055, 0.3285, 0.30555])
            np.testing.assert_allclose(actual, expected)

            # 1st and 4th values are nighttime.
            actual = ds['chl_nighttime'].values
            expected = np.array([np.nan, 0.35055, 0.3285, np.nan])
            np.testing.assert_allclose(actual, expected)

            actual = ds['chl_nighttime_qc'].values
            expected = np.array([
                core.quality.DAYTIME, core.quality.GOOD,
                core.quality.GOOD, core.quality.DAYTIME,
            ])
            np.testing.assert_allclose(actual, expected)

            # make sure it has the daytime flag attribute
            self.assertIn(
                core.quality.DAYTIME,
                ds['chl_nighttime_qc'].flag_masks
            )
            self.assertIn(
                "daytime",
                ds['chl_nighttime_qc'].flag_meanings
            )

            actual = ds['ntu'].values
            expected = np.array([3.1625, 3.2925, 6.538, 6.702])
            np.testing.assert_allclose(actual, expected)

            actual = ds['o2'].values
            expected = np.array([188.1965, 186.4967, 185.3627, 184.0634])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['o2_temp'].values
            expected = np.array([29.5105, 29.4835, 29.4268, 29.4034])
            np.testing.assert_allclose(actual, expected)

            # There's only one observation for the variables here, so the
            # stddevs is all zero.
            for variable in [
                'chl_stddev', 'ntu_stddev', 'o2_temp_stddev', 'o2_stddev'
            ]:
                actual = ds[variable].values
                expected = np.zeros((len(actual),))
                np.testing.assert_equal(actual, expected)

            # and the regular variables...
            actual = ds['current'].values
            expected = np.array([206.6, 198.4, 196.1, 189.7])
            np.testing.assert_allclose(actual, expected)

            actual = ds['density'].values
            expected = np.array([22.9135, 22.9251, 22.9481, 22.9459])
            np.testing.assert_allclose(actual, expected)

    def test_more_than_one_timesplit(self):
        """
        SCENARIO:  An array of timesplits is passed for the
        instrument_time_split keyword parameter.

        EXPECTED RESULT:  RuntimeError
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            deployment_number=12
        )

        with self.assertRaises(RuntimeError):
            with XCO2Reduce(
                self.raw_path, self.reduced_path,
                chl_scale_factor=[9, 8],
                chl_dark_count=[0.065, 0.070],
                ntu_scale_factor=[5, 6],
                ntu_dark_count=[0.076, 0.08],
                chl_global_conversion=1,
                o2_salinity_setting=[0, 0],
                instrument_time_split=[
                    dt.datetime(2022, 1, 1), dt.datetime(2022, 2, 1)
                ],
                sbe16_mapping=True
            ) as p:
                p.run()

    def test_no_o2_or_o2_temp(self):
        """
        SCENARIO:  Process a whots file.  There is only data for two channels,
        which will be chl and ntu.

        EXPECTED RESULT:  The chl and ntu are verified, and there is no o2 or
        o2 temp in the output.
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots.depl12',
            'mapco2_whots_0132_dp12_20180922__20191011.txt',
        )

        with XCO2Reduce(
            self.raw_path, self.reduced_path,
            chl_scale_factor=[9],
            chl_dark_count=[0.065],
            ntu_scale_factor=[5],
            ntu_dark_count=[0.076],
            o2_salinity_setting=[0],
            chl_global_conversion=1,
            sbe16_mapping=True
        ) as p1:
            p1.run()

        ncfile = self.reduced_path / core.SBE16_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['chl'].values
            expected = np.array([0.2628, 0.27405, 0.26415, 0.2628])
            np.testing.assert_allclose(actual, expected)

            actual = ds['chl_nighttime'].values
            expected = np.array([np.nan, np.nan, 0.26415, 0.2628])
            np.testing.assert_allclose(actual, expected)

            actual = ds['chl_nighttime_qc'].values
            expected = np.array([
                core.quality.DAYTIME, core.quality.DAYTIME,
                core.quality.GOOD, core.quality.GOOD,
            ])
            np.testing.assert_allclose(actual, expected)

            actual = ds['ntu'].values
            expected = np.array([0.066, 0.3335, 0.169, 0.199])
            np.testing.assert_allclose(actual, expected)

            self.assertFalse('o2' in ds)
            self.assertFalse('o2_temp' in ds)
