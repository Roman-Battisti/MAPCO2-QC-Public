# standard library imports
import unittest

# 3rd party library imports
import numpy as np
import pytest

# local imports
from xco2qc.Outlier_Detector import (
    OutlierDetector, byFrameGeneratorFactory, InterquartileVarianceAlgorithm,
)


class TestSuiteVariance(unittest.TestCase):
    """
    Use the frame generator factory.
    """

    def setUp(self):
        np.random.seed(seed=42)

    def test_no_outliers(self):
        """
        SCENARIO:  the data is fairly regular, i.e. no outliers

        EXPECTED RESULT:  no outliers detected
        """
        data = np.random.random_sample((20, 1))
        od = OutlierDetector(
            byFrameGeneratorFactory(), InterquartileVarianceAlgorithm()
        )
        outliers = od.outliers(data)
        self.assertEqual(len(np.argwhere(outliers)), 0)

    @pytest.mark.filterwarnings("ignore:invalid value encountered")
    def test_one_outlier(self):
        """
        SCENARIO:  one outlier

        EXPECTED RESULT:  out outlier detected
        """
        data = np.random.random_sample((20, 1))
        outlier = 10
        data[outlier, 0] = 5
        od = OutlierDetector(
            byFrameGeneratorFactory(), InterquartileVarianceAlgorithm()
        )
        outliers = od.outliers(data)
        np.testing.assert_array_equal(np.argwhere(outliers),
                                      np.array([[outlier, 0]]))


class TestSuiteFrame(unittest.TestCase):
    """
    Use the frame generator factory.
    """

    def setUp(self):
        np.random.seed(seed=42)

    def test_fairly_constant_data(self):
        """
        SCENARIO:  the data is constant

        EXPECTED RESULT:  no outliers detected, and the data is not changed
        """
        n = 25
        data = np.full((n,), -19.621525) + np.random.randn(n) / 1000
        expected = data.copy()
        od = OutlierDetector(byFrameGeneratorFactory(frame=4),
                             InterquartileVarianceAlgorithm())
        outliers = od.outliers(data)
        self.assertEqual(len(np.argwhere(outliers)), 0)
        np.testing.assert_allclose(data, expected)

    def test_no_outliers(self):
        """
        SCENARIO:  the data is fairly regular, i.e. no outliers.
        generator.

        EXPECTED RESULT:  no outliers detected
        """
        data = np.random.random_sample((20, 1))
        od = OutlierDetector(byFrameGeneratorFactory(),
                             InterquartileVarianceAlgorithm())
        outliers = od.outliers(data)
        self.assertEqual(len(np.argwhere(outliers)), 0)

    def test_one_outlier(self):
        """
        SCENARIO:  one outlier

        EXPECTED RESULT:  out outlier detected
        """
        data = np.random.random_sample((20, 1))
        outlier = 10
        data[outlier, 0] = 5
        od = OutlierDetector(byFrameGeneratorFactory(),
                             InterquartileVarianceAlgorithm())
        outliers = od.outliers(data)
        np.testing.assert_array_equal(np.argwhere(outliers),
                                      np.array([[outlier, 0]]))

    def test_two_outliers(self):
        """
        SCENARIO:  one outlier

        EXPECTED RESULT:  out outlier detected
        """
        data = np.random.random_sample((40, 1))
        data[10, 0] = 5
        data[30, 0] = 5
        od = OutlierDetector(
            byFrameGeneratorFactory(), InterquartileVarianceAlgorithm()
        )
        outliers = od.outliers(data)
        np.testing.assert_array_equal(np.argwhere(outliers),
                                      np.array([[10, 0],
                                                [30, 0]]))

    def test_nans(self):
        """
        SCENARIO:  There is a NaN in data that otherwise would not have any
        outliers.

        EXPECTED RESULT:  the NaN is not counted as an outlier
        """
        data = np.random.random_sample((17, 1))
        data[5, 0] = np.nan
        od = OutlierDetector(byFrameGeneratorFactory(),
                             InterquartileVarianceAlgorithm())
        outliers = od.outliers(data)
        self.assertEqual(len(np.argwhere(outliers)), 0)
