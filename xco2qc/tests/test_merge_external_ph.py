"""
Test suite for the process of merging external pH into the xco2 merge netCDF
file.
"""

# standard library imports
import importlib.resources as ir

# 3rd party library imports
import netCDF4
import numpy as np
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.external_sami import ImportExternalSAMI
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
        SCENARIO:  We perform a merge where external SAMI data was present.

        EXPECTED RESULT:  pH is verified against the external data
        """
        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(
            'tests.data.mapco2.whots'
            ).joinpath(
            'dp12_example_data.txt'
        )) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with ir.as_file(ir.files(
                'tests.data.mapco2.whots'
                ).joinpath(
                'sami_P0017_dp12_20180922_20190922_out.txt'
            )) as external_sami_inputfile:
                with ImportExternalSAMI(
                    external_sami_inputfile,
                    self.raw_path
                ) as p0:
                    p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p2:
                p2.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(self.reduced_path) as p3:
                p3.run()

            with QCChecker(
                self.reduced_path,
                initial_span_cal=490,
                num_points_eachside=1
            ) as p4:
                p4.run()

            with XCO2Merge(self.reduced_path, self.merge_ncfile) as mp:
                mp.run()

        with xr.open_dataset(self.merge_ncfile) as ds:

            actual = ds['pH_sw'][:]
            expected = np.array([8.0, 8.1, 8.2, 8.3])
            np.testing.assert_allclose(actual, expected)

            actual = ds['pH_sw_qc'][:]
            expected = np.array([
                core.quality.GOOD, core.quality.GOOD,
                core.quality.GOOD, core.quality.GOOD
            ])
            np.testing.assert_array_equal(actual, expected)

    def test_bad_gps(self):
        """
        SCENARIO:  There is a bad GPS point in the mapco2 cycle data.

        EXPECTED RESULT:  The ph QC shoud NOT reflect the bad gps point.
        """
        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(
            'tests.data.mapco2.whots'
            ).joinpath(
            'dp12_example_data.txt'
        )) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with ir.as_file(ir.files(
                'tests.data.mapco2.whots'
                ).joinpath(
                'sami_P0017_dp12_20180922_20190922_out.txt'
            )) as external_sami_inputfile:
                with ImportExternalSAMI(
                    external_sami_inputfile,
                    self.raw_path
                ) as p0:
                    p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p2:
                p2.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(self.reduced_path) as p3:
                p3.run()

            # inject the bad gps qc data here, it's where the manual QC is done
            ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
            data = np.array([
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.MANUALLY_FLAGGED,
                core.quality.GOOD,
            ])
            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                nc['latitude_qc'][:] = data
                nc['longitude_qc'][:] = data

            # resume regular processing
            with QCChecker(
                self.reduced_path,
                initial_span_cal=490,
                num_points_eachside=1
            ) as p4:
                p4.run()

            with XCO2Merge(self.reduced_path, self.merge_ncfile) as mp:
                mp.run()

        with xr.open_dataset(self.merge_ncfile) as ds:

            actual = ds['pH_sw_qc'][:]
            expected = np.array([
                core.quality.GOOD, core.quality.GOOD,
                core.quality.GOOD, core.quality.GOOD
            ])
            np.testing.assert_array_equal(actual, expected)
