# standard library imports
import importlib.resources as ir
import shutil

# 3rd party library imports
import xarray as xr

# local imports
import xco2qc.core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.external_historical import ImportHistorical
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from xco2qc.adjustments import XCO2Adjustments
from xco2qc.metadata_gui import MetadataGUI, NoMobileSelection
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(
        self, module, filename, initial_span_cal=490, num_points_eachside=1,
        historical_file=None
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p0:
                p0.run()

            if historical_file is not None:
                try:
                    with xr.open_dataset(historical_file):
                        pass
                except OSError:
                    # importing a PMEL ERDDAP file
                    with ImportHistorical(historical_file, self.raw_path) as p:
                        p.run()
                else:
                    # importing a text file
                    dst = self.raw_path / xco2qc.core.HISTORICAL_NCFILE
                    shutil.copyfile(historical_file, dst)

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

            with PostXCO2Calc(self.reduced_path) as p2:
                p2.run()

            with QCChecker(
                self.reduced_path,
                initial_span_cal=initial_span_cal,
                num_points_eachside=num_points_eachside
            ) as p3:
                p3.run()

            with XCO2Merge(self.reduced_path, self.merge_ncfile) as p:
                p.run()

            with XCO2Adjustments(self.reduced_path, self.merge_ncfile) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  The defaults are accepted.

        EXPECTED RESULT:  The defaults are verified, i.e. the default PI is
        present.
        """

        with MetadataGUI() as gui:
            gui.run()
            gui.stationary_mobile.value = 'Stationary'

            kwargs = gui.gather_kwargs()

        self.assertEqual(
            kwargs['pi_list'],
            [{
                'last_name': 'Sutton',
                'first_name': 'Adrienne',
                'title': 'Dr.',
                'organization': 'NOAA/PMEL',
                'address': '7600 Sand Point Way NE Seattle, WA 98115-6349',
                'phone': '(206) 526-6879',
                'email': 'Adrienne.Sutton@noaa.gov'
            }]
        )

    def test_vessel_id(self):
        """
        SCENARIO:  The vessel ID element is set.

        EXPECTED RESULT:  The vessel id is verified.
        """

        with MetadataGUI() as gui:
            gui.run()
            gui.stationary_mobile.value = 'Stationary'

            expected = 'BOBO'
            gui.vessel_id_text.value = expected

            kwargs = gui.gather_kwargs()
            actual = kwargs['vessel_id']

        self.assertEqual(actual, expected)

    def test_two_pis(self):
        """
        SCENARIO:  An additional PI is specified.

        EXPECTED RESULT:  The defaults are verified.
        """

        extra_pi = {
            'last_name': 'Washington',
            'first_name': 'George',
            'title': 'Dr.',
            'organization': 'NOAA/NCEP',
            'address': '5830 Research CT, College Park, MD  55555',
            'phone': '(555) 555-5555',
            'email': 'George.Washington@noaa.gov'
        }

        with MetadataGUI(num_pis=2) as gui:
            gui.run()

            gui2 = gui.pi_list.children[1]

            gui2.children[0].children[1].value = extra_pi['last_name']
            gui2.children[1].children[1].value = extra_pi['first_name']
            gui2.children[2].children[1].value = extra_pi['title']

            gui2.children[3].children[1].value = extra_pi['organization']
            gui2.children[4].children[1].value = extra_pi['address']
            gui2.children[5].children[1].value = extra_pi['phone']
            gui2.children[6].children[1].value = extra_pi['email']
            gui.stationary_mobile.value = 'Stationary'

            kwargs = gui.gather_kwargs()

        self.assertEqual(
            kwargs['pi_list'],
            [
                {
                    'last_name': 'Sutton',
                    'first_name': 'Adrienne',
                    'title': 'Dr.',
                    'organization': 'NOAA/PMEL',
                    'address': '7600 Sand Point Way NE Seattle, WA 98115-6349',
                    'phone': '(206) 526-6879',
                    'email': 'Adrienne.Sutton@noaa.gov'
                },
                extra_pi
            ]
        )
    
    def test_blank_pi(self):
        """
        SCENARIO:   More PIs were specified than details given.
        
        EXPECTED RESULT: Blank PIs are not collected.
        """
        
        with MetadataGUI(num_pis=2) as gui:
            gui.run()
            gui.stationary_mobile.value = 'Stationary'
            
            kwargs = gui.gather_kwargs()
        
        self.assertEqual(
            kwargs['pi_list'],
            [
                {
                    'last_name': 'Sutton',
                    'first_name': 'Adrienne',
                    'title': 'Dr.',
                    'organization': 'NOAA/PMEL',
                    'address': '7600 Sand Point Way NE Seattle, WA 98115-6349',
                    'phone': '(206) 526-6879',
                    'email': 'Adrienne.Sutton@noaa.gov'
                }
            ]
        )
        
    
    def test_qcer(self):
        """
        SCENARIO:  The details of the person running the QC program are
        entered.

        EXPECTED RESULT:  Those details are gathered from the GUI.
        """

        expected = {
            'last_name': 'Coyote',
            'first_name': 'Wile E.',
            'title': '',
            'organization': 'ACME',
            'address': 'Tucson',
            'phone': '(555) 555-5555',
            'email': 'coyote.wile.e@acme.com'
        }
        with MetadataGUI() as gui:
            gui.run()

            gui.qcer['last_name'].value = expected['last_name']
            gui.qcer['first_name'].value = expected['first_name']
            gui.qcer['title'].value = expected['title']
            gui.qcer['organization'].value = expected['organization']
            gui.qcer['address'].value = expected['address']
            gui.qcer['phone'].value = expected['phone']
            gui.qcer['email'].value = expected['email']
            gui.stationary_mobile.value = 'Stationary'

            kwargs = gui.gather_kwargs()

        self.assertEqual(kwargs['qcer']['last_name'], expected['last_name'])
        self.assertEqual(kwargs['qcer']['first_name'], expected['first_name'])
        self.assertEqual(kwargs['qcer']['title'], expected['title'])

        self.assertEqual(
            kwargs['qcer']['organization'], expected['organization']
        )
        self.assertEqual(kwargs['qcer']['address'], expected['address'])
        self.assertEqual(kwargs['qcer']['phone'], expected['phone'])
        self.assertEqual(kwargs['qcer']['email'], expected['email'])

    def test_acdd_attributes_against_historical_ncfile(self):
        """
        SCENARIO:  A historical netCDF file from PMEL is present.

        EXPECTED RESULT:  The keywords, title, summary attributes are populated
        from the historical netCDF file.
        """

        with ir.as_file(ir.files(
            'tests.data.netcdf'
            ).joinpath(
            'nh.nc'
        )) as historical_file:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

            with MetadataGUI(netcdf_dir=self.raw_path) as gui:
                gui.run()
                gui.stationary_mobile.value = 'Stationary'

                kwargs = gui.gather_kwargs()

        # The keyword arguments produced by the GUI should be the same as
        # what is found in the historical netCDF file.
        for attr in ['keywords', 'summary', 'title']:
            with xr.open_dataset(historical_file) as ds:

                for attr_name in [
                    'creator_name', 'creator_email', 'creator_url', 'infoUrl',
                    'institution', 'keywords', 'license', 'references',
                    'summary', 'title'
                ]:
                    attr_val = getattr(ds, attr_name)
                    self.assertEqual(attr_val, kwargs[attr_name], attr_name)

                # And just verify that these attributes just exist
                self.assertTrue(len(kwargs['history']) > 1)
                self.assertTrue(len(kwargs['standard_name_vocabulary']) > 1)
    
    def test_acdd_attributes_against_config_smoke(self):
        """
        SCENARIO:  No citation and link info provided in config file.

        EXPECTED RESULT:  The citation and link info should be ''.
        """

        with ir.as_file(ir.files(
            'tests.data.netcdf'
            ).joinpath(
            'nh.nc'
        )) as historical_file:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

            with MetadataGUI(netcdf_dir=self.raw_path) as gui:
                gui.run()
                gui.stationary_mobile.value = 'Mobile'

                kwargs = gui.gather_kwargs()
            
        self.assertEqual(kwargs['contributors_citation'], '')
        self.assertEqual(kwargs['link_citation'], '')
    
    def test_acdd_attributes_against_config(self):
        """
        SCENARIO:  Citation and link information is present in config file.

        EXPECTED RESULT:  The citation and link information are correct and properly formatted.
        """

        with ir.as_file(ir.files(
            'tests.data.netcdf'
            ).joinpath(
            'nh.nc'
        )) as historical_file:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

            with MetadataGUI(netcdf_dir=self.raw_path) as gui:
                gui.config['metadata']['contributors_citation'] = ['Sutton, A.', 'B. Smith', 'C. Kim']
                gui.config['metadata']['link_citation'] = 'https://test.org'
                gui.run()
                gui.stationary_mobile.value = 'Stationary'

                kwargs = gui.gather_kwargs()
                
        self.assertEqual(kwargs['contributors_citation'], 'Sutton, A., B. Smith, C. Kim')
        self.assertEqual(kwargs['link_citation'], 'https://test.org')
    
    def test_mobility_not_specified(self):
        with ir.as_file(ir.files(
            'tests.data.netcdf'
            ).joinpath(
            'nh.nc'
        )) as historical_file:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

            with MetadataGUI(netcdf_dir=self.raw_path) as gui:
                gui.run()
                
                with self.assertRaises(NoMobileSelection):
                    gui.gather_kwargs()
    
    def test_mobility_speicified(self):
        with ir.as_file(ir.files(
            'tests.data.netcdf'
            ).joinpath(
            'nh.nc'
        )) as historical_file:
            self._processing_chain(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.no_depl.txt',
                historical_file=historical_file
            )

            with MetadataGUI(netcdf_dir=self.raw_path) as gui:
                gui.run()
                gui.stationary_mobile.value = 'Stationary'
                
                kwargs = gui.gather_kwargs()
        self.assertEqual(kwargs['stationary_mobile'], 'stationary')
