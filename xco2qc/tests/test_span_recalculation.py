# standard library imports
import importlib.resources as ir

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.span2_coefficient import FixSpan2Coefficient, SpanRecalculation
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(self, module, filename):
        """
        Shortcut for running just raw processing.
        """

        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
            ) as p0:
                p0.run()
    
    def test_smoke(self):
        """
        SCENARIO:  Run FixSpan2Coefficient while leaving span_correction as False

        EXPECTED RESULT:  No change in span coefficients
        """
        
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )
        
        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            expected = ds['span_coefficient'][:]
            
        with FixSpan2Coefficient(ncfile) as p:
            p.run()
        
        with xr.open_dataset(ncfile) as ds:
            actual = ds['span_coefficient'][:]
        
        np.testing.assert_allclose(actual, expected, rtol=1e-7)
    
    def test_not_valid_filepath(self):
        """
        SCENARIO:  Run _load_post_hoc_temp_and_span of SpanRecalculation with bad post-hoc file path.

        EXPECTED RESULT:  output temperature and span are None.
        """
        
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )
        
        # not a file
        with SpanRecalculation(self.raw_path / core.CYCLE_HEADER_NCFILE) as p:
            post_hoc_temp, post_hoc_span_coeff = p._load_post_hoc_temp_and_span(self.root / "does_not_exist.csv")
            self.assertIsNone(post_hoc_temp)
            self.assertIsNone(post_hoc_span_coeff)
        
        # not a csv
        with SpanRecalculation(self.raw_path / core.CYCLE_HEADER_NCFILE) as p:
            post_hoc_temp, post_hoc_span_coeff = p._load_post_hoc_temp_and_span(self.raw_path / core.CYCLE_HEADER_NCFILE)
            self.assertIsNone(post_hoc_temp)
            self.assertIsNone(post_hoc_span_coeff)
        
        
    
    def test_wrong_columns(self):
        """
        SCENARIO:  Run _load_post_hoc_temp_and_span of SpanRecalculation with bad post-hoc file (missing column).

        EXPECTED RESULT:  output temperature and span are None.
        """
        
        # missing appropriate colums
        df = pd.DataFrame({"test": [1, 2, 3], "celltemp": [2, 3, 4]})
        fake_oven_data_path = self.raw_path / "test_oven_test.csv"
        df.to_csv(fake_oven_data_path, index=False)
        
        with SpanRecalculation(self.raw_path / core.CYCLE_HEADER_NCFILE) as p:
            post_hoc_temp, post_hoc_span_coeff = p._load_post_hoc_temp_and_span(fake_oven_data_path)
            self.assertIsNone(post_hoc_temp)
            self.assertIsNone(post_hoc_span_coeff)
    
    def test_correct_post_hoc_data_load(self):
        """
        SCENARIO:  Run _load_post_hoc_temp_and_span of SpanRecalculation with bad post-hoc file (missing column).

        EXPECTED RESULT:  output temperature and span are None.
        """
        
        expected_temperature = np.array([1, 2, 3]).reshape(-1, 1)
        expected_span_coeff = np.array([2, 3, 4]).reshape(-1, 1)
        df = pd.DataFrame({"test": [1, 2, 3], "celltemp": [2, 3, 4]})
        fake_oven_data_path = self.raw_path / "test_oven_test.csv"
        df.to_csv(fake_oven_data_path, index=False)
        
        with SpanRecalculation(self.raw_path / core.CYCLE_HEADER_NCFILE, temperature_column="test", span_coeff_column="celltemp") as p:
            post_hoc_temp, post_hoc_span_coeff = p._load_post_hoc_temp_and_span(fake_oven_data_path)
            np.testing.assert_array_equal(expected_temperature, post_hoc_temp)
            np.testing.assert_array_equal(expected_span_coeff, post_hoc_span_coeff)
    
    def test_corrected_span_bad_post_hoc_data(self):
        """
        SCENARIO:  Run _corrected_span_coefficients of SpanRecalculation with bad post-hoc data.

        EXPECTED RESULT:  output corrected span is None.
        """
        
        post_hoc_temperature = np.array([1, 2, 3]).reshape(-1, 1)
        post_hoc_span_coeff = None
        licor_temperature = np.array([0.5, 2.5]).reshape(-1, 1)
        
        with SpanRecalculation(self.raw_path / core.CYCLE_HEADER_NCFILE) as p:
            actual_corrected_span = p._corrected_span_coefficients(post_hoc_temperature, post_hoc_span_coeff, licor_temperature)
            self.assertIsNone(actual_corrected_span)
    
    def test_corrected_span(self):
        """
        SCENARIO:  Run _corrected_span_coefficients of SpanRecalculation with good post-hoc data.

        EXPECTED RESULT:  output corrected span is correct.
        """
        
        post_hoc_temperature = np.array([1, 2, 3]).reshape(-1, 1)
        post_hoc_span_coeff = np.array([2, 3, 4]).reshape(-1, 1)
        licor_temperature = np.array([0.5, 2.5]).reshape(-1, 1)
        
        expected_corrected_span = np.array([1.5, 3.5]).reshape(-1, 1)
        
        with SpanRecalculation(self.raw_path / core.CYCLE_HEADER_NCFILE) as p:
            actual_corrected_span = p._corrected_span_coefficients(post_hoc_temperature, post_hoc_span_coeff, licor_temperature)
            np.testing.assert_array_equal(expected_corrected_span, actual_corrected_span)
    
    def test_updated_span_coeff_bad_post_hoc(self):
        """
        SCENARIO:  Run SpanRecalculation with improper data (incomplete post-hoc data).

        EXPECTED RESULT:  cycle header span coefficients should not change.
        """
        
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )
        
        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()
        
        with xr.open_dataset(self.reduced_path / core.CYCLE_HEADER_NCFILE) as ds:
            expected = ds['span_coefficient'].to_numpy()
        
        post_hoc_temperature = np.array([1, 2, 3])
        post_hoc_span_coeff = np.array([2, 3, 4])
        df = pd.DataFrame({"celltemp": [1, 2, 3], "test": [2, 3, 4]})
        fake_oven_data_path = self.raw_path / "test_oven_test.csv"
        df.to_csv(fake_oven_data_path, index=False)
        
        with SpanRecalculation(self.reduced_path / core.CYCLE_HEADER_NCFILE) as p:
            p._correct_span_coefficients(fake_oven_data_path)
        
        with xr.open_dataset(self.reduced_path / core.CYCLE_HEADER_NCFILE) as ds:
            actual = ds['span_coefficient'].to_numpy()
            
        np.testing.assert_allclose(actual, expected, rtol=1e-7)
    
    def test_updated_span_coeff(self):
        """
        SCENARIO:  Run SpanRecalculation with proper data.

        EXPECTED RESULT:  cycle header span coefficients corrected.
        """
        
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )
        
        with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
            p1.run()
        
        with xr.open_dataset(self.reduced_path / core.CYCLE_HEADER_NCFILE) as ds:
            expected_uncorrected_span_coeff = ds['span_coefficient'].to_numpy()
        
        spoff_ncfile = self.reduced_path / core.licor.SPOFF_NCFILE
        with xr.open_dataset(spoff_ncfile) as ds:
            spoff_licor_temperature = ds['temperature'].to_numpy()
            expected = spoff_licor_temperature + 1
        
        post_hoc_temperature = np.array([1, 2, 3])
        post_hoc_span_coeff = np.array([2, 3, 4])
        df = pd.DataFrame({"celltemp": [1, 2, 3], "co2kspan": [2, 3, 4]})
        fake_oven_data_path = self.raw_path / "test_oven_test.csv"
        df.to_csv(fake_oven_data_path, index=False)
        
        with SpanRecalculation(self.reduced_path / core.CYCLE_HEADER_NCFILE) as p:
            p._correct_span_coefficients(fake_oven_data_path)
        
        with xr.open_dataset(self.reduced_path / core.CYCLE_HEADER_NCFILE) as ds:
            actual = ds['span_coefficient'].to_numpy()
            actual_uncorrected_span_coeff = ds['uncorrected_span_coefficient'].to_numpy()
            
        np.testing.assert_allclose(actual, expected, rtol=1e-7)
        np.testing.assert_allclose(actual_uncorrected_span_coeff, expected_uncorrected_span_coeff, rtol=1e-7)