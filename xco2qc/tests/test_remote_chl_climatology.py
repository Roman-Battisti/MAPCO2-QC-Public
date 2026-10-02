"""
Tests for accessing the remote CHL climatology.
"""

# standard library imports
import datetime as dt
import pathlib
import os
from unittest import mock

# 3rd party library imports
import numpy as np
import pandas as pd

# local imports
from xco2qc.remote_climatology import ChlCache
from . import test_core


@mock.patch('xco2qc.remote_climatology.pathlib.Path.home')
class TestSuite(test_core.TestSuite):
    """
    """
    def setUp(self):

        super().setUp()

        # Basic timeseries of gps latitude and longitude for three months.
        # 585 values here
        index = pd.date_range(start='2022-01-15', end='2022-03-22', freq='3h')
        latitude = np.linspace(44, 47, num=len(index))
        longitude = np.linspace(-112, -115, num=len(index))
        data = {'latitude': latitude, 'longitude': longitude}
        self.deployment = pd.DataFrame(data, index=index)

        # Write a default configuration that has credentials.
        self.config['chl_credentials'] = {
            'username': 'whoisit', 'password': 'thepassword'
        }
        self._write_config_file()
        self.configfile = self.root / 'config.yml'

    def test_local_cache_does_not_exist(self, mock_pathlib_path):
        """
        Scenario:  The local cache does not exist.

        Expected result:  The cache is created.
        """
        mock_pathlib_path.return_value = self.root

        o = ChlCache(self.deployment, self.configfile)
        self.assertTrue(o.cachedir.exists())

    def test_cache_empty(self, mock_pathlib_path):
        """
        Scenario:  The local cache is empty.  The common deployment coverage
        is 2022-01-15 through 2022-03-22.

        Expected results:  The cache retrieval is called three times, for 2022
        January, February, and March.
        """
        mock_pathlib_path.return_value = self.root

        with ChlCache(self.deployment, self.configfile) as o:

            with mock.patch.object(o, 'update_cache') as patch_cache:
                o.check_coverage()

                self.assertEqual(len(patch_cache.mock_calls), 3)

    def test_cache_covers_middle_of_deployment(self, mock_pathlib_path):
        """
        Scenario:  The local cache covers only the middle of the deployment.
        The beginning month and end month are not covered.

        Expected results:  The cache retrieval is called twice, once for the
        start of the deployment and once for the end.
        """
        mock_pathlib_path.return_value = self.root

        ncfilenames_before = [
            "L3m_20220201-20220228__GLOB_4_AV-MOD_CHL1_MO_00.nc"
        ]
        side_effect = [
            [pathlib.Path(ncfile) for ncfile in ncfilenames_before],
        ]

        with mock.patch(
            'xco2qc.remote_climatology.pathlib.Path.glob',
            side_effect=side_effect
        ):
            with ChlCache(self.deployment, self.configfile) as o:

                with mock.patch.object(o, 'update_cache') as patch_cache:
                    o.check_coverage()

                self.assertEqual(len(patch_cache.mock_calls), 2)

    def test_cache_misses_end_of_deployment(self, mock_pathlib_path):
        """
        Scenario:  The local cache does not cover the final month of the
        deployment.

        Expected results:  The cache retrieval is called once for the final
        month.
        """
        mock_pathlib_path.return_value = self.root

        ncfilenames = [
            "L3m_20220101-20220131__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20220201-20220228__GLOB_4_AV-MOD_CHL1_MO_00.nc",
        ]
        side_effect = [[pathlib.Path(ncfile) for ncfile in ncfilenames]]

        with mock.patch(
            'xco2qc.remote_climatology.pathlib.Path.glob',
            side_effect=side_effect
        ):
            with ChlCache(self.deployment, self.configfile) as o:
                with mock.patch.object(o, 'update_cache') as patch_cache:
                    o.check_coverage()

                self.assertEqual(len(patch_cache.mock_calls), 1)

    def test_cache_misses_beginning_of_deployment(self, mock_pathlib_path):
        """
        Scenario:  The local cache does not cover the starting month of the
        deployment.

        Expected results:  The cache retrieval is called once for the starting
        month.
        """
        mock_pathlib_path.return_value = self.root

        ncfilenames = [
            "L3m_20220201-20220228__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20220301-20220331__GLOB_4_AV-MOD_CHL1_MO_00.nc",
        ]
        side_effect = [[pathlib.Path(ncfile) for ncfile in ncfilenames]]

        with mock.patch(
            'xco2qc.remote_climatology.pathlib.Path.glob',
            side_effect=side_effect
        ):
            with ChlCache(self.deployment, self.configfile) as o:
                with mock.patch.object(o, 'update_cache') as patch_cache:
                    o.check_coverage()

                self.assertEqual(len(patch_cache.mock_calls), 1)

    def test_cache_covers_entire_deployment(self, mock_pathlib_path):
        """
        Scenario:  The local cache covers the entire deployment.

        Expected results:  The cache retrieval is called exactly zero times.
        """
        mock_pathlib_path.return_value = self.root

        ncfilenames = [
            "L3m_20220101-20220131__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20220202-20220228__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20220301-20220331__GLOB_4_AV-MOD_CHL1_MO_00.nc",
        ]
        side_effect = [[pathlib.Path(ncfile) for ncfile in ncfilenames]]

        with mock.patch(
            'xco2qc.remote_climatology.pathlib.Path.glob',
            side_effect=side_effect
        ):
            with ChlCache(self.deployment, self.configfile) as o:
                with mock.patch.object(o, 'update_cache') as patch_cache:
                    o.check_coverage()

                self.assertEqual(len(patch_cache.mock_calls), 0)

    def test_credentials_missing(self, mock_pathlib_path):
        """
        Scenario:  The configuration file is missing the chl_credentials
        section.

        Expected results:  KeyError
        """
        mock_pathlib_path.return_value = self.root

        # Write a default configuration that has no credentials.
        self.config.pop('chl_credentials')
        self._write_config_file()
        self.configfile = self.root / 'config.yml'

        with self.assertRaises(KeyError):
            ChlCache(self.deployment, self.configfile)

    def test_deployment_spans_multiple_years(self, mock_pathlib_path):
        """
        Scenario:  The deployment spans Dec 15 2020 thru Feb 15 2022.  The
        cache only spans from March 2021 thru October 2021.

        Expected results:  The cache retrieval is called 3 times for the
        beginning of the deployment and 4 times for the end.
        month.
        """
        index = pd.date_range(start='2020-12-15', end='2022-02-15', freq='3h')
        latitude = np.linspace(44, 47, num=len(index))
        longitude = np.linspace(-112, -115, num=len(index))
        data = {'latitude': latitude, 'longitude': longitude}
        deployment = pd.DataFrame(data, index=index)

        mock_pathlib_path.return_value = self.root

        ncfilenames = [
            "L3m_20210301-20210331__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20210401-20210431__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20210501-20210531__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20210601-20210631__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20210701-20210731__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20210801-20210831__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20210901-20210931__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20211001-20211031__GLOB_4_AV-MOD_CHL1_MO_00.nc",
        ]
        side_effect = [[pathlib.Path(ncfile) for ncfile in ncfilenames]]

        with mock.patch(
            'xco2qc.remote_climatology.pathlib.Path.glob',
            side_effect=side_effect
        ):
            with ChlCache(deployment, self.configfile) as o:
                with mock.patch.object(o, 'update_cache') as patch_cache:
                    o.check_coverage()

                self.assertEqual(len(patch_cache.mock_calls), 7)

    @mock.patch('xco2qc.remote_climatology.FTP')
    def test_update_cache(self, mock_ftplib, mock_pathlib_path):
        """
        Scenario:  The local cache does not cover the starting month of the
        deployment.

        Expected results:  The cache retrieval is called four times,
        constituting a single retrieval.
        """
        mock_pathlib_path.return_value = self.root

        ncfilenames = [
            "L3m_20220102-20220228__GLOB_4_AV-MOD_CHL1_MO_00.nc",
            "L3m_20220203-20220331__GLOB_4_AV-MOD_CHL1_MO_00.nc",
        ]
        side_effect = [[pathlib.Path(ncfile) for ncfile in ncfilenames]]

        with mock.patch(
            'xco2qc.remote_climatology.pathlib.Path.glob',
            side_effect=side_effect
        ):
            with ChlCache(self.deployment, self.configfile) as o:
                o.update_cache(dt.datetime(2022, 1, 1))

        self.assertEqual(len(mock_ftplib.mock_calls), 4)
        self.assertEqual(len(o.cache_contents), 3)

    def test_make_cache_timeseries(self, mock_pathlib_path):
        """
        Scenario:  We have a complete cache for a given deployment.

        Expected results:  Construct a time series from the cache.
        """
        index = pd.date_range(start='2021-11-15', end='2022-03-15', freq='3h')
        latitude = np.linspace(44, 47, num=len(index))
        longitude = np.linspace(-112, -115, num=len(index))
        data = {'latitude': latitude, 'longitude': longitude}
        deployment = pd.DataFrame(data, index=index)

        mock_pathlib_path.return_value = self.root

        with mock.patch(
            'xco2qc.remote_climatology.pathlib.Path.glob'
        ) as patch_glob:

            # each of these files is present, so the cache is complete
            ncfiles = [
                f"{self.root}{os.sep}L3m_202111.nc",
                f"{self.root}{os.sep}L3m_202112.nc",
                f"{self.root}{os.sep}L3m_202201.nc",
                f"{self.root}{os.sep}L3m_202202.nc",
                f"{self.root}{os.sep}L3m_202203.nc",
            ]
            patch_glob.side_effect = [
                [pathlib.Path(ncfile) for ncfile in ncfiles]
            ]

            with ChlCache(deployment, self.configfile) as o:
                o.map_cache_back_to_deployment()

                actual = o.cache_mapping

                # convert to string for easier comparison
                for idx, value in actual.items():
                    actual[idx] = str(actual[idx])

                index = pd.DatetimeIndex([
                    pd.Timestamp(2021, 11, 15),
                    pd.Timestamp(2021, 12, 15),
                    pd.Timestamp(2022, 1, 15),
                    pd.Timestamp(2022, 2, 15),
                    pd.Timestamp(2022, 3, 15),
                ])
                expected = pd.Series(ncfiles, index=index)

                pd.testing.assert_series_equal(actual, expected)

    @mock.patch('xco2qc.remote_climatology.xr')
    def test_da_interpolate(self, mock_xr, mock_pathlib_path):
        """
        Scenario:  interpolate a lat/lon timeseries to a chl climatology file

        Expected results:  Not sure how to mock this yet.
        """
        mock_pathlib_path.return_value = self.root

        index = pd.date_range(start='2021-11-15', periods=3, freq='3D')
        latitude = np.array([45.5, 46.5, 47.5])
        longitude = np.array([-115, -116, -117])
        data = {'latitude': latitude, 'longitude': longitude}
        deployment = pd.DataFrame(data, index=index)

        with ChlCache(deployment, self.configfile) as o:
            o.interpolate_cache(index, 'cache.nc')

            # there is a call to open_dataset
            mock_xr.assert_has_calls(
                [mock.call.open_dataset('cache.nc')], any_order=True
            )
