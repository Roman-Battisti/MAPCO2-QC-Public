"""
Tests for ensuring that the command line scripts are working.
"""

# standard library imports
import pathlib
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch

# 3rd party libraries
import netCDF4

# local imports
from xco2qc import commandline
from . import test_core


class TestSuite(test_core.TestSuite):

    def setUp(self):
        super().setUp()
        # Setup a scratch directory that will be cleaned up after each test.
        self.tmpdir = tempfile.mkdtemp()
        self.tmppath = pathlib.Path(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)
        super().tearDown()

    @patch('xco2qc.commandline.SocatQC.run')
    def test_compute_socat_qc(self, mymock):
        """
        SCENARIO:  The command line script for transforming the flag bit masks
        into SOCAT QC is run.

        EXPECTED RESULT:  It should not error out.
        """
        new = ['', str(self.merge_ncfile), '--verbosity=critical']
        with patch.object(sys, 'argv', new=new):
            commandline.calculate_socat_qc()

    @patch('xco2qc.commandline.PreXCO2Calc.run')
    def test__calculate_pre_xco2(self, mymock):
        """
        SCENARIO:  The command line script for running the conversion from
        reduced netcdf to pre xco2

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '', self.reduced_dir, '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.calculate_pre_xco2()

    @patch('xco2qc.commandline.PostXCO2Calc.run')
    def test__calculate_xco2(self, mymock):
        """
        SCENARIO:  The command line script for running the conversion from
        reduced netcdf to xco2-calculated.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '', self.reduced_dir, '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.calculate_post_xco2()

    @patch('xco2qc.commandline.XCO2Reduce.run')
    def test__to_reduced(self, mock_lev02lev1):
        """
        SCENARIO:  The command line script for running the conversion from
        raw netcdf to reduced status.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.raw_dir, self.reduced_dir,
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.mapco2_reduce()

    @patch('xco2qc.commandline.RawTextToRawNC.run')
    def test__raw_text_to_raw_nc(self, mock_raw2nc):
        """
        SCENARIO:  The command line script for running the conversion from raw
        text to raw netcdf.

        EXPECTED RESULT:  It should not error out.
        """
        # we need a test file to stand in for mapco2 raw text file.  It doesn't
        # matter what's in it.
        input_raw_text_file = self.tmppath / 'test.txt'
        with input_raw_text_file.open(mode='wt') as f:
            f.write('test')

        new = [
            '',
            str(input_raw_text_file),
            self.reduced_dir,
            '--deployment-number=12',
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.import_mapco2()

    @patch('xco2qc.commandline.MetadataWriter.run')
    def test__apply_metadata_conventions(self, mock_run):
        """
        SCENARIO:  Run the command line script for applying metadata
        conventions.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '', self.trimmed_dir, '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.apply_metadata_conventions()

    @patch('xco2qc.merge.XCO2Merge.run')
    def test_merge(self, mock_run):
        """
        SCENARIO:  Run the command line script for the final merge.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.reduced_dir, str(self.merge_ncfile), '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.merge()

    @patch('xco2qc.adjustments.XCO2Adjustments.run')
    def test_licor_correction(self, mock_run):
        """
        SCENARIO:  Run the command line script for the final adjustments,
        specify the licor pressure correction.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.reduced_dir, str(self.merge_ncfile),
            '--verbosity=critical',
            '--pressure-correction=0.3',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.adjustments()

    @patch('xco2qc.adjustments.XCO2Adjustments.run')
    def test_mbl_correction(self, mock_run):
        """
        SCENARIO:  Run the command line script for the final adjustments,
        specify the MBL xCO2 correction.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.reduced_dir, str(self.merge_ncfile),
            '--mbl-xco2-correction=0.3',
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.adjustments()

    @patch('xco2qc.export_to_csv.ExportToCSV.run')
    def test_nc2csv_smoke(self, mock_run):
        """
        SCENARIO:  Run the export-to-csv utility normally.

        EXPECTED RESULT:  No errors.
        """

        # The netCDF file has to at least exist for the initialization to work.
        ncfile = self.tmppath / 'a.nc'
        with netCDF4.Dataset(ncfile, mode='w'):
            pass

        new = ['', str(ncfile), '/tmp/path/to/file.csv']
        with patch.object(sys, 'argv', new=new):
            commandline.nc2csv()

    @patch('xco2qc.socat.SocatWriter.run')
    def test_socat_smoke(self, mock_run):
        """
        SCENARIO:  Run the SOCAT XML utility normally.

        EXPECTED RESULT:  No errors.
        """

        # The netCDF file has to at least exist for the initialization to work.
        ncfile = self.tmppath / 'a.nc'
        with netCDF4.Dataset(ncfile, mode='w'):
            pass

        new = [
            '',
            str(ncfile),
            '/tmp/path/to/file.xml',
            '/tmp/path/to/file.csv',
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.generate_socat_xml()

    @patch('xco2qc.socat.SocatWriter.run')
    def test_socat_bad_xml_filename(self, mock_run):
        """
        SCENARIO:  Run the SOCAT XML utility with a bad XML filename argument.

        EXPECTED RESULT:  RuntimeError
        """
        new = [
            '',
            '/tmp/path/to/reduced/netcdf/file.nc',
            '/tmp/path/to/file.nc',
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            with self.assertRaises(RuntimeError):
                commandline.generate_socat_xml()

    @patch('xco2qc.socat.SocatWriter.run')
    def test_socat_bad_csv_filename(self, mock_run):
        """
        SCENARIO:  Run the SOCAT XML utility with a bad argument for the CSV
        output file.

        EXPECTED RESULT:  RuntimeError
        """
        new = [
            '',
            '/tmp/path/to/reduced/netcdf/file.nc',
            '/tmp/path/to/output.xml',
            '/tmp/path/to/output.cvs',
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            with self.assertRaises(RuntimeError):
                commandline.generate_socat_xml()

    @unittest.skip('no longer applicable, it will always error out here')
    @patch('xco2qc.mbl.CompareMBL.run')
    def test_mbl_compare(self, mock_run):
        """
        SCENARIO:  Test the entry point for comparing APOFF with MBL.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            '/tmp/path/to/mapco2/merge.nc',
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.compare_with_mbl()

    @patch('xco2qc.merge.XCO2Merge.run')
    def test_merge_file_missing_nc_suffix(self, mock_run):
        """
        SCENARIO:  The merge netCDF file is named but does not have an ".nc"
        suffix.

        EXPECTED RESULT:  Error out.  Otherwise the result might be mistaken
        for a directory.  The user should be very clear on the fact that they
        need to specify a file.
        """
        new = [
            '',
            self.reduced_dir,
            self.merge_dir,
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            with self.assertRaises(RuntimeError):
                commandline.merge()

    @patch('xco2qc.trim_netcdf.TrimXCO2netCDF.run')
    def test_trimming_smoke(self, mock_run):
        """
        SCENARIO:  Run the trimming command line utility.

        EXPECTED RESULT:  Do not error out.
        """
        new = [
            '',
            self.reduced_dir, self.trimmed_dir,
            '--start=2001-01-01',
            '--stop=2002-01-01',
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.trim()


@patch('xco2qc.commandline.QCChecker.run')
class Test_XCO2_QC_CommandLine(test_core.TestSuite):

    def test__qc_xco2(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__spike_detection_turned_on(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with spike detection
        turned on.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--spike-detection=yes',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__spike_detection_turned_off(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with spike detection
        turned off.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--spike-detection=no',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__qc_xco2__max_rh_temp_std(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for max_rh_temp_std.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--max-rh-temp-std=3',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__qc_xco2__max_rh_std(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for max_rh_std.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--max-rh-std=3',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__spon_spoff_diff_range(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for span-diff-range.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--span-diff-range',
            '3', '4'
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__spon_spoff_diff_range_reversed(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for span-diff-range-{lower,higher}, but they are not in
        order.

        EXPECTED RESULT:  RuntimeError
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--span-diff-range',
            '4', '3'
        ]
        with patch.object(sys, 'argv', new=new):
            with self.assertRaises(RuntimeError):
                commandline.qc_xco2()

    def test__equil_diff_range(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for equil-diff-range.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--equil-diff-range',
            '3', '4'
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__equil_diff_range_reversed(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for equil-diff-range-{lower,higher}, but they are not in
        order.

        EXPECTED RESULT:  RuntimeError
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--equil-diff-range',
            '4', '3'
        ]
        with patch.object(sys, 'argv', new=new):
            with self.assertRaises(RuntimeError):
                commandline.qc_xco2()

    def test__air_diff_range(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for air-diff-range.

        EXPECTED RESULT:  It should not error out.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--air-diff-range',
            '3', '4'
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__ppm_span(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for ppm-{below,above}_span, but they are not in order.

        EXPECTED RESULT:  RuntimeError
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--ppm-span-cal-range',
            '4', '-3'
        ]
        with patch.object(sys, 'argv', new=new):
            with self.assertRaises(RuntimeError):
                commandline.qc_xco2()

    def test__ppm_below_zero(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for ppm-{below,above}_zero, but they are not both positive.

        EXPECTED RESULT:  RuntimeError
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--ppm-zero-range',
            '-4', '3'
        ]
        with patch.object(sys, 'argv', new=new):
            with self.assertRaises(RuntimeError):
                commandline.qc_xco2()

    def test__air_diff_range_reversed(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for air-diff-range-{lower,higher}, but they are not in order.

        EXPECTED RESULT:  RuntimeError
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--air-diff-range',
            '4', '3'
        ]
        with patch.object(sys, 'argv', new=new):
            with self.assertRaises(RuntimeError):
                commandline.qc_xco2()

    def test__max_air_xco2_std(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for max-air-xco2-std.

        EXPECTED RESULT:  There is no error.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--max-air-xco2-std=4',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__max_equil_xco2_std(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for max-equil-xco2-std.

        EXPECTED RESULT:  There is no error.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--max-equil-xco2-std=4',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__max_pressoff_diff(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for max-presoff-diff

        EXPECTED RESULT:  There is no error.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--max-pressoff-diff=4',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__xco2_trend_std(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for xco2-trend-std

        EXPECTED RESULT:  There is no error.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--xco2-trend-std=4',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()

    def test__num_points_eachside(self, mock_run):
        """
        SCENARIO:  Run the command line script for XCO2 QC with argument
        supplied for num-points-eachside

        EXPECTED RESULT:  There is no error.
        """
        new = [
            '',
            self.trimmed_dir,
            '--verbosity=critical',
            '--num-points-eachside=4',
        ]
        with patch.object(sys, 'argv', new=new):
            commandline.qc_xco2()
