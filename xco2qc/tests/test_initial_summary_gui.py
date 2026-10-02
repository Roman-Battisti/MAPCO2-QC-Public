# standard library imports
import importlib.resources as ir
import shutil

# local imports
import xco2qc.core
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.external_data import ImportExternalData
from xco2qc.external_historical import ImportHistorical
from xco2qc.initial_summary_gui import InitialSummaryGUI
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.data_reduction import XCO2Reduce
from tests import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, calculate_post_xco2=True,
        chl_scale_factor=None, chl_dark_count=None, ntu_scale_factor=None,
        ntu_dark_count=None, chl_global_conversion=None,
        o2_salinity_setting=None, sbe16_mapping=False,
        deployment_number=None, historical=False, external=True
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path,
                deployment_number=deployment_number
            ) as p:
                p.run()

            if external:
                with ir.as_file(ir.files(
                    'tests.data.external.chuuk'
                    ).joinpath(
                    'seafet.satphp0094.txt'
                )) as ifile:
                    with ImportExternalData(ifile, self.raw_path) as p:
                        p.run()

            if historical:
                # These files only contain SSS and SST.
                with ir.as_file(ir.files(
                    'tests.data.external.stratus'
                    ).joinpath(
                    'historical.123.sss.txt'
                )) as ifile:
                    with ImportHistorical(ifile, self.raw_path) as p:
                        p.run()

                with ir.as_file(ir.files(
                    'tests.data.external.stratus'
                    ).joinpath(
                    'historical.234.sst.txt'
                )) as ifile:
                    with ImportHistorical(ifile, self.raw_path) as p:
                        p.run()

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

    def test_smoke(self):
        """
        SCENARIO:  Run the initial summary GUI.

        EXPECTED RESULT:  No errors.
        """

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            deployment_number=9
        )

        path = self.reduced_path

        with InitialSummaryGUI(path) as p:
            p.run()
            p.plot_features(None)

    def test_historical_display(self):
        """
        SCENARIO:  The historical file is retrieved from PMEL ERDDAP server.

        EXPECTED RESULT:  The multi-select widget should only display true
        time series variables.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh', 'dp09_0014_20131105_20140802.met.txt'
        )
        path = self.reduced_path

        # copy an ERDDAP netCDF file to where the test expects to find it
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as src:
            dst = path / xco2qc.core.HISTORICAL_NCFILE
            shutil.copyfile(src, dst)

            with InitialSummaryGUI(path) as p:
                p.run()

                historical_choices = p.gui.children[2].children[0].children[1].options  # noqa : E501

                self.assertNotIn('rowSize', historical_choices)
                self.assertNotIn('station_id', historical_choices)

    def test_historical_file_lacks_xco2_air(self):
        """
        SCENARIO:  Run the initial summary GUI.  The historical netcdf file
        is not as expected, does not have xco2_air.

        EXPECTED RESULT:  No errors.
        """

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            deployment_number=9,
            historical=True
        )

        path = self.reduced_path

        with InitialSummaryGUI(path) as p:
            p.run()
            p.plot_features(None)

    def test_internal_seafet(self):
        """
        SCENARIO:  Run the initial summary GUI.  We have internal data.

        EXPECTED RESULT:  There is a selector widget for seafet
        """

        self._processing_pipeline(
            'tests.data.mapco2.cce2.depl_09',
            'mapco2_cce2_0109_dp09_20170815_20180315.txt',
        )

        path = self.reduced_path

        with InitialSummaryGUI(path) as p:
            p.run()

            self.assertEqual(
                p.gui.children[1].children[1].children[0].value,
                'SEAFET'
            )

    def test_external_seafet(self):
        """
        SCENARIO:  Run the initial summary GUI.  We have external seafet data.

        EXPECTED RESULT:  There is a selector widget for external-seafet.
        """

        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            deployment_number=9,
            external=True
        )

        path = self.reduced_path

        with InitialSummaryGUI(path) as p:
            p.run()

            self.assertEqual(
                p.gui.children[1].children[2].children[0].value,
                'external-seafet'
            )

    def test_kilonalu_no_sbe16_channels_0_or_1(self):
        """
        SCENARIO:  Run the static summary plots.  There was no channel 0 or 1,
        so by default, there's no chl or ntu.

        EXPECTED RESULT:  No errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.kilonalu',
            'dp09_20170203_20170830.txt',
            chl_scale_factor=[9], chl_dark_count=[0.065], ntu_scale_factor=[5],
            ntu_dark_count=[0.076], chl_global_conversion=1,
            o2_salinity_setting=[0], sbe16_mapping=True
        )

        with InitialSummaryGUI(self.reduced_path) as p:
            p.run()
            p.plot_features(None)


class TestSuiteSailDrone(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, calculate_post_xco2=True,
        chl_scale_factor=None, chl_dark_count=None, ntu_scale_factor=None,
        ntu_dark_count=None, chl_global_conversion=None,
        o2_salinity_setting=None, sbe16_mapping=False,
        deployment_number=None, historical=False, external=True
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            input_dir = inputfile.parents[0]

            with RawTextToRawNC(
                input_dir, dst_dir=self.raw_path,
                deployment_number=deployment_number
            ) as p:
                p.run()

            if external:
                with ir.as_file(ir.files(
                    'tests.data.external.chuuk'
                    ).joinpath(
                    'seafet.satphp0094.txt'
                )) as ifile:
                    with ImportExternalData(ifile, self.raw_path) as p:
                        p.run()

            if historical:
                # These files only contain SSS and SST.
                with ir.as_file(ir.files(
                    'tests.data.external.stratus'
                    ).joinpath(
                    'historical.123.sss.txt'
                )) as ifile:
                    with ImportHistorical(ifile, self.raw_path) as p:
                        p.run()

                with ir.as_file(ir.files(
                    'tests.data.external.stratus'
                    ).joinpath(
                    'historical.234.sst.txt'
                )) as ifile:
                    with ImportHistorical(ifile, self.raw_path) as p:
                        p.run()

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

    def test_smoke(self):
        """
        Scenario:  run initial summary gui on saildrone data

        Expected Result:  no errors
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        path = self.reduced_path

        with InitialSummaryGUI(path) as p:
            p.run()
            p.plot_features(None)
