# standard library imports
from importlib.resources import files, as_file
import importlib.resources as ir
import pathlib
import unittest

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.report_writer import *
from . import test_core


class TestSuite(test_core.TestSuite):
    
    def test_reportwriterwidget_input_default(self):
        writer = ReportWriterWidget()
        self.assertEqual(writer.src_dir_input.value, '')
        self.assertEqual(writer.station_name_input.value, '')
        self.assertEqual(writer.deployment_number_input.value, 1)
    
    def test_reportwriterwidget_input(self):
        writer = ReportWriterWidget('test', 'test2', 2)
        self.assertEqual(writer.src_dir_input.value, 'test')
        self.assertEqual(writer.station_name_input.value, 'test2')
        self.assertEqual(writer.deployment_number_input.value, 2)
    
    def test_widget_fields_response(self):
        with ReportWriterWidget('not_a_directory') as writer:
            writer._check_fields()
            self.assertEqual(writer.src_dir_input.style.background, 'red')
            self.assertEqual(writer.station_name_input.style.background, 'red')
            
            writer.src_dir_input.value = '.'
            writer._check_fields()
            self.assertIsNone(writer.src_dir_input.style.background)
            self.assertEqual(writer.station_name_input.style.background, 'red')
            
            writer.station_name_input.value = 'test'
            writer._check_fields()
            self.assertIsNone(writer.station_name_input.style.background)
    
    def test_widget_bad_station_name_input(self):
        with ReportWriterWidget('.') as writer:
            writer._write_document(None)
            self.assertEqual(writer.station_name_input.style.background, 'red')
    
    def test_directory_error_socat(self):
        """
        Scenario: SOCAT csv and QF logs are strictly necessary, program should throw error if one or more are missing (in this case csv).
        """
        
        folder = files('tests.data.report').joinpath('missing_socat')
        self.assertRaises(DirectoryStructureException, ReportWriter, folder, {})
    
    def test_directory_error_merge(self):
        """
        Scenario: merge.nc is strictly necessary, program should throw error if the file is missing.
        """
        folder = files('tests.data.report').joinpath('missing_merge')
        self.assertRaises(DirectoryStructureException, ReportWriter, folder, {})
    
    def test_missing_historic_and_config(self):
        """
        Scenario: Historic and config data are not strictly necessary, if they are not found, they should be None
        """
        
        folder = files('tests.data.report').joinpath('missing_historic')
        writer = ReportWriter(folder, {})
        self.assertIsNone(writer.historic_data)
        self.assertIsNone(writer.config)
    
    def test_aux_plotters_exist(self):
        """
        Scenario: deployment has aux parameters, these should exist in ReportWriter.aux_plotters dict.
        """
        folder = files('tests.data.report').joinpath('missing_historic')
        writer = ReportWriter(folder, {})
        
        self.assertIn('pH_sw', writer.aux_plotters)
        self.assertIsInstance(writer.aux_plotters['pH_sw'], ParameterPlotter)
        
        self.assertIn('CHL (night time)', writer.aux_plotters)
        self.assertIsInstance(writer.aux_plotters['CHL (night time)'], ParameterPlotter)
        
        self.assertIn('NTU', writer.aux_plotters)
        self.assertIsInstance(writer.aux_plotters['NTU'], ParameterPlotter)
        
        self.assertIn('DOXY', writer.aux_plotters)
        self.assertIsInstance(writer.aux_plotters['DOXY'], ParameterPlotter)
    
    def test_aux_plotters_missing(self):
        """
        Scenario: deployment does not have aux parameters, these should not exist in ReportWriter.aux_plotters dict.
        """
        
        folder = files('tests.data.report').joinpath('missing_aux')
        writer = ReportWriter(folder, {})
        self.assertNotIn('pH_sw', writer.aux_plotters)
        self.assertNotIn('CHL (night time)', writer.aux_plotters)
        self.assertNotIn('NTU', writer.aux_plotters)
        self.assertNotIn('DOXY', writer.aux_plotters)
    
    def test_getdata_bad_param(self):
        """
        ReportWriter should not fail at a bad measurement name, since there is no parameter, there is no data 
        """
        
        folder = files('tests.data.report').joinpath('missing_historic')
        writer = ReportWriter(folder, {})
        good, questionable, bad, historic = writer._get_data('test', 'test')
        self.assertIsNone(good)
        self.assertIsNone(questionable)
        self.assertIsNone(bad)
        self.assertIsNone(historic)
    
    def test_getdata_sst_no_historic(self):
        """
        Scenario: SST has no entries in QF Log, so there should be no questionable or bad data, only good data.
        Since no historic data is loaded, historic should be None as well.
        """
        
        folder = files('tests.data.report').joinpath('missing_historic')
        writer = ReportWriter(folder, {})
        good, questionable, bad, historic, use_colorblind = writer._get_data('sst (c)', 'SST')
        expected_datetimes = pd.to_datetime([
                                             '12/26/2022 00:17',
                                             '12/26/2022 03:17',
                                             '12/26/2022 06:17',
                                             '12/26/2022 09:17',
                                             '12/26/2022 12:17',
                                             '12/26/2022 15:17',
                                             '12/26/2022 18:17',
                                             '12/26/2022 21:17',
                                            ])
        expected_measurements = np.array([8.921, 8.922, 8.549, 8.475, 8.71, 8.896, 8.867, 8.844])
        np.testing.assert_array_equal(good.index.to_numpy(), expected_datetimes)
        np.testing.assert_array_almost_equal(good.to_numpy(), expected_measurements, decimal=10e-5)
        self.assertIsNone(questionable)
        self.assertIsNone(bad)
        self.assertIsNone(historic)
        
    def test_parameterplotter_sst_no_historic(self):
        """
        Check that data is properly transfered to plotter object.
        """
        folder = files('tests.data.report').joinpath('missing_historic')
        writer = ReportWriter(folder, {})
        plotter = writer.standard_plotters['SST']
        
        expected_measurements = np.array([8.921, 8.922, 8.549, 8.475, 8.71, 8.896, 8.867, 8.844])
        np.testing.assert_array_almost_equal(plotter.data_good.to_numpy(), expected_measurements, decimal=10e-5)
        self.assertIsNone(plotter.data_questionable)
        self.assertIsNone(plotter.data_bad)
        self.assertIsNone(plotter.historic)
        self.assertEqual(plotter.parameter_name, 'SST')
        self.assertEqual(plotter.parameter_units, r'[$^\circ$C]')
        
    def test_getdata_xco2_air_historic(self):
        folder = files('tests.data.report').joinpath('test')
        writer = ReportWriter(folder, {})
        good, questionable, bad, historic, use_colorblind = writer._get_data('xco2 air (dry) (umol/mol)', 'xCO2_air')
        expected_datetimes = pd.to_datetime([
                                             '12/26/2022 03:17',
                                             '12/26/2022 06:17',
                                             '12/26/2022 09:17',
                                             '12/26/2022 15:17',
                                             '12/26/2022 18:17',
                                             '12/26/2022 21:17',
                                             '12/27/2022 00:17',
                                             '12/27/2022 03:17'
                                            ])
        expected_good_measurements = np.array([419.7, 418.8, 419.2, 420.7, 421.6, 420.9, 421.5, 422.2])
        np.testing.assert_array_equal(good.index.to_numpy(), expected_datetimes)
        np.testing.assert_array_almost_equal(good.to_numpy(), expected_good_measurements, decimal=10e-5)
        
        self.assertEqual(questionable.index.to_numpy()[0], pd.to_datetime('12/26/2022 12:17'))
        np.testing.assert_array_almost_equal(questionable.to_numpy(), np.array([419.0]), decimal=10e-1)
        
        self.assertEqual(bad.index.to_numpy()[0], pd.to_datetime('12/26/2022 00:17'))
        np.testing.assert_array_almost_equal(bad.to_numpy(), np.array([422.8]), decimal=10e-1)
        
        self.assertIsNotNone(historic)
        self.assertEqual(use_colorblind, False)
    
    def test_temp_span_correlation_statements(self):
        """
        get_temp_coeff_corr should return the correct number of statements and have the correct format.
        """
        
        ifile = files('tests.data.report.test.reduced').joinpath(core.MODELS_FILE)
        statements = get_temp_coeff_corr(ifile)
        
        assert len(statements) == 1
        self.assertEqual(statements[0], '-0.000415 * Licor_Temp + 0.9437, R² = 0.0349')
    
    def test_mbl_correction(self):
        """
        mbl_correction should report the correct MBL correction.
        """
        
        ifile = files('tests.data.report.missing_aux.merge').joinpath(core.MERGE_NCFILE)
        self.assertAlmostEqual(mbl_correction(ifile), -1.0, places=10e-5)
        
    def test_round_percent(self):
        """
        Scenario: Reported statistics are rounded for readability. Rounding depends on the value of the percent.
        """
        
        self.assertEqual(0.101, round_percent(0.1011))
        self.assertEqual(9.12, round_percent(9.123))
        self.assertEqual(10.0, round_percent(10))
    
    def test_flag_statistics(self):
        """
        Scenario: Statistics for quality flags should return mathmatically accurate results.
        CHL does not count flag 5s due to daytime measurements.
        A QF column of only bad or missing values is reported as a failed.
        """
        
        stats = {
                 'xCO2 QF': [2, 2, 3, 4, 2, 2, 2, 2, 3, 2, 5],
                 'CHL QF': [2, 5, 2, 2, 3, 4, 2, 2, 2, 2, 2],
                 'pH QF': [5, 4, 5, 4, 5, 4, 5, 5, 5, 5, 5],
                }
        test_df = pd.DataFrame(stats)
        
        expected_xco2 = ['xCO2', '7 (63.6%)', '2 (18.2%)', '1 (9.09%)', '1 (9.09%)']
        expected_chl = ['CHL', '8 (80.0%)', '1 (10.0%)', '1 (10.0%)', 'N/A']
        expected_ph = ['pH', 'Failed', 'Failed', 'Failed', 'Failed']
        
        actual = flag_statistics(test_df)
        self.assertTrue(expected_xco2 == actual[0])
        self.assertTrue(expected_chl == actual[1])
        self.assertTrue(expected_ph == actual[2])