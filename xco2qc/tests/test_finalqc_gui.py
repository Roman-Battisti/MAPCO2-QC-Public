# standard library imports
import datetime as dt
import importlib.resources as ir
import io
import unittest
from unittest import mock

# 3rd party library imports
import matplotlib.dates as mdates
import numpy as np
import xarray as xr

# local imports
from xco2qc import core
import xco2qc.final_qc_gui
from xco2qc.final_qc_gui import XCO2FinalQCGUI
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.merge import XCO2Merge
from xco2qc.metadata_conventions import MetadataWriter
from xco2qc.socat_qc import SocatQC
from xco2qc.validation_data import ValidationData
from tests import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(
        self, module, filename,
        verbosity='CRITICAL',
        num_points_eachside=1,
        equil_diff_range_lower=8,
        region=None,
        sbe16_mapping=False
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
                verbosity=verbosity,
                sbe16_mapping=sbe16_mapping
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
                self.reduced_path, verbosity=verbosity
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
                verbosity=verbosity,
                region=region
            ) as p:
                p.run()

            with SocatQC(ncfile=self.merge_ncfile) as p:
                p.run()

            with MetadataWriter(self.merge_ncfile) as m:
                m.run()

    def test_smoke(self):
        """
        SCENARIO:  Run the ipython notebook GUI on data.  Set the primary
        variable to ntu, then chl_nighttime, and finally xCO2_sw.  Set the
        text reason for change.

        EXPECTED RESULT:  no errors, validate some ylabels for 2ndary plots
        on xco2_sw
        """
        self._processing_chain(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        with XCO2FinalQCGUI(
            self.merge_ncfile, self.reduced_path,
            qflog=self.socat_qf_log
        ) as qcgui:

            qcgui.run()

            qcgui.primary_dropdown.value = 'ntu'
            qcgui.primary_dropdown.value = 'chl_nighttime'
            qcgui.primary_dropdown.value = 'xCO2_sw'

            qcgui.reason.value = 'nothing'

            self.assertEqual(len(qcgui.axes), 1)

    def test_dropdowns_no_doxy(self):
        """
        SCENARIO:  Run the ipython notebook GUI on data with chlorophyll, but
        no dissolved oxygen because the sbe16 only had two channels hooked up

        EXPECTED RESULT:  dissolved oxygen should not be in the dropdown
        """
        self._processing_chain(
            'tests.data.mapco2.whots.depl12',
            'mapco2_whots_0132_dp12_20180922__20191011.txt',
            sbe16_mapping=True
        )

        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()

            self.assertIn('chl_nighttime', qcgui.primary_dropdown.options)
            self.assertIn('ntu', qcgui.primary_dropdown.options)

            self.assertNotIn(
                'dissolved_oxygen', qcgui.primary_dropdown.options
            )

    def test_no_o2_climatology(self):
        """
        SCENARIO:  Run the ipython notebook GUI on data, but the site has no
        O2 climatology.

        EXPECTED RESULT:  no errors
        """
        self._processing_chain(
            'tests.data.mapco2.chuuk1',
            'dp4_20151203_20170322.bad_seafet.txt',
            sbe16_mapping=True
        )

        with XCO2FinalQCGUI(
            self.merge_ncfile, self.reduced_path,
            verbosity='DEBUG'
        ) as qcgui:
            qcgui.run()
            qcgui.primary_dropdown.value = 'dissolved_oxygen'

    def test_o2_validation(self):
        """
        SCENARIO:  Run the ipython notebook GUI on data.  There is O2
        validation data.

        EXPECTED RESULT:  no errors
        """
        self._processing_chain(
            'tests.data.mapco2.chuuk1',
            'dp4_20151203_20170322.bad_seafet.txt',
            sbe16_mapping=True
        )

        text = (
                "time,dissolved_oxygen\n"
                "1950-02-10 09:18:00,100\n"
                "1950-02-10 12:30:00,200\n"
        )
        inputfile = io.StringIO(text)

        with ValidationData(inputfile, self.raw_path) as p:
            p.run()

        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()
            qcgui.primary_dropdown.value = 'dissolved_oxygen'

    @unittest.skip('No climatology plotted here, it is secondary')
    def test_cache_chl_climatology_but_no_excel_chl_climatology(self):
        """
        SCENARIO:  Run the ipython notebook GUI on data, but the site has no
        excel chlorophyll climatology.  The netCDF cache credentials are
        present.

        EXPECTED RESULT:  no errors, the netCDF cache climatology is run.
        """
        self._processing_chain(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        with mock.patch.object(
            xco2qc.data_common.ChlCache, 'run'
        ) as mock_clim_run:
            with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
                qcgui.config['chl_credentials'] = {
                    'username': 'testuser', 'password': 'testpassword'
                }
                qcgui.run()
                qcgui.primary_dropdown.value = 'chl_nighttime'

        mock_clim_run.assert_called_once()

    def test_secondary_dropdown_no_excel_chl_climatology_no_credentials(self):
        """
        SCENARIO:  Run the ipython notebook GUI on data, but the site has no
        chlorophyll climatology.  The netCDF cache credentials do not contain
        username/password for the remote repository.

        EXPECTED RESULT:  no errors, but the missing climatology is logged
        """
        self._processing_chain(
            'tests.data.mapco2.chuuk1',
            'dp4_20151203_20170322.bad_seafet.txt',
            sbe16_mapping=True
        )

        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()

            qcgui.primary_dropdown.value = 'chl_nighttime'

    def test_dropdowns(self):
        """
        SCENARIO:  Run the ipython notebook GUI

        EXPECTED RESULT:  No errors
        """
        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            equil_diff_range_lower=7,
            sbe16_mapping=False
        )

        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()

            # change the primary dropdown value.
            qcgui.primary_dropdown.value = 'xCO2_sw'

    def test_primary_is_o2(self):
        """
        SCENARIO:  run the gui, set the primary dropdown to O2.

        EXPECTED RESULT:  No errors.
        """

        self._processing_chain(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()
            qcgui.radio.value = 'bad'

            qcgui.primary_dropdown.value = 'dissolved_oxygen'

    def test_ph_validation(self):
        """
        SCENARIO:  run the gui, set the primary dropdown to pH.  There is
        pH validation data.

        EXPECTED RESULT:  No errors.  The current plot should have validation
        data.
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            equil_diff_range_lower=7,
            region=10
        )

        text = (
                "time,pH_sw\n"
                "1950-02-10 09:18:00,8\n"
                "1950-02-10 12:30:00,8.1\n"
        )
        inputfile = io.StringIO(text)

        with ValidationData(inputfile, self.raw_path) as p:
            p.run()

        # now run the region selection
        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()
            qcgui.radio.value = 'bad'

            # set the primary variable to ph.
            qcgui.primary_dropdown.value = 'pH_sw'

    def test_primary_is_ph(self):
        """
        SCENARIO:  run the gui, set the primary dropdown to pH.

        EXPECTED RESULT:  No errors.  The primary axis should be inverted.
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            equil_diff_range_lower=7,
            region=10
        )

        # now run the region selection
        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()
            qcgui.radio.value = 'bad'

            # set the primary variable to ph.  The ylims should be around 8.
            qcgui.primary_dropdown.value = 'pH_sw'
            ylim = qcgui.axes[0].get_ylim()
            self.assertTrue(ylim[1] < 10)

            # self.assertTrue(qcgui.axes[0].yaxis_inverted())  # no longer inverting pH in QC plot

    def test_zero_before_and_after(self):
        """
        SCENARIO:  run the gui, set the primary dropdown to xCO2_sw, this
        should trigger "zero before and after"

        EXPECTED RESULT:  no errors
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            equil_diff_range_lower=7
        )

        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()

        qcgui.primary_dropdown.value = 'xCO2_sw'

    def test_set_qc_to_bad(self):
        """
        SCENARIO:  run the gui, set the qc value to 'bad', and trigger a
        selection.  Then set the primary variable to pH.

        EXPECTED RESULT:  the points inside the selection are bad.  The ylim
        for the ph plot changes appropriately.  The primary dropdown contains
        SSS and SST.
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
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
            qc = ds['xco2_sw_socat_qc'].data.astype(np.uint32)

        # verify what those qc values are before running the final QC.
        np.testing.assert_array_equal(
            qc[idx], np.full((8,), core.quality.SOCAT_QUESTIONABLE)
        )

        # now run the region selection
        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()
            qcgui.radio.value = 'bad'
            qcgui.onselect(verts)

        with xr.open_dataset(self.merge_ncfile) as ds:
            qc = ds['xco2_air_socat_qc'].data.astype(np.uint32)

        np.testing.assert_array_equal(
            qc[idx], np.full((8,), core.quality.SOCAT_BAD)
        )

        # neither xco2_air_wet nor xco2_sw_wet should be in the primary
        # dropdown
        self.assertNotIn('xco2_air_wet', qcgui.primary_dropdown.options)
        self.assertNotIn('xco2_sw_wet', qcgui.primary_dropdown.options)

        # set the primary variable to ph.  The ylims should be around 8.
        qcgui.primary_dropdown.value = 'pH_sw'
        ylim = qcgui.axes[0].get_ylim()
        self.assertTrue(ylim[1] < 10)

    def test_no_dissolved_oxygen(self):
        """
        SCENARIO:  there was no dissolved_oxygen

        Expected Result:  no errors
        """
        self._processing_chain(
            'tests.data.mapco2.alawai',
            'dp3_0027_20101207_20120206.txt'
        )

        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()

            qcgui.primary_dropdown.value = 'xCO2_sw'

    def test_no_sss_sst(self):
        """
        SCENARIO:  there was no SSS or SST data

        Expected Result:  neither SSS nor SST are in the dropdowns.
        """
        self._processing_chain(
            'tests.data.mapco2.alawai',
            'dp3_0027_20101207_20120206.txt'
        )

        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()

            self.assertNotIn('SSS', qcgui.primary_dropdown.options)
            self.assertNotIn('SST', qcgui.primary_dropdown.options)

    def test_sst(self):
        """
        SCENARIO:  run the gui, choose SST.  make a selection

        EXPECTED RESULT:  the points inside the selection are manually flagged.
        The secondary dropdown contains SST from the pH sensor.  The radio
        choices change when SST is chosen.  SSS should be a secondary option.
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            equil_diff_range_lower=7
        )

        # construct the mouse-click data
        x = mdates.date2num([
            dt.datetime(2018, 9, x) for x in [26, 27, 27, 26, 26]
        ])
        y = [26.6, 26.6, 27.1, 27.1, 26.6]
        verts = list(zip(x, y))

        # We expect that these indices will be set to BAD
        idx = np.array([31, 32, 33, 34, 35, 36, 37, 38])

        with xr.open_dataset(self.merge_ncfile) as ds:
            qc = ds['SST_qc'].data.astype(np.uint32)

        # verify what those qc values are before running the final QC.
        np.testing.assert_array_equal(
            qc[idx], np.full((8,), core.quality.GOOD)
        )

        # now run the region selection
        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()

            qcgui.primary_dropdown.value = 'SST'
            self.assertEqual(qcgui.radio.options, ('good', 'bad'))

            # Simulate a polygon selection, verify that the section data
            # was manually flagged.
            qcgui.radio.value = 'bad'
            qcgui.onselect(verts)

            with xr.open_dataset(self.merge_ncfile) as ds:
                qc = ds['SST_qc'].data.astype(np.uint32)

            np.testing.assert_array_equal(
                qc[idx], np.full((8,), core.quality.MANUALLY_FLAGGED)
            )

            # restore the primary variable to one that should
            # have three radio button choices
            qcgui.primary_dropdown.value = 'xCO2_sw'
            self.assertEqual(
                qcgui.radio.options, ('good', 'bad', 'questionable')
            )

    def test_secondary_ph(self):
        """
        SCENARIO:  run the gui, set the qc value to 'bad', and trigger a
        selection.  The default primary variable is used, which has pH in
        a secondary plot.

        EXPECTED RESULT:  the points inside the selection are bad.  The pH
        plot axis is inverted.
        """

        self._processing_chain(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
            equil_diff_range_lower=7
        )

        # construct the mouse-click data
        x = mdates.date2num([
            dt.datetime(2018, 9, x) for x in [26, 27, 27, 26, 26]
        ])
        y = [400, 400, 450, 450, 400]
        verts = list(zip(x, y))

        # now run the region selection
        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()
            qcgui.radio.value = 'bad'
            qcgui.primary_dropdown.value = 'xCO2_sw'
            qcgui.onselect(verts)

            # Look at the secondary pH graph, it should be inverted.
            # self.assertTrue(qcgui.axes[2].yaxis_inverted())
