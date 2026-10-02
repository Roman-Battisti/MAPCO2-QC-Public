# standard library imports
import importlib.resources as ir

# 3rd party library imports
import netCDF4
import numpy as np
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_gps import ManualGpsQC
from tests import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(self, module, filename):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with XCO2Reduce(
                self.raw_path,
                self.reduced_path,
            ) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p2:
                p2.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  the gps location (0, 0) is clearly bad, that's the one we
        will flag.  It is the first reported location.

        EXPECTED RESULT:  There is just one datum that is masked.
        """

        # Run the processing chain up until the merge.
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        # construct the mouse-click data
        x = [-1, 1, 1, -1, -1]
        y = [-1, -1, 1, 1, -1]
        verts = list(zip(x, y))

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with ManualGpsQC(ncfile, verbosity='CRITICAL') as p:
            p.run()
            p.onselect(verts)

        with xr.open_dataset(ncfile) as ds:
            actual = ds['latitude_qc'].data.astype(np.uint32)
            expected = np.full(50, core.quality.GOOD).astype(np.uint32)
            expected[0] = core.quality.MANUALLY_FLAGGED
            np.testing.assert_allclose(actual, expected)

            actual = ds['longitude_qc'].data.astype(np.uint32)
            expected = np.full(50, core.quality.GOOD).astype(np.uint32)
            expected[0] = core.quality.MANUALLY_FLAGGED
            np.testing.assert_allclose(actual, expected)

        # If we run it again without selecting any points, the flag must be
        # cleared
        with ManualGpsQC(ncfile) as p:
            p.run()

        with xr.open_dataset(ncfile) as ds:
            actual = ds['latitude_qc'].data.astype(np.uint32)
            actual = np.nonzero(
                np.bitwise_and(actual, core.quality.MANUALLY_FLAGGED)
            )
            actual = actual[0]
            self.assertEqual(len(actual), 0)

            actual = ds['longitude_qc'].data.astype(np.uint32)
            actual = np.nonzero(
                np.bitwise_and(actual, core.quality.MANUALLY_FLAGGED)
            )
            actual = actual[0]
            self.assertEqual(len(actual), 0)

    def test_unselect(self):
        """
        SCENARIO:  the gps location (0, 0) is clearly bad, that's the one we
        will flag.  It is the first reported location.  But then we will unflag
        it.

        EXPECTED RESULT:  All the data is good.
        """

        # Run the processing chain up until the merge.
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt'
        )

        # construct the mouse-click data
        x = [-1, 1, 1, -1, -1]
        y = [-1, -1, 1, 1, -1]
        verts = list(zip(x, y))

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with ManualGpsQC(ncfile, verbosity='CRITICAL') as p:
            p.run()
            p.onselect(verts)
            p.onselect(verts)

        with xr.open_dataset(ncfile) as ds:
            actual = ds['latitude_qc'].data.astype(np.uint32)
            expected = np.full(50, core.quality.GOOD).astype(np.uint32)
            np.testing.assert_allclose(actual, expected)

            actual = ds['longitude_qc'].data.astype(np.uint32)
            expected = np.full(50, core.quality.GOOD).astype(np.uint32)
            np.testing.assert_allclose(actual, expected)

    def test_all_zeros(self):
        """
        SCENARIO:  All the GPS is bad, reporting back as lat and lon equal to
        zero.

        EXPECTED RESULT:  don't error out
        """

        # Run the processing chain up until the merge.
        self._processing_chain(
            'tests.data.mapco2.alawai',
            'dp2_0110_20091108_20101028.50.txt'
        )

        # Rewrite the lat and lon as all zeros.
        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['latitude'][:] = np.zeros((50,))
            nc['longitude'][:] = np.zeros((50,))

        with ManualGpsQC(ncfile) as p:
            p.run()

            # construct the mouse-click data
            x = [-1, 1, 1, -1, -1]
            y = [-1, -1, 1, 1, -1]
            verts = list(zip(x, y))

            # This should mask out all the zero gps values.  No errors, please.
            p.onselect(verts)


class TestSuiteSailDrone(test_core.TestSuite):

    def _processing_pipeline(self, module, filename):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with XCO2Reduce(
                self.raw_path,
                self.reduced_path,
            ) as p1:
                p1.run()

            with PreXCO2Calc(self.reduced_path) as p2:
                p2.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  QC GPS with saildrone data

        EXPECTED RESULT:  no errors
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with ManualGpsQC(ncfile, verbosity='CRITICAL') as p:
            p.run()
