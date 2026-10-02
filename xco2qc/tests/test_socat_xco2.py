"""
Test suite for proper generation of the socat products.
"""
# standard library imports
import datetime as dt
import importlib.resources as ir
import re
import shutil
import warnings
import os

# 3rd party library imports
import lxml.etree as ET
import matplotlib.dates as mdates
import netCDF4
import numpy as np
import pandas as pd

# local imports
from xco2qc import core
from xco2qc.adjustments import XCO2Adjustments
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.external_sbe63 import ImportExternalSBE63
from xco2qc.final_qc_gui import XCO2FinalQCGUI
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.mbl import CompareMBL
from xco2qc.merge import XCO2Merge
from xco2qc.metadata_conventions import MetadataWriter
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.qc import QCChecker
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.socat import SocatWriter
from xco2qc.socat_qc import SocatQC
from xco2qc.trim_netcdf import TrimXCO2netCDF
import tests.test_core


class TestSuite(tests.test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename,
        spanconc=0, loss_of_span=False,
        mbl_correction=0.0,
        models_file=None,
        num_points_eachside=1,
        dissolved_oxygen=None,
        calculate_post_xco2=True,
        mbl_check=False,
        sbe16_mapping=False,
        historical_ncfile=None,
        contributors_citation=None,
        link_citation=None,
        mobility='stationary'
    ):

        cycle_header_ncfile = (
            self.reduced_path / core.CYCLE_HEADER_NCFILE
        )

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:
                p.run()

            if dissolved_oxygen is not None:
                with ImportExternalSBE63(dissolved_oxygen, self.raw_path) as p:
                    p.run()

            with XCO2Reduce(
                self.raw_path,
                self.reduced_path,
                chl_scale_factor=[9], chl_dark_count=[0.065],
                ntu_scale_factor=[5],
                ntu_dark_count=[0.076], chl_global_conversion=1,
                o2_salinity_setting=[0], sbe16_mapping=sbe16_mapping
            ) as p:
                p.run()

            if loss_of_span:
                # Rewrite the loss of span flag appropriately.
                with netCDF4.Dataset(cycle_header_ncfile, mode='r+') as nc:
                    nc['span_flag'][2:] = np.uint8(255)

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with TrimXCO2netCDF(self.reduced_path, self.trimmed_path) as m:
                m.run()

            with ManualRegressionQC(
                self.trimmed_path, models_file=models_file
            ) as p:
                p.run()

            with PostXCO2Calc(
                self.trimmed_path, calculate_post_xco2=calculate_post_xco2
            ) as p:
                p.run()

            with QCChecker(
                self.trimmed_path,
                initial_span_cal=spanconc,
                num_points_eachside=num_points_eachside
            ) as p:
                p.run()

            with XCO2Merge(self.trimmed_path, self.merge_ncfile) as m:
                m.run()

            with SocatQC(ncfile=self.merge_ncfile) as p:
                p.run()

            with MetadataWriter(
                                self.merge_ncfile,
                                contributors_citation=contributors_citation,
                                link_citation=link_citation,
                                stationary_mobile=mobility
                               ) as m:
                m.run()

            if mbl_check:
                with warnings.catch_warnings():
                    warnings.simplefilter('ignore')
                    with CompareMBL(
                        src_dir=self.trimmed_dir,
                        merge_ncfile=self.merge_ncfile,
                        historical_ncfile=historical_ncfile
                    ) as p:
                        p.run()

                with XCO2Adjustments(
                    self.trimmed_path, self.merge_ncfile,
                    mbl_correction=mbl_correction
                ) as mp:
                    mp.run()

    def test_smoke(self):
        """
        SCENARIO:  Create the socat products

        EXPECTED RESULT:  The pCO2 columns should be present in the CSV file.
        The initial submission date should be filled in in the XML file.  The
        vessel ID is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        vessel_id = 'BOBO'

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
            vessel_id=vessel_id,
        ) as p:
            p.run()
        
        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', skiprows=4)

        # the pCO2 columns should not be NaNs
        actual = df['pCO2 SW (sat) uatm']
        expected = pd.Series(
            [379.01, 372.11, 370.7, 367.07], name='pCO2 SW (sat) uatm'
        )
        pd.testing.assert_series_equal(actual, expected)

        actual = df['pCO2 Air (sat) uatm']
        expected = pd.Series(
            [403.62, 402.51, 401.68, 401.03], name='pCO2 Air (sat) uatm'
        )
        pd.testing.assert_series_equal(actual, expected)

        actual = df['dpCO2']
        expected = pd.Series([-24.61, -30.41, -30.98, -33.95], name='dpCO2')
        pd.testing.assert_series_equal(actual, expected)

        # the initial submission element in the XML file should be filled in
        # with today's date.
        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))
        path = 'Dataset_Info/Submission_Dates/Initial_Submission/text()'
        actual = doc.xpath(path)[0]
        expected = dt.date.today().strftime('%m/%d/%Y')
        self.assertEqual(actual, expected)

        # The vessel ID is verified.
        path = 'Cruise_Info/Vessel/Vessel_ID/text()'
        actual = doc.xpath(path)[0]
        self.assertEqual(actual, vessel_id)

        # verify that the pCO2 variables are described in the socat xml file
        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))
        path = 'Variables_Info/Variable/Variable_Name/text()'
        elts = doc.xpath(path)

        self.assertTrue('dpCO2' in elts)
        self.assertTrue('pCO2 SW (wet)' in elts)
        self.assertTrue('pCO2 Air (wet)' in elts)
        
        path = 'Citation'
        actual = doc.xpath(path)[0]
        expected = None
        self.assertEqual(actual.text, expected)
        
        path = 'Data_Set_Link/Link_Note'
        actual = doc.xpath(path)[0]
        expected = None
        self.assertEqual(actual.text, expected)

    def test_qf_log(self):
        """
        SCENARIO:  Auxiliary data is in the data stream.

        EXPECTED RESULT:  The QF log file has the specific reasons for any
        flags.  There is at least xCO2_sw. There are no flag 2s,
        no chl_nighttime due to daytime QC Note and no chl_daytime.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile,
            qflog=self.socat_qf_log
        ) as p:
            p.run()

        actual = pd.read_csv(csvfile / 'La_Parguera_67W_18N_Jun2019_Jun2019_QFlog.csv')
        
        self.assertIn('xCO2_sw', actual['Parameter'].values)
        self.assertNotIn('chl_nighttime', actual['Parameter'].values)
        self.assertNotIn('chl', actual['Parameter'].values)
        self.assertNotIn(2, actual['QF'].values)

        expected_file = ir.files('tests.data.mapco2.laparguera').joinpath('dp12.qflog.csv')  # noqa : E501
        expected = pd.read_csv(expected_file)
        expected = expected.round({"Value": 2})
        pd.testing.assert_frame_equal(actual, expected)

    def test_qf_log_with_user_comments(self):
        """
        SCENARIO:  The QFLOG has is pre-existing and has NTU comments

        EXPECTED RESULT:  The contents are verified. Since NTU is all flag 2, they should not be present in final QFLog, despite notes.
        Additional notes should exist for xCO2_sw and xCO2_air.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        path = ir.files('tests.data.mapco2.laparguera').joinpath('dp12.user_comments.csv')  # noqa : E501
        pd.read_csv(path).to_csv(self.socat_qf_log, index=None)

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile,
            qflog=self.socat_qf_log
        ) as p:
            p.run()

        actual = pd.read_csv(csvfile / 'La_Parguera_67W_18N_Jun2019_Jun2019_QFlog.csv')

        path = ir.files('tests.data.mapco2.laparguera').joinpath('dp12.qflog_with_usercomments.csv')  # noqa : E501
        expected = pd.read_csv(path)
        expected = expected.round({"Value": 2})
        
        self.assertNotIn('ntu', actual['Parameter'].values)
        
        xco2_sw_with_comment = actual[(actual['Date/Time'] == '2019-06-10 00:17:00') & (actual['Parameter'] == 'xCO2_sw')].values[0]
        self.assertEqual(xco2_sw_with_comment[-1], 'out of span range; questionable')
        xco2_air_with_comment = actual[(actual['Date/Time'] == '2019-06-10 03:17:00') & (actual['Parameter'] == 'xCO2_air')].values[0]
        self.assertEqual(xco2_air_with_comment[-1], 'out of span range; also questionable')
        
        pd.testing.assert_frame_equal(actual, expected)

    def test_qflog_after_final_qc(self):
        """
        SCENARIO:  Manual QC is run and 8 items set to BAD.  Then it is run
        again and those same items set to GOOD.

        EXPECTED RESULT:  The QFLOG will reflect the change in the reasons for
        the changes.
        """

        self._processing_pipeline(
            'tests.data.mapco2.whots',
            '0132_dp12_20180922_20191011.cycles-1-50.loss-of-span.txt',
        )

        # generate the socat products BEFORE performing manual QC.
        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile,
            qflog=self.socat_qf_log
        ) as p:
            p.run()

        # there should be no QF values of 4 that are not OUT OF RANGE
        # After we run manual QC, there will be a few such records.
        df = pd.read_csv(csvfile / 'WHOTS_158W_23N_Sep2018_Sep2018_QFlog.csv')
        df = df[(df.QF == core.quality.SOCAT_BAD) & (~df['QC Note'].str.contains('out of range'))]  # noqa : E501
        self.assertEqual(len(df), 0)

        # Now run the manual QC
        #
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
            qcgui.onselect(verts)

        # regenerate the socat products
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile,
            qflog=self.socat_qf_log
        ) as p:
            p.run()

        # the QFLOG will now show BAD records that are not just out of range.
        # These will be the selected values from the manual QC, there are 8
        # of them.
        df = pd.read_csv(csvfile / 'WHOTS_158W_23N_Sep2018_Sep2018_QFlog.csv')
        
        actual = df[(df.QF == core.quality.SOCAT_BAD) & (~df['QC Note'].str.contains('out of range'))]  # noqa : E501
        self.assertEqual(len(actual), 8)

        # 35 good values exist, these should be 0 good values in the final file.
        actual = df[(df.QF == core.quality.SOCAT_GOOD)]
        self.assertEqual(len(actual), 0)

        # Go ahead and test the whole CSV file
        expected_file = ir.files('tests.data.mapco2.whots.depl12').joinpath('dp12.qflog.csv')  # noqa : E501
        expected = pd.read_csv(expected_file)
        expected = expected.round({'Value': 2})
        pd.testing.assert_frame_equal(df, expected)

        # Now change those same back to xco2qc.core.quality.SOCAT_GOOD
        # There should no longer be any BAD items that do not also have the
        # OUT OF RANGE flag set.
        with XCO2FinalQCGUI(self.merge_ncfile, self.reduced_path) as qcgui:
            qcgui.run()
            qcgui.radio.value = 'good'
            qcgui.onselect(verts)

        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile,
            qflog=self.socat_qf_log
        ) as p:
            p.run()

        # no socat bad flags that cannot be tracked back to OUT OF RANGE
        df = pd.read_csv(csvfile / 'WHOTS_158W_23N_Sep2018_Sep2018_QFlog.csv')
        actual = df[(df.QF == core.quality.SOCAT_BAD) & (~df['QC Note'].str.contains('out of range'))]  # noqa : E501
        self.assertEqual(len(actual), 0)

        # eight more good datums - none should show up
        actual = df.query("QF == @core.quality.SOCAT_GOOD")
        self.assertEqual(len(actual), 0)

    def test_bad_pCO2_fugacity_dry(self):
        """
        SCENARIO:  Create the socat products.  The pCO2 and fugacity dry have
        bad socat qc value.

        EXPECTED RESULT:  The pCO2 and fugacity data corresponding to the bad
        values should be set to -999.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            mbl_check=False
        )

        # alter the xCO2 qc value value.
        with netCDF4.Dataset(self.merge_ncfile, 'r+') as nc:
            new_qc = np.array([
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.SOCAT_BAD,
                core.quality.GOOD,
            ])
            nc['xco2_air_socat_qc'][:] = new_qc
            nc['xco2_sw_socat_qc'][:] = new_qc

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
            vessel_id='BOBO'
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', skiprows=4)

        actual = df['pCO2 SW (sat) uatm']
        expected = pd.Series(
            [379.01, 372.11, -999, 367.07], name='pCO2 SW (sat) uatm'
        )
        pd.testing.assert_series_equal(actual, expected)

        actual = df['pCO2 Air (sat) uatm']
        expected = pd.Series(
            [403.62, 402.51, -999, 401.03], name='pCO2 Air (sat) uatm'
        )
        pd.testing.assert_series_equal(actual, expected)

        actual = df['dpCO2']
        expected = pd.Series([-24.61, -30.41, -999, -33.95], name='dpCO2')
        pd.testing.assert_series_equal(actual, expected)

        actual = df[core.socat.FUGACITY_AIR]
        expected = pd.Series(
            [402.07, 400.97, -999, 399.49], name=core.socat.FUGACITY_AIR
        )
        pd.testing.assert_series_equal(actual, expected)

        actual = df[core.socat.FUGACITY_SW]
        expected = pd.Series(
            [377.56, 370.68, -999, 365.67], name=core.socat.FUGACITY_SW
        )
        pd.testing.assert_series_equal(actual, expected)

        actual = df[core.socat.DFCO2]
        expected = pd.Series(
            [-24.51, -30.30, -999, -33.82], name=core.socat.DFCO2
        )
        np.testing.assert_allclose(actual, expected, rtol=1e-3)

    def test_bad_xco2_combination_to_dpco2_dfco2(self):
        """
        SCENARIO: various combinations of xCO2_air and xCO2_sw have been marked bad.
        
        EXPECTED RESULT: Each combination (save for both xCO2s being good) result in -999 in dpCO2 and dfCO2.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            mbl_check=False
        )

        # alter the xCO2 qc value value.
        with netCDF4.Dataset(self.merge_ncfile, 'r+') as nc:
            new_qc_air = np.array([
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.SOCAT_BAD,
                core.quality.SOCAT_BAD,
            ])
            new_qc_sw = np.array([
                core.quality.GOOD,
                core.quality.SOCAT_BAD,
                core.quality.GOOD,
                core.quality.SOCAT_BAD,
            ])
            nc['xco2_air_socat_qc'][:] = new_qc_air
            nc['xco2_sw_socat_qc'][:] = new_qc_sw

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
            vessel_id='BOBO'
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', skiprows=4)

        actual = df['dpCO2']
        expected = pd.Series([-24.61, -999, -999, -999], name='dpCO2')
        np.testing.assert_allclose(actual, expected, rtol=1e-3)

        actual = df[core.socat.DFCO2]
        expected = pd.Series(
            [-24.52, -999, -999, -999], name=core.socat.DFCO2
        )
        np.testing.assert_allclose(actual, expected, rtol=1e-3)
    
    def test_sbe63_smoke(self):
        """
        SCENARIO:  Create the socat products

        EXPECTED RESULT:  The dissolved oxygen and associated QF column should
        be present in the CSV file.  The dissolved oxygen and associated QF
        variables should be identified in the XML file, but there should be no
        CHL or NTU.
        """
        with ir.as_file(ir.files('tests.data.mapco2.whots.depl08').joinpath('sbe63.txt')) as p:
            dissolved_oxygen = p
        self._processing_pipeline(
            'tests.data.mapco2.whots.depl08', 'dp08.example.txt',
            dissolved_oxygen=dissolved_oxygen,
            mbl_check=False
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()
        
        df = pd.read_csv(csvfile / 'WHOTS_158W_23N_Jul2014_Jul2014.csv', skiprows=4)

        # Verify dissolve oxygen columns.
        actual = df['DOXY']
        expected = pd.Series([-999.0, 206.08, 205.64], name='DOXY')
        pd.testing.assert_series_equal(actual, expected)

        actual = df['DOXY QF']
        qc = [
            core.quality.SOCAT_BAD,
            core.quality.SOCAT_GOOD,
            core.quality.SOCAT_GOOD,
        ]
        expected = pd.Series(qc, name='DOXY QF').astype(np.float64)
        pd.testing.assert_series_equal(actual, expected)

        # verify that the new variables are described in the socat xml file
        doc = ET.parse(str(xmlfile / 'WHOTS_158W_23N_Jul2014_Jul2014.xml'))
        path = 'Variables_Info/Variable/Variable_Name/text()'
        elts = doc.xpath(path)

        self.assertTrue('DOXY' in elts)
        self.assertTrue('DOXY QF' in elts)

        # There should be no CHL or NTU in the XML file.
        self.assertFalse('CHL' in elts)
        self.assertFalse('NTU' in elts)
    
    def test_sbe63_bad_qc(self):
        """
        SCENARIO:  Create the socat products

        EXPECTED RESULT:  The dissolved oxygen and associated QF column should
        be present in the CSV file.  The dissolved oxygen and associated QF
        variables should be identified in the XML file, but there should be no
        CHL or NTU.
        """
        with ir.as_file(ir.files('tests.data.mapco2.whots.depl08').joinpath('sbe63.txt')) as p:
            dissolved_oxygen = p
        self._processing_pipeline(
            'tests.data.mapco2.whots.depl08', 'dp08.example.txt',
            dissolved_oxygen=dissolved_oxygen,
            mbl_check=False
        )

        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            nc['dissolved_oxygen_socat_qc'][-1] = core.quality.SOCAT_BAD
        
        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()
        
        df = pd.read_csv(csvfile / 'WHOTS_158W_23N_Jul2014_Jul2014.csv', skiprows=4)

        # Verify dissolve oxygen columns.
        actual = df['DOXY']
        expected = pd.Series([-999.0, 206.08, -999.0], name='DOXY')
        pd.testing.assert_series_equal(actual, expected)
    
    def test_chl_smoke(self):
        """
        SCENARIO:  Create the socat products

        EXPECTED RESULT:  The chl, ntu, and associated QF columns should be
        present in the CSV file.  The chl, ntu, and associated QC variables
        should be identified in the XML file.  There is no dissolved oxygen
        in the XML file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True,
            mbl_check=False
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'La_Parguera_67W_18N_Jun2019_Jun2019.csv', skiprows=4)

        # Verify CHL, NTU, and associated quality columns.
        actual = df['CHL']
        expected = pd.Series([-999.0, 0.35055, 0.3285, -999.0], name='CHL')
        pd.testing.assert_series_equal(actual, expected)

        actual = df['CHL QF']
        expected = np.array([
            core.quality.SOCAT_MISSING,
            core.quality.SOCAT_GOOD,
            core.quality.SOCAT_GOOD,
            core.quality.SOCAT_MISSING,
        ])
        expected = pd.Series(expected, name='CHL QF').astype(np.float64)
        pd.testing.assert_series_equal(actual, expected)

        actual = df['NTU']
        expected = pd.Series([3.1625, 3.2925, 3.269, 3.351], name='NTU')
        pd.testing.assert_series_equal(actual, expected)

        actual = df['NTU QF']
        expected = pd.Series(
            np.full(4, core.quality.SOCAT_GOOD), name='NTU QF'
        ).astype(np.float64)
        pd.testing.assert_series_equal(actual, expected)

        # verify that the new variables are described in the socat xml file
        doc = ET.parse(str(xmlfile / 'La_Parguera_67W_18N_Jun2019_Jun2019.xml'))
        path = 'Variables_Info/Variable/Variable_Name/text()'
        elts = doc.xpath(path)

        self.assertTrue('CHL' in elts)
        self.assertTrue('CHL QF' in elts)
        self.assertTrue('NTU' in elts)
        self.assertTrue('NTU QF' in elts)
        self.assertTrue('DOXY' in elts)
        self.assertTrue('DOXY QF' in elts)

        path = "Method_Description/Other_Sensors/Sensor/Model/text()"
        elts = doc.xpath(path)
        self.assertTrue('Max-250' in elts)
        self.assertTrue('SBE63' in elts)

    def test_chl_bad_qc(self):
        """
        SCENARIO:  Create the socat products

        EXPECTED RESULT:  The chl, ntu, and associated QF columns should be
        present in the CSV file.  The chl, ntu, and associated QC variables
        should be identified in the XML file.  There is no dissolved oxygen
        in the XML file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True,
            mbl_check=False
        )

        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            nc['chl_nighttime_socat_qc'][2] = core.quality.SOCAT_BAD
        
        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'La_Parguera_67W_18N_Jun2019_Jun2019.csv', skiprows=4)

        # Verify CHL, NTU, and associated quality columns.
        actual = df['CHL']
        expected = pd.Series([-999.0, 0.35055, -999.0, -999.0], name='CHL')
        pd.testing.assert_series_equal(actual, expected)
        
    def test_ntu_bad_qc(self):
        """
        SCENARIO:  Create the socat products

        EXPECTED RESULT:  The chl, ntu, and associated QF columns should be
        present in the CSV file.  The chl, ntu, and associated QC variables
        should be identified in the XML file.  There is no dissolved oxygen
        in the XML file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True,
            mbl_check=False
        )

        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            nc['ntu_socat_qc'][2] = core.quality.SOCAT_BAD
        
        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'La_Parguera_67W_18N_Jun2019_Jun2019.csv', skiprows=4)

        # Verify CHL, NTU, and associated quality columns.
        actual = df['NTU']
        expected = pd.Series([3.1625, 3.2925, -999.0, 3.351], name='NTU')
        pd.testing.assert_series_equal(actual, expected)

    def test_2nd_pi(self):
        """
        SCENARIO:  Create the socat products, supply the details of a 2nd PI.

        EXPECTED RESULT:  The PI details show up in the XML file.  The PI names
        show up in the CSV file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            mbl_check=False
        )

        xmlfile = self.root
        csvfile = self.root

        pis = [
            {
                'first_name': 'Adrienne',
                'last_name': 'Sutton',
                'title': 'Dr.',
                'organization': 'NOAA/PMEL',
                'address': '7600 Sand Point Way NE Seattle, WA 98115-6349',
                'phone': '(206) 526-6879',
                'email': 'Adrienne.Sutton@noaa.gov'
            },
            {
                'first_name': 'Wile E.',
                'last_name': 'Coyote',
                'title': '',
                'organization': 'ACME',
                'address': 'Tucson',
                'phone': '(555) 555-5555',
                'email': 'coyote.wile.e@acme.com'
            }
        ]
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
            pi_list=pis
        ) as p:
            p.run()

        # Verify the PI details in the XML file.
        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))

        actual = doc.xpath('Investigator/Name/text()')[1]
        expected = 'Wile E. Coyote'
        self.assertEqual(actual, expected)

        actual = doc.xpath('Investigator/Organization/text()')[1]
        self.assertEqual(actual, pis[1]['organization'])

        actual = doc.xpath('Investigator/Address/text()')[1]
        self.assertEqual(actual, pis[1]['address'])

        actual = doc.xpath('Investigator/Phone/text()')[1]
        self.assertEqual(actual, pis[1]['phone'])

        actual = doc.xpath('Investigator/Email/text()')[1]
        self.assertEqual(actual, pis[1]['email'])

        actual = doc.xpath('Investigator/Name/text()')[0]
        expected = 'Dr. Adrienne Sutton'
        self.assertEqual(actual, expected)

        # Verify the PI details in the CSV file.
        text = (csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv').read_text()
        actual = text.splitlines()[2]
        expected = 'PIs: Sutton_A.; Coyote_W.'
        self.assertEqual(actual, expected)

    def test_qc_operator(self):
        """
        SCENARIO:  Create the socat products, supply the details of the QC
        operator.

        EXPECTED RESULT:  The QCer details show up in the XML file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        xmlfile = self.root
        csvfile = self.root

        qcer = {
            'last_name': 'Coyote',
            'first_name': 'Wile E.',
            'title': '',
            'organization': 'ACME',
            'address': 'Tucson',
            'phone': '(555) 555-5555',
            'email': 'coyote.wile.e@acme.com'
        }
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
            qcer=qcer
        ) as p:
            p.run()

        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))

        actual = doc.xpath('User/Name/text()')[0]
        self.assertEqual(actual, 'Coyote, Wile E.')

        actual = doc.xpath('User/Organization/text()')[0]
        self.assertEqual(actual, qcer['organization'])

        actual = doc.xpath('User/Address/text()')[0]
        self.assertEqual(actual, qcer['address'])

        actual = doc.xpath('User/Phone/text()')[0]
        self.assertEqual(actual, qcer['phone'])

        actual = doc.xpath('User/Email/text()')[0]
        self.assertEqual(actual, qcer['email'])

    def test_unrecognized_id(self):
        """
        SCENARIO:  Create the socat products when the ID is unrecognized.

        EXPECTED RESULT:  There will be a warning, but the products will be
        created.  There should be no PH data mentioned in the XML product.
        """
        self._processing_pipeline(
            'tests.data.mapco2.asv',
            'pco2asv_sd1006.3.full.txt'
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile
        ) as p:
            with warnings.catch_warnings(record=True) as w:
                p.run()

                self.assertTrue(len(w) >= 1)

        # pH should be in the XML, it comes from durafet
        doc = ET.parse(str(xmlfile / 'SD1006_Aug2017_Aug2017.xml'))
        path = 'Variables_Info/Variable/Variable_Name/text()'
        elts = doc.xpath(path)

        self.assertTrue('pH SW' in elts)
        self.assertTrue('pH QF' in elts)

        path = "Method_Description/Other_Sensors/Sensor/Model/text()"
        elts = doc.xpath(path)
        self.assertTrue('SAMI2 pH' not in elts)

    def test_smoke_no_post_xco2(self):
        """
        SCENARIO:  Create the socat products when no post xco2 has been
        calculated.

        EXPECTED RESULT:  The vapor pressure columns will be calculated, i.e.
        not all -999.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            calculate_post_xco2=False
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', index_col=None, skiprows=4)

        expected = pd.Series(
            index=[0, 1, 2, 3],
            data=[1.472859, 1.164336, 1.204243, 1.236940],
            name='H2O Air (mmol/mol)'
        )
        pd.testing.assert_series_equal(df['H2O Air (mmol/mol)'], expected)

    def test_mbl_correction(self):
        """
        SCENARIO:  If an mbl correction was specified, an item in the SOCAT
        MBL must list the creation date of the MBL metadata.

        EXPECTED RESULT:  No errors.
        """
        mbl_correction = 1.0
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                mbl_correction=mbl_correction,
                mbl_check=True,
                spanconc=490,
                historical_ncfile=historical_ncfile
            )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()

        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))
        elt = doc.xpath('Additional_Information')[0]

        timestamp = core.data.mbl.get_timestamp()
        blurb = (
            f'''o As part of the QC process, xCO2 air measurements are compared to the following data sets when available: previous MAPCO2 deployment at same site if overlap on recovery/deployment, following MAPCO2 deployment at same site if overlap on recovery/deployment, and Marine Boundary Layer (MBL) xCO2 air data from GlobalView-CO2.  This MAPCO2 deployment is offset from the available comparison data sets, and an adjustment of {mbl_correction} umol mol-1 was applied to the data set.
   Dlugokencky, E.J., K.W. Thoning, P.M. Lang, and P.P. Tans (2019),
   NOAA Greenhouse Gas Reference from Atmospheric Carbon Dioxide
   Dry Air Mole Fractions from the NOAA ESRL Carbon Cycle Cooperative
   Global Air Sampling Network.
   Data Path: ftp://aftp.cmdl.noaa.gov/data/trace_gases/co2/flask/surface/.

o MBL Data were last downloaded from ESRL on {timestamp.strftime("%Y-%m-%d")}.'''
        )
        self.assertTrue(blurb in elt.text)

    def test_no_mbl_correction(self):
        """
        SCENARIO:  If no mbl correction was specified (0.0), an item in the SOCAT
        MBL must list the creation date of the MBL metadata.

        EXPECTED RESULT:  No errors.
        """
        mbl_correction = 0.0
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                mbl_correction=mbl_correction,
                mbl_check=True,
                spanconc=490,
                historical_ncfile=historical_ncfile
            )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()

        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))
        elt = doc.xpath('Additional_Information')[0]

        timestamp = core.data.mbl.get_timestamp()
        blurb = (
            f'''o As part of the QC process, xCO2 air measurements are compared to the following data sets when available: previous MAPCO2 deployment at same site if overlap on recovery/deployment, following MAPCO2 deployment at same site if overlap on recovery/deployment, and Marine Boundary Layer (MBL) xCO2 air data from GlobalView-CO2.  This MAPCO2 deployment is offset from the available comparison data sets, and no adjustment was applied to the data set.
   Dlugokencky, E.J., K.W. Thoning, P.M. Lang, and P.P. Tans (2019),
   NOAA Greenhouse Gas Reference from Atmospheric Carbon Dioxide
   Dry Air Mole Fractions from the NOAA ESRL Carbon Cycle Cooperative
   Global Air Sampling Network.
   Data Path: ftp://aftp.cmdl.noaa.gov/data/trace_gases/co2/flask/surface/.

o MBL Data were last downloaded from ESRL on {timestamp.strftime("%Y-%m-%d")}.'''
        )
        self.assertTrue(blurb in elt.text)

    def test_citations_stationary(self):
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                spanconc=490,
                historical_ncfile=historical_ncfile,
                contributors_citation='Smith, A., B. Liu, C. Ahmed',
                link_citation='https://test.org'
            )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()

        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))
        path = 'Citation'
        actual = doc.xpath(path)[0]
        expected = 'Smith, A., B. Liu, and C. Ahmed. 2013. High-resolution ocean and atmosphere pCO2 time-series measurements from mooring NH_70W_43N.'
        self.assertEqual(actual.text, expected)
        
        path = 'Data_Set_Link/Link_Note'
        actual = doc.xpath(path)[0]
        expected = 'Refer to https://test.org for links to actual data.'
        self.assertEqual(actual.text, expected)
    
    def test_citations_mobile(self):
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                spanconc=490,
                historical_ncfile=historical_ncfile,
                contributors_citation='Smith, A., B. Liu, C. Ahmed',
                mobility='mobile'
            )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()

        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))
        path = 'Citation'
        actual = doc.xpath(path)[0]
        expected = 'Smith, A., B. Liu, and C. Ahmed. 2013. High-resolution ocean and atmosphere pCO2 time-series measurements from uncrewed surface vehicle NH_70W_43N.'
        self.assertEqual(actual.text, expected)
    
    def test_full(self):
        """
        SCENARIO:  Generate the socat files.

        EXPECTED RESULT:  Geographic coverage and temporal coverage elements
        are verified.  The PI list is verified.
        """
        models_file = self.trimmed_path / core.MODELS_FILE
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
            models_file=models_file,
            loss_of_span=False,
            mbl_check=False
        )

        princ_inv = [
            {
                'first_name': 'Adrienne',
                'last_name': 'Sutton',
                'title': 'Dr.',
                'organization': 'NOAA/PMEL',
                'address': '7600 Sand Point Way NE Seattle, WA 98115-6349',
                'phone': '(206) 526-6879',
                'email': 'Adrienne.Sutton@noaa.gov'
            },
            {
                'first_name': 'Wile E.',
                'last_name': 'Coyote',
                'title': '',
                'organization': 'ACME',
                'address': 'Tucson',
                'phone': '(555) 555-5555',
                'email': 'coyote.wile.e@acme.com'
            }
        ]
        xmlfile = self.root
        csvfile = self.root
        kwargs = {
            'models_file': models_file,
            'pi_list': princ_inv,
            'licor_pressure_correction': 0.3,
        }
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
            **kwargs,
        ) as p:
            p.run()

        # Verify the XML file
        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))

        self._assert_cruise_id(doc)
        self._assert_geographic_coverage(doc)
        self._assert_temporal_coverage(doc)
        self._assert_co2_sensor_calibration(doc)
        self._assert_additional_information_licor_pressure_bias(doc)
        self._assert_additional_information_loss_of_span(doc, False)
        self._assert_additional_information_licor_regression(doc)

        # verify the PI list, it should be in the header (first four lines)
        with (csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv').open() as f:
            header = '\n'.join([f.readline() for _ in range(4)])
        self.assertIn('Sutton_A.; Coyote_W.', header)

        # Verify the CSV file
        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', index_col=None, skiprows=4)
        self.assertEqual(len(df), 4)

        expected_cols = pd.Index([
            "Mooring Name", "Latitude", "Longitude", "Date", "Time",
            "xCO2 SW (wet) (umol/mol)", "CO2 SW QF", "H2O SW (mmol/mol)",
            "xCO2 Air (wet) (umol/mol)", "CO2 Air QF",
            "H2O Air (mmol/mol)",
            "Licor Atm Pressure (hPa)", "Licor Temp (C)", "MAPCO2 %O2",
            "SST (C)", "Salinity", "xCO2 SW (dry) (umol/mol)",
            "xCO2 Air (dry) (umol/mol)", "fCO2 SW (sat) uatm",
            "fCO2 Air (sat) uatm",
            "dfCO2", "pCO2 SW (sat) uatm",
            "pCO2 Air (sat) uatm", "dpCO2", "pH (total scale)", "pH QF"
        ])
        pd.testing.assert_index_equal(df.columns, expected_cols)

    def test_sami(self):
        """
        SCENARIO:  Generate the socat XML, CSV files.  This is a case where we
        know we have good SAMI PH.

        EXPECTED RESULT:  The sami column is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.stratus',
            '0156_dp11_20180410_20190424.4.txt'
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'Stratus_85W_20S_Jun2018_Jun2018.csv', index_col=None, skiprows=4)

        actual = df['pH (total scale)']
        expected = pd.Series(
            [8.103380, 8.061230, 8.058725, 8.060641], name='pH (total scale)'
        )
        pd.testing.assert_series_equal(actual, expected)

    def test_line_endings(self):
        """
        SCENARIO:  Generate the socat CSV file.

        EXPECTED RESULT:  The CSV file has consistent file endings.
        There are no instances of double newlines.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile
        ) as p:
            p.run()

        with open(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', mode='rt') as f:
            text = f.read()

        # there should be no cases of two line endings in a row
        m = re.search('\n\n', text)
        self.assertIsNone(m)

    def test_licor_pressure_correction_via_parameter(self):
        """
        SCENARIO:  Generate the socat XML file.  The licor pressure correction
        is given via a parameter instaed of the config file.

        EXPECTED RESULT:  The licor pressure correction value is found in the
        XML file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            loss_of_span=False,
        )

        licor_pressure_correction = 0.7
        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
            licor_pressure_correction=licor_pressure_correction,
        ) as p:
            p.run()

        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))

        elt = doc.xpath('Additional_Information')[0]

        expected = 'Licor pressure bias of +0.7'
        self.assertIn(expected, elt.text)

    def test_initial_span_cal_via_parameter(self):
        """
        SCENARIO:  Generate the socat XML file.  The initial span cal is given
        via a parameter instead of the config file.

        EXPECTED RESULT:  The initial span cal value is found in the XML file.
        """
        initial_span_cal = 480

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=initial_span_cal,
            loss_of_span=False,
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
            initial_span_cal=initial_span_cal,
        ) as p:
            p.run()

        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))

        path = '/'.join([
            'Method_Description',
            'CO2_Sensors',
            'CO2_Sensor',
            'CO2_Sensor_Calibration',
            'text()'
        ])
        elt = doc.xpath(path)[0]

        self.assertIn(str(initial_span_cal), elt)

    def test_bad_data(self):
        """
        SCENARIO:  Generate the SOCAT XML file.  The first xco2 socat qc value
        was manually flagged bad.

        EXPECTED RESULT:  The bad QC value in the netCDF file results
        in -999 values in the associated xco2 variables.
        """
        models_file = self.trimmed_path / core.MODELS_FILE
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'dp2_0110_20091108_20101028.50.txt',
            spanconc=435,
            models_file=models_file,
        )

        # Write the questionable QC value into the merge file before the SOCAT
        # writer gets hold of it.
        qc = np.full((47,), core.quality.SOCAT_GOOD, dtype=np.uint32)
        qc[0] = core.quality.SOCAT_BAD
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            for xco2qc_var in [
                'xco2_sw_socat_qc', 'xco2_air_socat_qc',
            ]:
                nc[xco2qc_var][:] = qc

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile,
            models_file=models_file
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'Alawai_158W_21N_Nov2009_Nov2009.csv', index_col=None, skiprows=4)

        actual = df['CO2 SW QF'].astype(np.uint32)

        expected = np.full((47,), core.quality.SOCAT_GOOD, dtype=np.uint32)
        expected[0] = core.quality.SOCAT_BAD
        expected = pd.Series(expected, name=core.socat.XCO2_SW_QC)

        pd.testing.assert_series_equal(actual, expected)

        # a bad value will change the associated xco2 variables
        actual = df['xCO2 SW (wet) (umol/mol)'].iloc[0]
        expected = -999
        self.assertEqual(actual, expected)

        actual = df['xCO2 SW (dry) (umol/mol)'].iloc[0]
        expected = -999
        self.assertEqual(actual, expected)

        actual = df['fCO2 SW (sat) uatm'].iloc[0]
        expected = -999
        self.assertEqual(actual, expected)
    
    def test_questionable_data(self):
        """
        SCENARIO:  Generate the SOCAT XML file.  The first xco2 reading was
        flagged.

        EXPECTED RESULT:  The questionable QC value in the netCDF file results
        in a questionable QC value in the CSV file.
        """
        models_file = self.trimmed_path / core.MODELS_FILE
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
            models_file=models_file,
        )

        # Write the questionable QC value into the merge file before the SOCAT
        # writer gets hold of it.
        qc = np.full((4,), core.quality.SOCAT_GOOD, dtype=np.uint32)
        qc[0] = core.quality.SOCAT_QUESTIONABLE
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            for xco2qc_var in [
                'xco2_sw_socat_qc', 'xco2_air_socat_qc',
            ]:
                nc[xco2qc_var][:] = qc

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile,
            models_file=models_file
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', index_col=None, skiprows=4)

        actual = df['CO2 SW QF'].astype(np.uint32)

        # 2 is the GOOD flag
        # 3 is the QUESTIONABLE flag
        expected = np.full((4,), core.quality.SOCAT_GOOD, dtype=np.uint32)
        expected[0] = core.quality.SOCAT_QUESTIONABLE
        expected = pd.Series(expected, name=core.socat.XCO2_SW_QC)

        pd.testing.assert_series_equal(actual, expected)

        # a questionable value does not change the associated pCO2 values
        actual = df['pCO2 SW (sat) uatm'].iloc[0]
        expected = -999
        self.assertNotEqual(actual, expected)

    def test_missing_met_data(self):
        """
        SCENARIO:  Generate the SOCAT XML file.  The met data buffer was always
        empty so there's no salinity, sst data.

        EXPECTED RESULT:  No errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'dp2_0110_20091108_20101028.50.txt',
            spanconc=490
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile
        ) as p:
            p.run()

        # the csv file needs to have salinity and sst, even though they are all
        # -999
        df = pd.read_csv(csvfile / 'Alawai_158W_21N_Nov2009_Nov2009.csv', index_col=None, skiprows=4)
        self.assertEqual(len(df), 47)

        expected_cols = pd.Index([
            "Mooring Name", "Latitude", "Longitude", "Date", "Time",
            "xCO2 SW (wet) (umol/mol)", "CO2 SW QF", "H2O SW (mmol/mol)",
            "xCO2 Air (wet) (umol/mol)", "CO2 Air QF",
            "H2O Air (mmol/mol)",
            "Licor Atm Pressure (hPa)", "Licor Temp (C)", "MAPCO2 %O2",
            "SST (C)", "Salinity", "xCO2 SW (dry) (umol/mol)",
            "xCO2 Air (dry) (umol/mol)", "fCO2 SW (sat) uatm",
            "fCO2 Air (sat) uatm",
            "dfCO2", "pCO2 SW (sat) uatm",
            "pCO2 Air (sat) uatm", "dpCO2", "pH (total scale)", "pH QF"
        ])
        pd.testing.assert_index_equal(df.columns, expected_cols)

        expected = pd.Series(
            np.full((47,), -999), name=core.socat.SST, dtype=np.int64
        )
        pd.testing.assert_series_equal(df[core.socat.SST], expected)

        expected = pd.Series(
            np.full((47,), -999), name=core.socat.SALINITY, dtype=np.int64
        )
        pd.testing.assert_series_equal(df[core.socat.SALINITY], expected)

    def test_bad_gps(self):
        """
        SCENARIO:  Generate the SOCAT XML file when there was bad GPS

        EXPECTED RESULT:  The latitude and longitude values should be -999.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
        )

        # Force the 1st two gps values to have bad QC.
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            data = np.array([
                core.quality.OUT_OF_RANGE,
                core.quality.OUT_OF_RANGE,
                core.quality.GOOD,
                core.quality.GOOD,
            ])
            nc['latitude_qc'][:] = data
            nc['longitude_qc'][:] = data

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', skiprows=4)

        expected = pd.Series(
            [43.022, 43.022, 43.022, 43.022], name=core.socat.LATITUDE
        )
        pd.testing.assert_series_equal(df[core.socat.LATITUDE], expected)

        expected = pd.Series(
            [-70.543, -70.543, -70.543, -70.543], name=core.socat.LONGITUDE
        )
        pd.testing.assert_series_equal(df[core.socat.LONGITUDE], expected)
    
    def test_stationary_gps(self):
        """
        SCENARIO:  Generate the SOCAT XML file when there was bad GPS

        EXPECTED RESULT:  The latitude and longitude values should be -999.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
        )

        # Force the 1st two gps values to have bad QC.
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            lat_data = np.array([
                45.000, 47.000, 43.000, 43.044
            ])
            long_data = np.array([
                45.000, -90.000, -70.543, -70.542
            ])
            nc['latitude'][:] = lat_data
            nc['longitude'][:] = long_data
            
            qc_data = np.array([
                core.quality.OUT_OF_RANGE,
                core.quality.OUT_OF_RANGE,
                core.quality.GOOD,
                core.quality.GOOD,
            ])
            nc['latitude_qc'][:] = qc_data
            nc['longitude_qc'][:] = qc_data

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', skiprows=4)

        expected = pd.Series(
            [43.022, 43.022, 43.022, 43.022], name=core.socat.LATITUDE
        )
        pd.testing.assert_series_equal(df[core.socat.LATITUDE], expected)

        expected = pd.Series(
            [-70.542, -70.542, -70.542, -70.542], name=core.socat.LONGITUDE
        )
        pd.testing.assert_series_equal(df[core.socat.LONGITUDE], expected)
    
    def test_mobile_gps(self):
        """
        SCENARIO:  Generate the SOCAT XML file when there was bad GPS

        EXPECTED RESULT:  The latitude and longitude values should be -999.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490, mobility='mobile',
        )

        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            lat_data = np.array([
                45.000, 46.000, 47.000, 48.000
            ])
            long_data = np.array([
                -70.543, -70.543, -70.543, -70.543
            ])
            nc['latitude'][:] = lat_data
            nc['longitude'][:] = long_data
            
            qc_data = np.array([
                core.quality.GOOD,
                core.quality.OUT_OF_RANGE,
                core.quality.GOOD,
                core.quality.OUT_OF_RANGE,
            ])
            nc['latitude_qc'][:] = qc_data
            nc['longitude_qc'][:] = qc_data

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', skiprows=4)

        expected = pd.Series(
            [45.000, 46.000, 47.000, 47.000], name=core.socat.LATITUDE
        )
        pd.testing.assert_series_equal(df[core.socat.LATITUDE], expected)

        expected = pd.Series(
            [-70.543, -70.543, -70.543, -70.543], name=core.socat.LONGITUDE
        )
        pd.testing.assert_series_equal(df[core.socat.LONGITUDE], expected)

    def test_bad_sstc_qc_for_fugacity_and_pCO2(self):
        """
        SCENARIO:  Generate the SOCAT XML file when the fugacity variables
        show BAD_SSTC.

        EXPECTED RESULT:  The fugacity_sw shows -999 in the corresponding
        location, but the fugacity_air is good.  dfCO2 will also show -999.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
        )

        # Force the 1st two salinity values to have bad QC.
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            data = np.array([
                core.quality.GOOD,
                core.quality.BAD_SSTC,
                core.quality.GOOD,
                core.quality.GOOD,
            ])
            nc['fCO2_air_qc'][:] = data
            nc['fCO2_sw_qc'][:] = data
            nc['pCO2_air_qc'][:] = data
            nc['pCO2_sw_qc'][:] = data

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', skiprows=4)

        # no change for fCO2_air
        expected = pd.Series(
            [402.07, 400.97, 400.14, 399.49], name=core.socat.FUGACITY_AIR
        )
        pd.testing.assert_series_equal(df[core.socat.FUGACITY_AIR], expected)

        # fCO2 sw shows a -999 though.
        expected = pd.Series(
            [377.56, -999.0, 369.28, 365.67], name=core.socat.FUGACITY_SW
        )
        pd.testing.assert_series_equal(df[core.socat.FUGACITY_SW], expected)

        # dfCO2 also shows a -999 though.
        expected = pd.Series(
            [-24.52, -999, -30.88, -33.82], name=core.socat.DFCO2
        )
        np.testing.assert_allclose(df[core.socat.DFCO2], expected, rtol=1e-3)

        # no change for pCO2_air
        expected = pd.Series(
            [403.62, 402.51, 401.68, 401.03], name=core.socat.PCO2_AIR
        )
        pd.testing.assert_series_equal(df[core.socat.PCO2_AIR], expected)

        # pCO2 sw shows a -999 though.
        expected = pd.Series(
            [379.01, -999.0, 370.7, 367.07], name=core.socat.PCO2_SW
        )
        pd.testing.assert_series_equal(df[core.socat.PCO2_SW], expected)

        # dpCO2 also shows a -999 though.
        expected = pd.Series(
            [-24.62, -999.0, -31.00, -33.95], name=core.socat.DPCO2
        )
        np.testing.assert_allclose(df[core.socat.DPCO2], expected, rtol=1e-3)

    def test_bad_salinity_qc(self):
        """
        SCENARIO:  Generate the SOCAT XML file when there was bad SSS

        EXPECTED RESULT:  The SSS values should be -999.
        should be -999.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
        )

        # Force the 1st two salinity values to have bad QC.
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            data = np.array([
                core.quality.MISSING_DATA,
                core.quality.MISSING_DATA,
                core.quality.GOOD,
                core.quality.GOOD,
            ])
            nc['SSS_qc'][:] = data

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', skiprows=4)
        expected = pd.Series(
            [-999, -999, 32.188, 32.188], name=core.socat.SALINITY
        )
        pd.testing.assert_series_equal(df[core.socat.SALINITY], expected)
        
        actual = df['fCO2 SW (sat) uatm'].iloc[:2]
        expected = pd.Series([-999., -999.], name='fCO2 SW (sat) uatm')
        pd.testing.assert_series_equal(actual, expected)
        
        actual = df['fCO2 Air (sat) uatm'].iloc[:2]
        expected = pd.Series([-999., -999.], name='fCO2 Air (sat) uatm')
        pd.testing.assert_series_equal(actual, expected)

        actual = df['dfCO2'].iloc[:2]
        expected = pd.Series([-999., -999.], name='dfCO2')
        pd.testing.assert_series_equal(actual, expected)

        actual = df['pCO2 SW (sat) uatm'].iloc[:2]
        expected = pd.Series([-999., -999.], name='pCO2 SW (sat) uatm')
        pd.testing.assert_series_equal(actual, expected)
        
        actual = df['pCO2 Air (sat) uatm'].iloc[:2]
        expected = pd.Series([-999., -999.], name='pCO2 Air (sat) uatm')
        pd.testing.assert_series_equal(actual, expected)
        
        actual = df['dpCO2'].iloc[:2]
        expected = pd.Series([-999., -999.], name='dpCO2')
        pd.testing.assert_series_equal(actual, expected)
    
    def test_bad_sst_qc(self):
        """
        SCENARIO:  Generate the SOCAT XML file when there was bad SSS

        EXPECTED RESULT:  The SSS values should be -999.
        should be -999.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
        )

        # Force the 1st two SST values to have bad QC.
        with netCDF4.Dataset(self.merge_ncfile, mode='r+') as nc:
            data = np.array([
                core.quality.MISSING_DATA,
                core.quality.MISSING_DATA,
                core.quality.GOOD,
                core.quality.GOOD,
            ])
            nc['SST_qc'][:] = data

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile
        ) as p:
            p.run()

        df = pd.read_csv(csvfile / 'NH_70W_43N_Nov2013_Nov2013.csv', skiprows=4)
        expected = pd.Series(
            [-999, -999, 11.35, 11.35], name=core.socat.SST
        )
        pd.testing.assert_series_equal(df[core.socat.SST], expected)
        
        actual = df['fCO2 SW (sat) uatm'].iloc[:2]
        expected = pd.Series([-999., -999.], name='fCO2 SW (sat) uatm')
        pd.testing.assert_series_equal(actual, expected)
        
        actual = df['fCO2 Air (sat) uatm'].iloc[:2]
        expected = pd.Series([-999., -999.], name='fCO2 Air (sat) uatm')
        pd.testing.assert_series_equal(actual, expected)

        actual = df['dfCO2'].iloc[:2]
        expected = pd.Series([-999., -999.], name='dfCO2')
        pd.testing.assert_series_equal(actual, expected)

        actual = df['pCO2 SW (sat) uatm'].iloc[:2]
        expected = pd.Series([-999., -999.], name='pCO2 SW (sat) uatm')
        pd.testing.assert_series_equal(actual, expected)
        
        actual = df['pCO2 Air (sat) uatm'].iloc[:2]
        expected = pd.Series([-999., -999.], name='pCO2 Air (sat) uatm')
        pd.testing.assert_series_equal(actual, expected)
        
        actual = df['dpCO2'].iloc[:2]
        expected = pd.Series([-999., -999.], name='dpCO2')
        pd.testing.assert_series_equal(actual, expected)
    
    def test_loss_of_span(self):
        """
        SCENARIO:  Generate the SOCAT XML file when there was loss of span.

        EXPECTED RESULT:  Geographic coverage and temporal coverage elements
        are verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            spanconc=490,
            loss_of_span=True,
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile, xmlfile=xmlfile, csvfile=csvfile
        ) as p:
            p.run()

        doc = ET.parse(str(xmlfile / 'NH_70W_43N_Nov2013_Nov2013.xml'))

        self._assert_additional_information_loss_of_span(doc, True)

    def _assert_additional_information_licor_regression(self, doc):
        """
        This is extremely brittle.

        Parameters
        ----------
        doc : lxml.ElementTree
            the SOCAT XML document we just wrote
        """

        path = 'Additional_Information'
        elt = doc.xpath(path)[0]

        blurb = (
            'o Post calculation and correlation between Licor temperature and '
            'span coefficient at cluster center 0 is: '
            'Licor coef = -0.002651 * Temp + 0.9411, '
            'r^2 = 0.9843'
        )
        self.assertTrue(blurb in elt.text)

    def _assert_additional_information_loss_of_span(self, doc,
                                                    loss_of_span=False):
        """
        Parameters
        ----------
        doc : lxml.ElementTree
            the SOCAT XML document we just wrote
        loss_of_span : bool
            If true, then loss of span occured.
        """

        path = 'Additional_Information'
        elt = doc.xpath(path)[0]

        if loss_of_span:
            self.assertTrue("The standard reference gas ran out" in elt.text)
        else:
            self.assertFalse("The standard reference gas ran out" in elt.text)

    def _assert_additional_information_licor_pressure_bias(self, doc):

        path = 'Additional_Information'
        elt = doc.xpath(path)[0]

        licor_correction_text = (
            'This system has Licor pressure bias of +0.300 applied'
        )
        self.assertTrue(licor_correction_text in elt.text)

    def _assert_co2_sensor_calibration(self, doc):
        path = '/'.join([
            'Method_Description',
            'CO2_Sensors',
            'CO2_Sensor',
            'CO2_Sensor_Calibration',
            'text()'
        ])
        txt = doc.xpath(path)[0]
        self.assertTrue('490' in txt)

    def _assert_cruise_id(self, doc):

        path = 'Cruise_Info/Experiment/Cruise/Cruise_ID'
        elt = doc.xpath(path)[0]
        self.assertEqual(elt.text, '316420131105')

    def _assert_temporal_coverage(self, doc):

        path = 'Cruise_Info/Experiment/Cruise/Temporal_Coverage/Start_Date'
        elt = doc.xpath(path)[0]
        self.assertEqual(elt.text, '20131105')

        path = 'Cruise_Info/Experiment/Cruise/Temporal_Coverage/End_Date'
        elt = doc.xpath(path)[0]
        self.assertEqual(elt.text, '20131105')

    def _assert_geographic_coverage(self, doc):

        path = 'Cruise_Info/Experiment/Cruise/Geographical_Coverage/Bounds'

        actual = float(doc.xpath(path + '/Westernmost_Longitude')[0].text)
        expected = -70.543
        self.assertEqual(actual, expected)

        actual = float(doc.xpath(path + '/Easternmost_Longitude')[0].text)
        expected = -70.543
        self.assertEqual(actual, expected)

        actual = float(doc.xpath(path + '/Northernmost_Latitude')[0].text)
        expected = 43.022
        self.assertEqual(actual, expected)

        actual = float(doc.xpath(path + '/Southernmost_Latitude')[0].text)
        expected = 43.022
        self.assertEqual(actual, expected)


class TestSuiteSailDrone(tests.test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, historical_ncfile=None,
        chl_scale_factor=None, chl_dark_count=None, ntu_scale_factor=None,
        ntu_dark_count=None, chl_global_conversion=None,
        o2_salinity_setting=None, sbe16_mapping=False,
        num_points_eachside=1, equil_diff_range_lower=8, 
        mobility='mobile', verbosity=None
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

            with MetadataWriter(self.merge_ncfile, stationary_mobile=mobility) as m:
                m.run()

    def test_smoke(self):
        """
        SCENARIO:  Create the socat products

        EXPECTED RESULT:  The pCO2 columns should be present in the CSV file.
        The initial submission date should be filled in in the XML file.  The
        vessel ID is verified.
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            # There's a UserWarning due to the lack of a site code for AVSCO2
            # systems
            with self.assertWarns(UserWarning):
                p.run()

        df = pd.read_csv(csvfile / 'Unknown_Aug2021_Aug2021.csv', skiprows=4)

        self.assertIn('pCO2 SW (sat) uatm', df.columns)
        self.assertIn('pCO2 Air (sat) uatm', df.columns)
        self.assertIn('dpCO2', df.columns)

        # the initial submission element in the XML file should be filled in
        # with today's date.
        doc = ET.parse(str(xmlfile / 'Unknown_Aug2021_Aug2021.xml'))
        path = 'Dataset_Info/Submission_Dates/Initial_Submission/text()'
        actual = doc.xpath(path)[0]
        expected = dt.date.today().strftime('%m/%d/%Y')
        self.assertEqual(actual, expected)
    
    def test_config_ncei_name(self):
        """
        SCENARIO:  ncei_station_name has been specified in the config file.

        EXPECTED RESULT:  New socat csv, xml, QFlog should start with the specified station name.
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        xmlfile = self.root
        csvfile = self.root
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
        ) as p:
            # Since a ncei_station_name a UserWarning due to the lack of a site code for AVSCO2
            # systems should not be raised
            
            with warnings.catch_warnings():
                warnings.simplefilter('error')
                p.config['metadata']['ncei_station_name'] = 'roadrunner'
                p.run()
            
        dir_list = os.listdir(self.root)
        self.assertIn('roadrunner_Aug2021_Aug2021.csv', dir_list)
        self.assertIn('roadrunner_Aug2021_Aug2021.xml', dir_list)
        self.assertIn('roadrunner_Aug2021_Aug2021_QFlog.csv', dir_list)
        self.assertNotIn('Unknown_Aug2021_Aug2021.csv', dir_list)
        self.assertNotIn('Unknown_Aug2021_Aug2021.xml', dir_list)
        self.assertNotIn('Unknown_Aug2021_Aug2021_QFlog.csv', dir_list)
            
        
    def test_kwargs(self):
        """
        SCENARIO:  the socat writer needs to be able to accept unspecified
        keywords.  it may be pass a slew of metadata parameters, not all of
        which are used

        EXPECTED RESULT:  no errors
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        xmlfile = self.root
        csvfile = self.root
        kwargs = {'a': 1, 'b': 2}
        with SocatWriter(
            ncfile=self.merge_ncfile,
            xmlfile=xmlfile,
            csvfile=csvfile,
            **kwargs
        ) as p:
            # There's a UserWarning due to the lack of a site code for AVSCO2
            # systems
            with self.assertWarns(UserWarning):
                p.run()
