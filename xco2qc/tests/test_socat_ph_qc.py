"""
Test suite for converting PH QC bitmasks into SOCAT QC.
"""

# standard library imports
import importlib.resources as ir

# 3rd party library imports
import netCDF4
import numpy as np

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.pre_xco2_processing import PreXCO2Calc
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
        spanconc=0, num_points_eachside=1
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p0:
                p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p2:
                p2.run()

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
            ) as p4:
                p4.run()

            with XCO2Merge(self.trimmed_path, self.merge_ncfile) as m:
                m.run()

    def test_smoke(self):
        """
        SCENARIO:  The socat quality flags should be written back to the
        netCDF file.  This deployment has SAMI data.

        EXPECTED RESULT:  The sami socat qc variable is verified.
        """
        self._processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
        )

        with SocatQC(ncfile=self.merge_ncfile) as p:
            p.run()

        with netCDF4.Dataset(self.merge_ncfile) as nc:

            actual = nc['pH_sw'].ancillary_variables
            expected = f"{'pH_sw_qc'} {'pH_sw_socat_qc'}"
            self.assertEqual(actual, expected)

        # verify that the quality flags agree with each other
        with netCDF4.Dataset(self.merge_ncfile) as nc:

            varname = 'pH_sw_socat_qc'
            actual_socat_qc = nc[varname][:]
            varname = 'pH_sw_qc'
            actual_mask_qc = nc[varname][:]

            expected_mask_qc = np.full(
                (4,),
                core.quality.MISSING_DATA | core.quality.OUT_OF_RANGE
            )
            np.testing.assert_allclose(actual_mask_qc, expected_mask_qc)

            # missing and out of range equates to bad, it's a case of all zeros
            expected_socat_qc = np.full((4,), core.quality.SOCAT_BAD)
            np.testing.assert_allclose(actual_socat_qc, expected_socat_qc)
