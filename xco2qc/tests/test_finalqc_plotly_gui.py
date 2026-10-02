# standard library imports
import importlib.resources as ir

# 3rd party library imports

# local imports
from xco2qc.add_plot_widget import AdditionalPlotsGUI
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.trim_netcdf import TrimXCO2netCDF
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.merge import XCO2Merge
from xco2qc.metadata_conventions import MetadataWriter
from xco2qc.socat_qc import SocatQC
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
            
            with TrimXCO2netCDF(
                self.reduced_path, self.trimmed_path,
            ) as p:
                p.run()

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
        variable to ntu, then chl_nighttime, and finally xCO2_sw.

        EXPECTED RESULT:  no errors, validate some ylabels for 2ndary plots
        on xco2_sw
        """
        self._processing_chain(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        with AdditionalPlotsGUI(
            merged_folder_path=self.merge_path,
            trimmed_folder_path=self.trimmed_path,
            site_id='laparguera',
            isMobile=False,
            config = self.config,
        ) as gui:
            gui.run()
    
    def test_netcdf_access(self):
        """
        SCENARIO:  Run the ipython notebook AdditionalPlotsGUI on data. Check that internal netcdf access
        is getting data properly.
        
        EXPECTED RESULT: no errors
        """
        
        self._processing_chain(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        with AdditionalPlotsGUI(
            merged_folder_path=self.merge_path,
            trimmed_folder_path=self.trimmed_path,
            site_id='laparguera',
            isMobile=False,
            config = self.config,
        ) as gui:
            gui.run()
        
        data = gui.data
        
        # test data has correctly identified and stored all netCDF files in trimmed.
        actual = data.available_data_sources()
        actual.sort()
        expected = [
                    'apoff', 'apon', 'chl_climatology', 'epoff', 'epon',
                    'header', 'merge', 'metsstc','o2_climatology', 'sami',
                    'sbe16', 'spcal', 'spoff', 'spon', 'zpcal', 'zpoff', 'zpon'
                   ]
        self.assertEqual(actual, expected)
        
        # test data returns correct column names from data source call
        actual = data.available_data_in_source('header')
        actual.sort()
        expected = ['battery_logic', 'battery_trans', 'gps_aqtime',
                    'gps_dtime', 'gps_dtime_ck', 'gps_qf', 'in_out_flag',
                    'latitude', 'latitude_qc', 'longitude', 'longitude_qc',
                    'mode', 'rand1', 'rand2', 'span2_coefficient', 'span_coefficient',
                    'span_coefficient_qc', 'span_flag', 'sys_dtime2',
                    'time', 'valve_pulse', 'zero_coefficient', 'zero_flag']
        self.assertEqual(actual, expected)
        
        # test proper return when asking data for column that doesn't exist
        actual = data.get_data('met something')
        expected = 'met something'
        self.assertEqual(actual, expected)
    
    def test_plotter(self):
        """
        SCENARIO:  Run the ipython notebook AdditionalPlotsGUI on data. Check that internal plotter
        is functioning properly.
        
        EXPECTED RESULT: no errors
        """
        
        self._processing_chain(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        with AdditionalPlotsGUI(
            merged_folder_path=self.merge_path,
            trimmed_folder_path=self.trimmed_path,
            site_id='laparguera',
            isMobile=True,
            config = self.config,
        ) as gui:
            gui.run()
        
        plotter = gui.plotter
        plotter_dict = plotter.plot_groups
        
        # test plotter dict has expected keys
        self.assertIn('qc_plots', plotter_dict)
        
        pages_dict = plotter_dict['qc_plots']
        
        # sami pH is an added plot, check that adding plot function working properly
        data_dict = pages_dict['data'].plots_dict['col_3']
        self.assertEqual('measured pH and calculated pH (pCO2 & TA)', data_dict[1]['name'])
        self.assertNotIn('x', data_dict[1])
        
        # test that maps exist and first plot meets expected keys
        self.assertIn('maps', pages_dict)  # since isMobile=True
        maps_dict = pages_dict['maps'].plots_dict['col_1']
        self.assertEqual('xCO2 Air (dry) by position', maps_dict[1]['name'])
        self.assertEqual('HEADER LONGITUDE', maps_dict[1]['x'])
        self.assertIn('HEADER LATITUDE', maps_dict[1]['y1'][0])
        
        self.assertIn('multi_year', plotter_dict)
        