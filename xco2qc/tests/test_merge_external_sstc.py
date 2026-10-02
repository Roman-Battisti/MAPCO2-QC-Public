"""
This test suite looks at cases where there was external SSS and SST, and how
that affects the merge process.
"""

# standard library imports
import importlib.resources as ir
import io

# 3rd party library imports
import numpy as np
import xarray as xr

# local imports
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.external_met import ImportExternalMET
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from tests import test_core


class TestSuite(test_core.TestSuite):

    def test_smoke(self):
        """
        SCENARIO:  An NH file is processed thru the merge step.  There is
        externally provided met data.

        EXPECTED RESULT:  The external met data is used for the merge SSS and
        SST data.
        """

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(
            'tests.data.mapco2.nh'
            ).joinpath(
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path
            ) as p:
                p.run()

            text = (
                "time,salinity,temperature\n"
                "2013-11-05 18:30:00,33,22\n"
                "2013-11-05 19:00:00,34,23\n"
                "2013-11-05 19:30:00,33,22\n"
                "2013-11-05 20:00:00,34,23\n"
            )
            inputfile = io.StringIO(text)
            with ImportExternalMET(inputfile, self.raw_path) as p:
                p.run()

            with XCO2Reduce(
                self.raw_path,
                self.reduced_path,
            ) as p:
                p.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(
                self.reduced_path, calculate_post_xco2=True
            ) as p:
                p.run()

            with QCChecker(
                self.reduced_path,
                initial_span_cal=0,
                num_points_eachside=1
            ) as p:
                p.run()

        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with xr.open_dataset(ncfile) as ds:

            actual = ds['SSS'][:]
            expected = np.array([34, 33, 34, 34])
            np.testing.assert_allclose(actual, expected)

            actual = ds['SST'][:]
            expected = np.array([23, 22, 23, 23])
            np.testing.assert_allclose(actual, expected)
