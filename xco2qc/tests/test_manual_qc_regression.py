# standard library imports
import datetime as dt
import importlib.resources as ir
import pickle
import platform
import shutil
import unittest
import warnings

# 3rd party library imports
import numpy as np
from nco import Nco
import netCDF4
import pandas as pd

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(
        self, module, filename,
        verbosity='CRITICAL',
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity=verbosity
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

    def test_kmeans_nans(self):
        """
        Scenario:  the temperature data has a single NaN

        Expected results:  the regression is still good
        """
        with ManualRegressionQC(self.reduced_path) as p:

            temperature = [10, 20, np.nan, 30]
            temp_qc = [1, 1, 4, 1]
            sc = [19, 41, 39, 59]
            sc_qc = [1, 1, 1, 1]
            span_flag = [1, 1, 1, 1]
            label = [np.nan, np.nan, np.nan, np.nan]

            timestamp = [
                dt.datetime(2020, 1, 1),
                dt.datetime(2020, 1, 2),
                dt.datetime(2020, 1, 2, 1),
                dt.datetime(2020, 1, 3)
            ]

            data = {
                'temperature': temperature,
                'temp_qc': temp_qc,
                'sc': sc,
                'sc_qc': sc_qc,
                'span_flag': span_flag,
                'label': label,
                'timestamp': timestamp
            }
            df = pd.DataFrame(data)
            df['timestamp'] = df['timestamp'].apply(lambda x: x.timestamp())

            p.df = df

            p.run_kmeans()
            p.run_regression_on_kmeans_clusters()
            p.update_span_coefficients()

            # there should be only one NaN in the prediction
            self.assertEqual((p.df['predict'] == -999999).sum(), 1)

    def test_smoke(self):
        """
        SCENARIO:  four points are selected

        EXPECTED RESULT:  the span coefficient should be appropriately flagged
        """
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        with warnings.catch_warnings():

            # there is a spurious warning in seaborn due to the label
            # column being all NaN.  Just ignore it.
            warnings.simplefilter('ignore')

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            # create mouse-click data
            x = [25.5, 26, 26, 25.5, 25.5]
            y = [0.821, 0.821, 0.822, 0.822, 0.821]
            verts = list(zip(x, y))

            p.onselect(verts)

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['span_coefficient_qc'][:]

        expected = np.full((50,), core.quality.GOOD)
        expected[2] = core.quality.MANUALLY_FLAGGED
        expected[11] = core.quality.MANUALLY_FLAGGED
        expected[19] = core.quality.MANUALLY_FLAGGED
        expected[20] = core.quality.MANUALLY_FLAGGED

        np.testing.assert_allclose(actual, expected)

    def test_span_flag(self):
        """
        SCENARIO:  a span flag value is 255

        EXPECTED RESULT:  no errors
        """
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            data = nc['span_flag'][:]
            data[10] = 255
            nc['span_flag'][:] = data

        with warnings.catch_warnings():

            # there is a spurious warning in seaborn due to the label
            # column being all NaN.  Just ignore it.
            warnings.simplefilter('ignore')

            with ManualRegressionQC(self.reduced_path, n_clusters=2) as p:
                p.run()

    @unittest.skipIf(
        platform.machine() == 'arm64', 'Nco not working on apple silicon'
    )
    def test_zpon_file_short(self):
        """
        SCENARIO:  The ZPON netCDF file has a length that is one less than
        the others.

        EXPECTED RESULT:  no errors
        """
        if platform.machine() == 'arm64':
            return
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        # cut the zpon file by 1 time slice
        nco = Nco()
        ifile = self.reduced_path / 'licor.zero-pump-on.nc'
        ofile = self.reduced_path / 'tmp.nc'
        nco.ncks(input=str(ifile), output=str(ofile), dmn='time,0,48')

        # copy the file into place
        shutil.copyfile(ofile, ifile)

        with warnings.catch_warnings():

            # there is a spurious warning in seaborn due to the label
            # column being all NaN.  Just ignore it.
            warnings.simplefilter('ignore')

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

                # create mouse-click data
                x = [25.5, 26, 26, 25.5, 25.5]
                y = [0.821, 0.821, 0.822, 0.822, 0.821]
                verts = list(zip(x, y))

                p.onselect(verts)

    def test_deselect(self):
        """
        SCENARIO:  four points are selected, then two are deselected

        EXPECTED RESULT:  the span coefficient should be appropriately flagged
        """
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        with warnings.catch_warnings():

            # there is a spurious warning in seaborn due to the label
            # column being all NaN.  Just ignore it.
            warnings.simplefilter('ignore')

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

                # create mouse-click data for the initial select
                x = [25.5, 26, 26, 25.5, 25.5]
                y = [0.821, 0.821, 0.822, 0.822, 0.821]
                verts = list(zip(x, y))
                p.onselect(verts)

                # create mouse-click data for the de-select
                x = [25.5, 25.8, 25.8, 25.5, 25.5]
                y = [0.821, 0.821, 0.822, 0.822, 0.821]
                verts = list(zip(x, y))
                p.onselect(verts)

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['span_coefficient_qc'][:]

        expected = np.full((50,), core.quality.GOOD)
        expected[2] = core.quality.MANUALLY_FLAGGED
        expected[11] = core.quality.MANUALLY_FLAGGED

        np.testing.assert_allclose(actual, expected)

    def test_read_back_model_file(self):
        """
        SCENARIO:  We wish to independently access the linear regressions and
        clustering models.

        EXPECTED RESULT:  the models are accessed successfully
        """
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        models_file = self.reduced_path / core.MODELS_FILE
        with ManualRegressionQC(
            self.reduced_path, models_file=models_file
        ) as p:
            p.run()

        with open(models_file, mode='rb') as f:
            regr_models, km = pickle.load(f)

        np.testing.assert_allclose(regr_models[0].rsquared, 0.9794, rtol=1e-3)
        self.assertEqual(km.n_clusters, 1)


class TestSuiteSailDrone(test_core.TestSuite):

    def _processing_pipeline(self, module, filename, **kwargs):

        # Run the processing up until the xco2 processing
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            input_dir = inputfile.parents[0]

            with RawTextToRawNC(
                input_dir, dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path, verbosity='warning') as p2:
                p2.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  Process reduced LICOR data.

        EXPECTED RESULT:  The pCO2 is present.
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        with warnings.catch_warnings():

            # there is a spurious warning in seaborn due to the label
            # column being all NaN.  Just ignore it.
            warnings.simplefilter('ignore')

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

                # create mouse-click data
                x = [14.3, 14.58, 14.58, 14.3, 14.3]
                y = [0.8106, 0.8106, 0.8107, 0.8107, 0.8106]
                verts = list(zip(x, y))

                p.onselect(verts)

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['span_coefficient_qc'][:]

        expected = np.full((3,), core.quality.GOOD)
        expected[1] = core.quality.MANUALLY_FLAGGED

        np.testing.assert_allclose(actual, expected)
