# standard library imports
import datetime as dt
import importlib.resources as ir
import shutil

# 3rd party library imports
import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from xco2qc.metadata_conventions import MetadataWriter
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.socat_qc import SocatQC
from xco2qc.final_qc import XCO2FinalQC
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(
        self, module, filename,
        verbosity='CRITICAL',
        num_points_eachside=1,
        equil_diff_range_lower=8,
        licor_version='820 v1'
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path, verbosity=verbosity
            ) as p0:
                p0.run()

            with XCO2Reduce(
                self.raw_path,
                self.reduced_path,
                verbosity=verbosity
            ) as p1:
                p1.run()

            with PreXCO2Calc(
                self.reduced_path, verbosity=verbosity
            ) as p2:
                p2.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(
                self.reduced_path,
                verbosity=verbosity,
                licor_version=licor_version
            ) as p3:
                p3.run()

            with QCChecker(
                self.reduced_path, verbosity=verbosity,
                num_points_eachside=num_points_eachside,
                equil_diff_range_lower=equil_diff_range_lower
            ) as p4:
                p4.run()

            with XCO2Merge(
                self.reduced_path, self.merge_ncfile,
                verbosity=verbosity
            ) as p:
                p.run()

            with SocatQC(ncfile=self.merge_ncfile) as p:
                p.run()

            with MetadataWriter(self.merge_ncfile) as m:
                m.run()

    def test_qflog_xCO2_air_followed_by_SSS(self):
        """
        SCENARIO:  Select a set of vertices, all points within that path
        are intended to be set to bad.  Do the same for SSS, different region.

        EXPECTED RESULT:  the qflog shows both the xCO2_air and SSS user
        comments.
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            licor_version='820 v2',
            equil_diff_range_lower=7
        )

        # construct the mouse-click data
        x = mdates.date2num([
            dt.datetime(2018, 9, x) for x in [26, 27, 27, 26, 26]
        ])
        y = [590, 590, 675, 675, 590]
        verts = list(zip(x, y))

        # run the final qc and verify that those qc values have changed
        with XCO2FinalQC(
            self.merge_ncfile, 'xCO2_sw', verts, core.quality.SOCAT_BAD,
            user_comment='bad', qflog=self.socat_qf_log
        ) as p:
            p.run()

        # verify the temporary QF log
        df = pd.read_csv(
            self.socat_qf_log,
            index_col='Date/Time',
            parse_dates=['Date/Time']
        )

        nrows = 8
        data = {
            'Parameter': ['xCO2_sw'] * nrows,
            'Reason': ['bad'] * nrows
        }
        index = pd.date_range(
            '2018-09-26 00:17:00', periods=8, freq='3h', name='Date/Time'
        )
        expected = pd.DataFrame(data=data, index=index)
        expected.index.freq = None
        pd.testing.assert_frame_equal(df, expected)

        # construct the mouse-click data for a different region
        x = mdates.date2num([
            dt.datetime(2018, 9, 26, h) for h in [0, 12, 12, 0, 0]
        ])
        y = [32, 32, 35, 35, 32]
        verts = list(zip(x, y))

        # run the final qc and verify that those qc values have changed
        with XCO2FinalQC(
            self.merge_ncfile, 'SSS', verts, core.quality.SOCAT_BAD,
            user_comment='even worse', qflog=self.socat_qf_log
        ) as p:
            p.run()

        # verify the temporary QF log
        df = pd.read_csv(
            self.socat_qf_log,
            index_col='Date/Time',
            parse_dates=['Date/Time']
        )

        data = {
            'Parameter': [
                'xCO2_sw', 'SSS', 'xCO2_sw', 'SSS',
                'xCO2_sw', 'SSS', 'xCO2_sw', 'SSS',
                'xCO2_sw', 'xCO2_sw', 'xCO2_sw', 'xCO2_sw',
            ],
            'Reason': [
                'bad', 'even worse', 'bad', 'even worse',
                'bad', 'even worse', 'bad', 'even worse',
                'bad', 'bad', 'bad', 'bad',
            ]
        }
        index_data = [
            '2018-09-26 00:17:00', '2018-09-26 00:17:00',
            '2018-09-26 03:17:00', '2018-09-26 03:17:00',
            '2018-09-26 06:17:00', '2018-09-26 06:17:00',
            '2018-09-26 09:17:00', '2018-09-26 09:17:00',
            '2018-09-26 12:17:00', '2018-09-26 15:17:00',
            '2018-09-26 18:17:00', '2018-09-26 21:17:00',
        ]
        index = pd.DatetimeIndex(index_data, name='Date/Time')
        expected = pd.DataFrame(data=data, index=index)

        pd.testing.assert_frame_equal(df, expected)

    def test_xco2_sw_wet(self):
        """
        SCENARIO:  Select a set of vertices, all four points within that path
        are intended to be set to bad.

        EXPECTED RESULT:  the sw and associated qc vars are set to bad.
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            licor_version='820 v2',
            equil_diff_range_lower=7
        )

        # construct the mouse-click data
        x = mdates.date2num([
            dt.datetime(2018, 9, x) for x in [26, 27, 27, 26, 26]
        ])
        y = [590, 590, 675, 675, 590]
        verts = list(zip(x, y))

        # We expect that these indices will be set to BAD
        idx = np.array([31, 32, 33, 34, 35, 36, 37, 38])

        # run the final qc and verify that those qc values have changed
        with XCO2FinalQC(
            self.merge_ncfile, 'xCO2_sw', verts, core.quality.SOCAT_BAD,
            user_comment='bad', qflog=self.socat_qf_log
        ) as p:
            p.run()

        # verify the temporary QF log
        df = pd.read_csv(
            self.socat_qf_log,
            index_col='Date/Time',
            parse_dates=['Date/Time']
        )

        nrows = 8
        data = {
            'Parameter': ['xCO2_sw'] * nrows,
            'Reason': ['bad'] * nrows
        }
        index = pd.date_range(
            '2018-09-26 00:17:00', periods=8, freq='3h', name='Date/Time'
        )
        expected = pd.DataFrame(data=data, index=index)
        expected.index.freq = None
        pd.testing.assert_frame_equal(df, expected)

        with xr.open_dataset(self.merge_ncfile) as ds:
            df = ds.to_dataframe()
            xco2_socat_qc = df['xco2_sw_socat_qc'].astype(np.uint32)
            pCO2_qc = df['pCO2_sw_qc'].astype(np.uint32)
            fCO2_qc = df['fCO2_sw_qc'].astype(np.uint32)

        expected = np.full((8,), core.quality.SOCAT_BAD)
        np.testing.assert_array_equal(xco2_socat_qc[idx], expected)

        # the pCO2 qc data has changed, but it is not socat qc
        expected = np.full((8,), core.quality.MANUALLY_FLAGGED_XCO2)
        np.testing.assert_array_equal(pCO2_qc.iloc[idx], expected)
        np.testing.assert_array_equal(fCO2_qc.iloc[idx], expected)

        # construct the mouse-click data for just half of the previous range
        x = mdates.date2num([
            dt.datetime(2018, 9, 26, h) for h in [0, 12, 12, 0, 0]
        ])
        y = [590, 590, 675, 675, 590]
        verts = list(zip(x, y))

        # run the final qc and verify that those qc values have changed
        with XCO2FinalQC(
            self.merge_ncfile, 'xCO2_sw', verts, core.quality.SOCAT_GOOD,
            user_comment='good', qflog=self.socat_qf_log
        ) as p:
            p.run()

        # verify the temporary QF log
        df = pd.read_csv(
            self.socat_qf_log,
            index_col='Date/Time',
            parse_dates=['Date/Time']
        )

        nrows = 8
        data = {
            'Parameter': ['xCO2_sw'] * nrows,
            'Reason': [
                'good', 'good', 'good', 'good',
                'bad', 'bad', 'bad', 'bad',
            ]
        }
        index = pd.date_range(
            '2018-09-26 00:17:00', periods=8, freq='3h', name='Date/Time'
        )
        expected = pd.DataFrame(data=data, index=index)
        expected.index.freq = None

        pd.testing.assert_frame_equal(df, expected)

        with xr.open_dataset(self.merge_ncfile) as ds:
            df = ds.to_dataframe()
            xco2_socat_qc = df['xco2_sw_socat_qc'].astype(np.uint32)
            pCO2_qc = df['pCO2_sw_qc'].astype(np.uint32)
            fCO2_qc = df['fCO2_sw_qc'].astype(np.uint32)

        expected = np.full((8,), core.quality.SOCAT_GOOD)
        expected[4:] = core.quality.SOCAT_BAD
        np.testing.assert_array_equal(xco2_socat_qc.iloc[idx], expected)

        # pCO2 should have changed back, half of them, anyway
        expected = np.full((8,), core.quality.MANUALLY_FLAGGED_XCO2)
        expected[:4] = core.quality.GOOD
        np.testing.assert_array_equal(pCO2_qc.iloc[idx], expected)
        np.testing.assert_array_equal(fCO2_qc.iloc[idx], expected)

    def test_xco2_air_wet(self):
        """
        SCENARIO:  Select a set of vertices, all four points within that path
        are intended to be set to bad.

        EXPECTED RESULT:  the air and associated qc vars are set to bad.
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            licor_version='820 v2',
            equil_diff_range_lower=7
        )

        # construct the mouse-click data
        x = mdates.date2num([
            dt.datetime(2018, 9, x) for x in [26, 27, 27, 26, 26]
        ])
        y = [400, 400, 450, 450, 400]
        verts = list(zip(x, y))

        # We expect that these indices will be set to BAD
        idx = np.array([31, 32, 33, 34, 35, 36, 37, 38])

        with xr.open_dataset(self.merge_ncfile) as ds:
            df = ds.to_dataframe()
            xco2_air_qc = df.loc[:, 'xco2_air_socat_qc'].astype(np.uint32)
            xco2_sw_qc = df.loc[:, 'xco2_sw_socat_qc'].astype(np.uint32)
            pCO2_air_qc = df.loc[:, 'pCO2_air_qc'].astype(np.uint32)
            pCO2_sw_qc = df.loc[:, 'pCO2_sw_qc'].astype(np.uint32)
            fCO2_air_qc = df.loc[:, 'fCO2_air_qc'].astype(np.uint32)
            fCO2_sw_qc = df.loc[:, 'fCO2_sw_qc'].astype(np.uint32)

        # verify what those qc values are before running the final QC.
        expected = np.full((8,), core.quality.SOCAT_QUESTIONABLE)
        np.testing.assert_array_equal(xco2_air_qc.iloc[idx], expected)
        np.testing.assert_array_equal(xco2_sw_qc.iloc[idx], expected)

        # verify pCO2 qc values are as expected
        expected = np.full((8,), core.quality.GOOD)
        np.testing.assert_array_equal(pCO2_air_qc.iloc[idx], expected)
        np.testing.assert_array_equal(pCO2_sw_qc.iloc[idx], expected)

        # verify dfCO2 qc values are as expected
        expected = np.full((8,), core.quality.GOOD)
        np.testing.assert_array_equal(fCO2_air_qc.iloc[idx], expected)
        np.testing.assert_array_equal(fCO2_sw_qc.iloc[idx], expected)

        # run the final qc and verify that those qc values have changed
        with XCO2FinalQC(
            self.merge_ncfile, 'xCO2_air', verts, core.quality.SOCAT_BAD
        ) as p:
            p.run()

        with xr.open_dataset(self.merge_ncfile) as ds:
            df = ds.to_dataframe()
            xco2_air_socat_qc = df.loc[:, 'xco2_air_socat_qc'].astype(np.uint32)
            pCO2_air_qc = df.loc[:, 'pCO2_air_qc'].astype(np.uint32)
            fCO2_air_qc = df.loc[:, 'fCO2_air_qc'].astype(np.uint32)

        expected = np.full((8,), core.quality.SOCAT_BAD)
        np.testing.assert_array_equal(xco2_air_socat_qc.iloc[idx], expected)

        # the pCO2 qc data has changed, but it is not socat qc
        expected = np.full((8,), core.quality.MANUALLY_FLAGGED_XCO2)
        np.testing.assert_array_equal(pCO2_air_qc.iloc[idx], expected)
        np.testing.assert_array_equal(fCO2_air_qc.iloc[idx], expected)

        # run the final qc and verify that those qc values have changed
        with XCO2FinalQC(
            self.merge_ncfile, 'xCO2_air', verts, core.quality.SOCAT_GOOD
        ) as p:
            p.run()

        with xr.open_dataset(self.merge_ncfile) as ds:
            df = ds.to_dataframe()
            xco2_air_socat_qc = df.loc[:, 'xco2_air_socat_qc'].astype(np.uint32)
            pCO2_air_qc = df.loc[:, 'pCO2_air_qc'].astype(np.uint32)
            fCO2_air_qc = df.loc[:, 'fCO2_air_qc'].astype(np.uint32)

        expected = np.full((8,), core.quality.SOCAT_GOOD)
        np.testing.assert_array_equal(xco2_air_socat_qc.iloc[idx], expected)

        # pCO2 should have changed back
        expected = np.full((8,), core.quality.GOOD)
        np.testing.assert_array_equal(pCO2_air_qc.iloc[idx], expected)
        np.testing.assert_array_equal(fCO2_air_qc.iloc[idx], expected)


class TestSuiteSailDrone(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, historical_ncfile=None,
        chl_scale_factor=None, chl_dark_count=None, ntu_scale_factor=None,
        ntu_dark_count=None, chl_global_conversion=None,
        o2_salinity_setting=None, sbe16_mapping=False,
        num_points_eachside=1, equil_diff_range_lower=8, verbosity=None
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:
                p.run()

            if historical_ncfile is not None:
                dest = self.raw_path / core.HISTORICAL_NCFILE
                shutil.copyfile(historical_ncfile, dest)

            with XCO2Reduce(
                self.raw_path, self.reduced_path,
                chl_scale_factor=chl_scale_factor,
                chl_dark_count=chl_dark_count,
                ntu_scale_factor=ntu_scale_factor,
                ntu_dark_count=ntu_dark_count,
                chl_global_conversion=chl_global_conversion,
                o2_salinity_setting=o2_salinity_setting,
                sbe16_mapping=sbe16_mapping
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

            with PostXCO2Calc(self.reduced_path, licor_version='830 v1') as p3:
                p3.run()

            with QCChecker(
                self.reduced_path,
                num_points_eachside=num_points_eachside,
                equil_diff_range_lower=equil_diff_range_lower
            ) as p4:
                p4.run()

            with XCO2Merge(
                self.reduced_path, self.merge_ncfile,
                verbosity=verbosity
            ) as p:
                p.run()

            with SocatQC(ncfile=self.merge_ncfile) as p:
                p.run()

            with MetadataWriter(self.merge_ncfile) as m:
                m.run()

    def test_smoke(self):
        """
        Scenario:  run static plot summaries on saildrone data

        Expected Result:  no errors
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        with xr.open_dataset(self.merge_ncfile) as ds:
            df = ds.to_dataframe()
            qc_dry = df.loc[:, 'xco2_air_socat_qc'].astype(np.uint32)
            qc_wet = df.loc[:, 'xco2_sw_socat_qc'].astype(np.uint32)

        # verify what those qc values are before running the final QC.
        expected = np.full((3,), core.quality.SOCAT_QUESTIONABLE)
        np.testing.assert_array_equal(qc_dry, expected)
        np.testing.assert_array_equal(qc_wet, expected)

        # construct the mouse-click data
        x = mdates.date2num([
            dt.datetime(2021, 8, 16, 1, x) for x in [0, 20, 40]
        ])
        y = [400, 398, 400]
        verts = list(zip(x, y))

        # run the final qc and verify that those qc values have changed
        with XCO2FinalQC(
            self.merge_ncfile, 'xCO2_air', verts, core.quality.SOCAT_BAD
        ) as p:
            p.run()

        with xr.open_dataset(self.merge_ncfile) as ds:
            df = ds.to_dataframe()
            qc_dry = df.loc[:, 'xco2_air_socat_qc'].astype(np.uint32)
            qc_wet = df.loc[:, 'xco2_sw_socat_qc'].astype(np.uint32)

        expected = np.array([
            core.quality.SOCAT_QUESTIONABLE,
            core.quality.SOCAT_BAD,
            core.quality.SOCAT_QUESTIONABLE
        ])
        np.testing.assert_array_equal(qc_dry, expected)
