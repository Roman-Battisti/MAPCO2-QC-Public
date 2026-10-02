# standard library imports
import unittest

# 3rd party library imports
import numpy as np

# local imports
from xco2qc.science_algorithms import ta


class TestSuite(unittest.TestCase):

    def test_washington_state(self):

        sss = np.array([10, 20])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=1)
        expected = np.array([1124, 1601])
        np.testing.assert_array_equal(actual, expected)

    def test_california_current_ecosystem(self):

        sss = np.array([32.15, 33.15])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=2)
        expected = np.array([2176.72, 2227.52])
        np.testing.assert_array_equal(actual, expected)

    def test_south_atlantic_bight(self):

        sss = np.array([10, 20])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=3)
        expected = np.array([1070.23, 1566.83])
        np.testing.assert_array_equal(actual, expected)

    def test_gulf_of_maine(self):

        sss = np.array([10, 20])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=4)
        expected = np.array([1001, 1526])
        np.testing.assert_array_equal(actual, expected)

    def test_kuroshio_extension(self):

        sss = np.array([10, 20])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=5)
        expected = np.array([705, 1335])
        np.testing.assert_array_equal(actual, expected)

    def test_northeast_pacific(self):

        sss = np.array([10, 20])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=6)
        expected = np.array([1358, 1728])
        np.testing.assert_array_equal(actual, expected)

    def test_north_atlantic_subtropics_split(self):
        """
        Scenario:  anything SST > 20 uses the subtropics
        """

        sss = np.array([37, 36])
        sst = np.array([21, 19])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=7)
        expected = np.array([2430.23, 2362.83])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_north_atlantic_30n_80n(self):

        sss = np.array([37, 36])
        sst = np.array([18, 19])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=7)
        expected = np.array([2426.06, 2362.83])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_north_pacific(self):

        sss = np.array([37, 36])
        sst = np.array([18, 19])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=8)
        expected = np.array([2417.288, 2359.514])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_north_pacific_split(self):
        """
        Scenario: some of the SST > 20 ==> subtropics equation
        """

        sss = np.array([37, 36])
        sst = np.array([18, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=8)
        expected = np.array([2417.288, 2364.61])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_north_pacific_negative_longitude(self):

        sss = np.array([37, 36])
        sst = np.array([19, 18])
        longitude = np.array([245, 244]) - 360

        actual = ta.compute_ta(sss, sst, longitude, region=8)
        expected = np.array([2418.232, 2358.632])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_subtropics_atlantic_split(self):
        """
        Scenario:  some SST < 20

        Expected results:  SST < 20 ==> north atlantic equation
        """

        sss = np.array([37, 36])
        sst = np.array([18, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=9)
        expected = np.array([2426.06, 2364.61])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_subtropics_atlantic(self):

        sss = np.array([37, 36])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=9)
        expected = np.array([2428.94, 2364.61])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_subtropics_pacific_split(self):
        """
        Scenario:  when sst < 20, use north pacific equation
        """

        sss = np.array([37, 36])
        sst = np.array([19, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=10)
        expected = np.array([2418.232, 2364.61])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_subtropics_pacific(self):

        sss = np.array([37, 36])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=10)
        expected = np.array([2428.94, 2364.61])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_subtropics_indian_split(self):
        """
        Scenario:  when sst < 20, use southern ocean
        """

        sss = np.array([37, 36])
        sst = np.array([19, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=11)
        expected = np.array([2421.936, 2364.61])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_subtropics_indian(self):

        sss = np.array([37, 36])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=11)
        expected = np.array([2428.94, 2364.61])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_eastern_pacific_equatorial_upwelling_pacific_split(self):
        """
        Scenario:  when sst < 18, use subtropics
        """

        sss = np.array([37, 36])
        sst = np.array([17, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=12)
        expected = np.array([2436.19, 2380.582])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_eastern_pacific_equatorial_upwelling_pacific(self):

        sss = np.array([37, 36])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=12)
        expected = np.array([2445.592, 2380.582])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_central_pacific_equatorial_upwelling_pacific_split(self):
        """
        Scenario: when sst < 18, use subtropics
        """

        sss = np.array([37, 36])
        sst = np.array([17, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=13)
        expected = np.array([2436.19, 2380.582])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_central_pacific_equatorial_upwelling_pacific(self):

        sss = np.array([37, 36])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=13)
        expected = np.array([2445.592, 2380.582])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_equatorial_pacific_upwelling_pacific_not_central_or_eastern(self):

        sss = np.array([37, 36])
        sst = np.array([22, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=14)
        expected = np.array([2428.94, 2364.61])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_southern_ocean(self):

        sss = np.array([37, 36])
        sst = np.array([11, 12])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=15)
        expected = np.array([2432.736, 2369.754])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_southern_ocean_split(self):
        """
        Scenario:  when sst > 20, use subtropics
        """

        sss = np.array([37, 36])
        sst = np.array([19, 21])
        longitude = np.array([245, 244])

        actual = ta.compute_ta(sss, sst, longitude, region=15)
        expected = np.array([2421.936, 2364.61])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)
    
    def test_cce1(self):
        sss = np.array([37, 36])
        sst = np.array([19, 21])
        longitude = np.array([245, 244])
        
        actual = ta.compute_ta(sss, sst, longitude, region=16)
        expected = np.array([2419.3895, 2370.9838])
        np.testing.assert_array_almost_equal(actual, expected, decimal=4)
    
    def test_cce2(self):
        sss = np.array([37, 36])
        sst = np.array([19, 21])
        longitude = np.array([245, 244])
        
        actual = ta.compute_ta(sss, sst, longitude, region=17)
        expected = np.array([2412.0256, 2361.4949])
        np.testing.assert_array_almost_equal(actual, expected, decimal=4)