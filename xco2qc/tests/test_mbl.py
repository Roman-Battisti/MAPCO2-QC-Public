"""
Test the MBL and licor pressure corrections.
"""

# standard library imports
import gzip
import importlib.resources as ir
import shutil
from unittest.mock import patch
import unittest

# 3rd party library imports
import netCDF4
import requests
import xarray as xr

# local imports
import xco2qc.core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.external_historical import ImportHistorical
from xco2qc.trim_netcdf import TrimXCO2netCDF
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.mbl import CompareMBL
from xco2qc.merge import XCO2Merge
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.qc import QCChecker
from xco2qc.adjustments import XCO2Adjustments
from xco2qc.socat_qc import SocatQC
from tests import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(
        self, module, filename, initial_span_cal=490, num_points_eachside=1,
        historical_file=None
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p0:
                p0.run()

            if historical_file is not None:
                try:
                    with xr.open_dataset(historical_file):
                        pass
                except (OSError, ValueError):
                    # importing a text file
                    with ImportHistorical(historical_file, self.raw_path) as p:
                        p.run()
                else:
                    # importing a PMEL ERDDAP file
                    dst = self.raw_path / xco2qc.core.HISTORICAL_NCFILE
                    shutil.copyfile(historical_file, dst)

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()
            
            with TrimXCO2netCDF(
                self.reduced_path, self.trimmed_path,
            ) as p:
                p.run()

            with PreXCO2Calc(self.trimmed_path) as p2:
                p2.run()

            with CalcO2Concentration(self.trimmed_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.trimmed_path) as p:
                p.run()

            with ManualRegressionQC(self.trimmed_path) as p:
                p.run()

            with PostXCO2Calc(self.trimmed_path) as p2:
                p2.run()

            with QCChecker(
                self.trimmed_path,
                initial_span_cal=initial_span_cal,
                num_points_eachside=num_points_eachside
            ) as p3:
                p3.run()

            with XCO2Merge(self.trimmed_path, self.merge_ncfile) as p:
                p.run()

            with SocatQC(ncfile=self.merge_ncfile) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Read in the MBL test file, convert to netCDF, compare it
        against APOFF

        EXPECTED RESULT:  No errors.
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_ncfile
            )

        with CompareMBL(
            src_dir=self.trimmed_dir, merge_ncfile=self.merge_ncfile, historical_ncfile=historical_ncfile
        ) as p:
            p.run()

        with XCO2Adjustments(self.reduced_path, self.merge_ncfile) as p:
            p.run()

    def test_no_historical_data(self):
        """
        SCENARIO:  Read in the MBL test file, convert to netCDF, compare it
        against APOFF

        EXPECTED RESULT:  No errors.
        """
        self._processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        with CompareMBL(src_dir=self.trimmed_dir, merge_ncfile=self.merge_ncfile) as p:
            p.run()

    def test_historical_pmel(self):
        """
        SCENARIO:  Read in the MBL test file, convert to netCDF, compare it
        against APOFF.  Include a historical file.

        EXPECTED RESULT:  No errors.
        """

        with ir.as_file(ir.files(
            'tests.data.netcdf'
            ).joinpath(
            'nh.nc'
        )) as historical_file:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

        historical_ncfile = self.reduced_path / xco2qc.core.HISTORICAL_NCFILE
        with CompareMBL(
            src_dir=self.trimmed_dir, merge_ncfile=self.merge_ncfile, historical_ncfile=historical_ncfile
        ) as p:
            p.run()

        with XCO2Adjustments(self.reduced_path, self.merge_ncfile) as p:
            p.run()

    def test_historical_pmel_text(self):
        """
        SCENARIO:  Read in the MBL test file, convert to netCDF, compare it
        against APOFF.  Include a historical file that does have xco2_air.

        EXPECTED RESULT:  No errors.
        """

        with ir.as_file(ir.files(
            'tests.data.external.nh'
            ).joinpath(
            'historical.4.txt'
        )) as historical_file:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

        historical_ncfile = self.reduced_path / xco2qc.core.HISTORICAL_NCFILE
        with CompareMBL(
            src_dir=self.trimmed_dir, merge_ncfile=self.merge_ncfile, historical_ncfile=historical_ncfile
        ) as p:
            p.run()

        with XCO2Adjustments(self.reduced_path, self.merge_ncfile) as p:
            p.run()

    @unittest.skip('no longer appropriate')
    def test_historical_no_xco2_air(self):
        """
        SCENARIO:  Read in the MBL test file, convert to netCDF, compare it
        against APOFF.  Include a historical file that does not have xco2_air.

        EXPECTED RESULT:  No errors.
        """

        with ir.as_file(ir.files(
            'tests.data.external.nh'
            ).joinpath(
            'historical.4.no_xco2_air.txt'
        )) as historical_file:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

        historical_ncfile = self.reduced_path / xco2qc.core.HISTORICAL_NCFILE
        with CompareMBL(
            merge_ncfile=self.merge_ncfile, historical_ncfile=historical_ncfile
        ) as p:
            p.run()

        with XCO2Adjustments(self.reduced_path, self.merge_ncfile) as p:
            p.run()

    def test_merge_file_time_range_out_of_mbl_time_range(self):
        """
        SCENARIO:  The merge file time range is not contained by the MBL file
        time range.  This means we cannot align the MBL data.

        EXPECTED RESULT:  A RuntimeError is issued.
        """

        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_file:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

        # manually adjust the time data in the merge file, a litle over 6 years
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            time = nc[xco2qc.core.TIME][:]
            # time += 86400 * 365 * 100
            # time += 86400 * 365 * 100 - 2959440420 - 3600
            time += 194155980
            nc[xco2qc.core.TIME][:] = time

        with CompareMBL(
            src_dir=self.trimmed_dir, merge_ncfile=self.merge_ncfile, historical_ncfile=historical_file
        ) as p:
            p.run()

        with XCO2Adjustments(self.reduced_path, self.merge_ncfile) as p:
            p.run()

    def test_time_stamp(self):
        """
        SCENARIO:  After the MBL comparison has been run, the timestamp of the
        MBL data should be available.

        EXPECTED RESULT:  The timestamp should not be None.
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_ncfile
            )

        with CompareMBL(
            src_dir=self.trimmed_dir, merge_ncfile=self.merge_ncfile, historical_ncfile=historical_ncfile
        ) as p:
            p.run()

        with XCO2Adjustments(self.reduced_path, self.merge_ncfile) as p:
            p.run()

        timestamp = xco2qc.core.data.mbl.get_timestamp()
        self.assertTrue(timestamp is not None)

    def test_remote_retrieval(self):
        """
        SCENARIO:  Specify to retrieve the remote MBL data.

        EXPECTED RESULT:  No errors
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_file:
            with ir.as_file(ir.files(
                'xco2qc.core.data.mbl.data'
                ).joinpath(
                'Latest_MBL.txt.gz'
            )) as path:
                with gzip.open(path, mode='rt') as f:
                    text = f.read()

            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

        with patch('xco2qc.core.data.mbl.requests.get') as mock_get:

            mock_get.return_value.status_code = 200
            mock_get.return_value.text = text
            mock_get.return_value.content = text.encode('utf-8')

            with CompareMBL(
                src_dir=self.trimmed_dir,
                merge_ncfile=self.merge_ncfile,
                historical_ncfile=historical_file,
                retrieve_remote=True
            ) as p:
                p.run()

            with XCO2Adjustments(self.reduced_path, self.merge_ncfile) as p:
                p.run()

    def test_remote_retrieval_404(self):
        """
        SCENARIO:  Specify to retrieve the remote MBL data, but the request
        comes back with a 404

        EXPECTED RESULT:  No errors
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_ncfile
            )

        with patch('xco2qc.core.data.mbl.requests.get') as mock_get:

            mock_get.return_value.status_code = 404
            mock_get.return_value.raise_for_status.side_effect = requests.HTTPError('404')  # noqa : E501

            with self.assertRaises(requests.HTTPError):
                with CompareMBL(
                    src_dir=self.trimmed_dir,
                    merge_ncfile=self.merge_ncfile,
                    historical_ncfile=historical_ncfile,
                    retrieve_remote=True
                ) as p:
                    p.run()

                with XCO2Adjustments(
                    self.reduced_path, self.merge_ncfile
                ) as p:
                    p.run()


class TestSuite2(test_core.TestSuite):

    def _processing_chain(
        self, module, filename, initial_span_cal=490, num_points_eachside=1,
        historical_file=None
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p0:
                p0.run()

            if historical_file is not None:
                try:
                    with xr.open_dataset(historical_file):
                        pass
                except (OSError, ValueError):
                    # importing a text file
                    with ImportHistorical(historical_file, self.raw_path) as p:
                        p.run()
                else:
                    # importing a PMEL ERDDAP file
                    dst = self.raw_path / xco2qc.core.HISTORICAL_NCFILE
                    shutil.copyfile(historical_file, dst)

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()
            
            with TrimXCO2netCDF(
                self.reduced_path, self.trimmed_path,
            ) as p:
                p.run()

            with PreXCO2Calc(self.trimmed_path) as p2:
                p2.run()

            with CalcO2Concentration(self.trimmed_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.trimmed_path) as p:
                p.run()

            with ManualRegressionQC(self.trimmed_path) as p:
                p.run()

            with PostXCO2Calc(self.trimmed_path, calculate_post_xco2=False) as p2:
                p2.run()

            with QCChecker(
                self.trimmed_path,
                initial_span_cal=initial_span_cal,
                num_points_eachside=num_points_eachside
            ) as p3:
                p3.run()

            with XCO2Merge(self.trimmed_path, self.merge_ncfile) as p:
                p.run()

            with SocatQC(ncfile=self.merge_ncfile) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Read in the MBL test file, convert to netCDF, compare it
        against APOFF when no post processing has occurred.

        EXPECTED RESULT:  No errors.
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_ncfile
            )

        with CompareMBL(
            src_dir=self.trimmed_dir, merge_ncfile=self.merge_ncfile, historical_ncfile=historical_ncfile
        ) as p:
            p.run()

        with XCO2Adjustments(self.reduced_path, self.merge_ncfile) as p:
            p.run()