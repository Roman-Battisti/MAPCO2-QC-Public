"""
Tests for O2 opendap climatology.
"""

# standard library imports
import pathlib
from unittest import mock
from unittest.mock import MagicMock

# 3rd party library imports
import numpy as np
import pandas as pd

# local imports
from xco2qc.remote_climatology import OpenDAPO2Climatology
from . import test_core


@mock.patch('xco2qc.remote_climatology.pathlib.Path.home')
@mock.patch('xco2qc.remote_climatology.xr')
class TestSuite(test_core.TestSuite):
    """
    """
    def test_smoke(self, mock_xr, mock_pathlib_home):
        """
        Scenario:  interpolate a lat/lon timeseries to an o2 climatology.

        Expected results:  No errors.
        """
        # setup a mock that returns two values, a 2-item time series for the
        # month of november, and a single item series for the month of december
        side_effect = [
            np.array([1, 2]), np.array([3])
        ]

        # this is the numpy array referenced by the DA's value attribute
        mock_np = MagicMock()
        mock_np.diagonal.side_effect = side_effect

        # this is the data array referenced by the dataset's dictionary
        # and indexing
        mock_da = MagicMock()
        mock_da.interp.return_value.values = mock_np

        # this is the data set returned by xarray's open_dataset.
        # it must perform a dictionary look up.
        mock_ds = MagicMock()
        mock_ds.__getitem__.return_value = mock_da

        # open_dataset invokes a context manager whose return value is a data
        # set
        mock_xr.open_dataset.return_value.__enter__.return_value = mock_ds

        index = pd.date_range(start='2021-11-15', periods=3, freq='10D')
        latitude = np.array([45.5, 46.5, 47.5])
        longitude = np.array([-115, -116, -117])
        data = {'latitude': latitude, 'longitude': longitude}
        deployment = pd.DataFrame(data, index=index)

        with OpenDAPO2Climatology(deployment) as o:
            o.interpolate()

        actual = o.ts
        expected = pd.Series(
            index=index, data=[1, 2, 3], dtype=np.float64,
            name='o2 climatology',
        )
        pd.testing.assert_series_equal(actual, expected)

    def test_check_coverage(self, mock_xr, mock_pathlib_home):
        """
        Scenario:  the deployment spans two months and the cache is empty

        Expected results:  two downloads are recorded
        """
        mock_pathlib_home.return_value = self.root

        # this data partially covers two months
        index = pd.date_range(start='2021-11-15', periods=3, freq='10D')
        latitude = np.array([45.5, 46.5, 47.5])
        longitude = np.array([-115, -116, -117])
        data = {'latitude': latitude, 'longitude': longitude}
        deployment = pd.DataFrame(data, index=index)

        with OpenDAPO2Climatology(deployment) as o:
            with mock.patch.object(o, 'update_cache') as patch_cache:
                o.check_coverage()

                self.assertEqual(len(patch_cache.mock_calls), 2)

    @mock.patch('xco2qc.remote_climatology.pathlib.Path.glob')
    def test_check_gappy_coverage(
        self, patch_glob, mock_xr, mock_pathlib_home
    ):
        """
        Scenario:  the cache is missing data for half of the months of the year
        and the deployment spans an entire year

        Expected results:  six downloads are recorded for the missing months
        """
        mock_pathlib_home.return_value = self.root

        # 6 monthly files are present in the cache
        ncfiles = [
            '02.nc', '04.nc', '06.nc', '08.nc', '10.nc', '12.nc'
        ]
        patch_glob.side_effect = [
            [pathlib.Path(ncfile) for ncfile in ncfiles]
        ]

        # this data spans 12 months
        index = pd.date_range(start='2021-11-15', periods=36, freq='10D')
        latitude = np.full((36,), 45)
        longitude = np.full((36,), 45)
        data = {'latitude': latitude, 'longitude': longitude}
        deployment = pd.DataFrame(data, index=index)

        with OpenDAPO2Climatology(deployment) as o:
            with mock.patch.object(o, 'update_cache') as patch_cache:
                o.check_coverage()

                # six months of data need to be retrieved
                self.assertEqual(len(patch_cache.mock_calls), 6)
