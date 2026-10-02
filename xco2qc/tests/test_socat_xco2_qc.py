"""
Test suite for converting QC bitmasks into SOCAT QC.
"""

# standard library imports
import importlib.resources as ir
import unittest

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from xco2qc.trim_netcdf import TrimXCO2netCDF
from xco2qc.socat_qc import SocatQC
import tests.test_core


class TestSuite(tests.test_core.TestSuite):

    def _processing_chain(
        self, module, filename,
        spanconc=0, num_points_eachside=1,
        span_diff_range_lower=1.5,
        sbe16_mapping=False
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p0:
                p0.run()

            with XCO2Reduce(
                self.raw_path, self.reduced_path, sbe16_mapping=sbe16_mapping
            ) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p2:
                p2.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with TrimXCO2netCDF(self.reduced_path, self.trimmed_path) as p:
                p.run()

            with ManualRegressionQC(self.trimmed_path) as p:
                p.run()

            with PostXCO2Calc(self.trimmed_path) as p3:
                p3.run()

            with QCChecker(
                self.trimmed_path,
                initial_span_cal=spanconc,
                num_points_eachside=num_points_eachside,
                span_diff_range_lower=span_diff_range_lower
            ) as p4:
                p4.run()

            with XCO2Merge(self.trimmed_path, self.merge_ncfile) as m:
                m.run()

    def test_netcdf_socat_flags(self):
        """
        SCENARIO:  The socat quality flags should be written back to the
        netCDF file.

        EXPECTED RESULT:  The new variables are verified.  The
        ancillary_variables attributes are updated.
        """
        self._processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
        )

        # Alter the netCDF file so that we get all four socat flags
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            qcvar = nc['xCO2_air_qc']

            qcdata = qcvar[:]

            qcdata[2] = core.quality.MISSING_DATA
            qcdata[3] = core.quality.MANUALLY_FLAGGED

            qcvar[:] = qcdata

        with SocatQC(ncfile=self.merge_ncfile) as p:
            p.run()

        # Verify that the attributes are updated.
        with netCDF4.Dataset(self.merge_ncfile) as nc:

            varname = 'xCO2_air'
            actual = nc[varname].ancillary_variables
            expected = 'xCO2_air_qc xco2_air_socat_qc'
            self.assertEqual(actual, expected)

            varname = 'xCO2_sw'
            actual = nc[varname].ancillary_variables
            expected = 'xCO2_sw_qc xco2_sw_socat_qc'
            self.assertEqual(actual, expected)

        # verify that the quality flags agree with each other
        with netCDF4.Dataset(self.merge_ncfile) as nc:

            varname = 'xco2_air_socat_qc'
            actual_socat_qc = nc[varname][:]
            varname = 'xCO2_air_qc'
            actual_mask_qc = nc[varname][:]

            expected_mask_qc = np.array([
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.MISSING_DATA,
                core.quality.MANUALLY_FLAGGED,
            ])
            np.testing.assert_allclose(actual_mask_qc, expected_mask_qc)

            expected_socat_qc = np.array([
                core.quality.SOCAT_GOOD,
                core.quality.SOCAT_GOOD,
                core.quality.SOCAT_MISSING,
                core.quality.SOCAT_BAD,
            ])
            np.testing.assert_allclose(actual_socat_qc, expected_socat_qc)

    @unittest.skip('skip until salinity compensated o2 question is resolved')
    def test_laparguera_bad_sstc(self):
        """
        SCENARIO:  There is missing SSS.

        EXPECTED RESULT:  The socat quality for o2 should be BAD.
        """
        self._processing_chain(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt'
        )

        # put the BAD_SSTC flag into the merge file.
        with netCDF4.Dataset(self.merge_ncfile) as nc:
            nc['dissolved_oxygen_qc'][:] = np.array([
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.BAD_SSTC,
                core.quality.GOOD,
            ])

        with SocatQC(ncfile=self.merge_ncfile) as p:
            p.run()

        with xr.open_dataset(self.merge_ncfile) as ds:
            qc = ds['dissolved_oxygen_qc'][:]

        expected = np.array([
            core.quality.SOCAT_GOOD,
            core.quality.SOCAT_GOOD,
            core.quality.SOCAT_BAD,
            core.quality.SOCAT_GOOD,
        ])
        np.testing.assert_allclose(qc, expected)

    def test_laparguera_chl(self):
        """
        SCENARIO:  CHL is in the data stream.

        EXPECTED RESULT:  chl_socat_qc, ntu_socat_qc, dissolved_oxygen_socat_qc
        are in the merge file.
        """
        self._processing_chain(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        with SocatQC(ncfile=self.merge_ncfile) as p:
            p.run()

        with xr.load_dataset(self.merge_ncfile) as ds:
            chl_socat_qc = ds['chl_nighttime_socat_qc'][:]
            ntu_qc = ds['ntu_socat_qc'][:]
            doxy_qc = ds['dissolved_oxygen_socat_qc'][:]

        expected = np.array([
            core.quality.SOCAT_MISSING,
            core.quality.SOCAT_GOOD,
            core.quality.SOCAT_GOOD,
            core.quality.SOCAT_MISSING,
        ])
        np.testing.assert_allclose(chl_socat_qc, expected)

        expected = np.full((4,), core.quality.SOCAT_GOOD, dtype=np.uint32)
        np.testing.assert_allclose(ntu_qc, expected)
        np.testing.assert_allclose(doxy_qc, expected)

    def test_cheeca(self):
        """
        SCENARIO:  The bitmask quality for xco2_wet_qc at 21:17 is good.

        EXPECTED RESULT:  The socat quality should be good as well.
        """
        self._processing_chain(
            'tests.data.mapco2.cheeca',
            '0111_dp08_20190319_20200105.txt',
            spanconc=505,
            span_diff_range_lower=0
        )

        with SocatQC(ncfile=self.merge_ncfile) as p:
            p.run()

        with xr.load_dataset(self.merge_ncfile) as ds:
            qc = ds['xco2_sw_socat_qc'][:]

        expected = np.full((11,), core.quality.SOCAT_GOOD, dtype=np.uint32)
        np.testing.assert_allclose(qc, expected)

    @unittest.skip('this test is no longer appropriate')
    def test_bad_gps_data(self):
        """
        SCENARIO:  The first GPS reading was bad.

        EXPECTED RESULT:  The bad GPS results in a questionable QC value in
        the CSV file.
        """
        self._processing_chain(
            'tests.data.mapco2.alawai',
            'dp2_0110_20091108_20101028.50.txt',
            spanconc=490,
        )

        # Write the bad QC value into the merge file before the SOCAT writer
        # gets hold of it.
        qc = np.full(50, core.quality.GOOD, dtype=np.uint32)
        qc[0] = core.quality.BAD_GPS
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            for xco2qc_var in [
                'xco2_sw_wet_qc', 'xCO2_sw_qc',
                'xco2_air_wet_qc', 'xCO2_air_qc',
            ]:
                nc[xco2qc_var][:] = qc

        with SocatQC(ncfile=self.merge_ncfile) as p:
            p.run()

        with netCDF4.Dataset(self.merge_ncfile) as nc:
            qc = nc['xco2_sw_socat_qc'][:]

        expected = np.full((50,), core.quality.SOCAT_GOOD, dtype=np.uint32)
        expected[0] = core.quality.SOCAT_QUESTIONABLE
        np.testing.assert_allclose(qc, expected)

    def test_transform_to_socat_quality(self):
        """
        SCENARIO:  We are given a bitmask QC array.

        EXPECTED RESULT:  The array is accurately transformed to SOCAT quality.
        """
        qc = pd.Series([
            core.quality.GOOD,
            core.quality.MISSING_DATA,
            core.quality.MANUALLY_FLAGGED,
            core.quality.OUT_OF_RANGE,
            core.quality.OUT_OF_RANGE | core.quality.TREND_STDDEV_OUT_OF_RANGE,
        ])

        with SocatQC(ncfile=self.merge_ncfile) as q:
            socat_qc = q.transform_to_socat_quality(qc)

        expected = pd.Series([
            core.quality.SOCAT_GOOD,
            core.quality.SOCAT_MISSING,
            core.quality.SOCAT_BAD,
            core.quality.SOCAT_BAD,
            core.quality.SOCAT_BAD,
        ]).astype(np.uint32)

        pd.testing.assert_series_equal(socat_qc, expected)
