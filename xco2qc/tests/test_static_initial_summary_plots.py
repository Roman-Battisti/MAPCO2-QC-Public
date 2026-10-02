# standard library imports
import importlib.resources as ir
import shutil

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from tests import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, historical_ncfile=None,
        chl_scale_factor=None, chl_dark_count=None, ntu_scale_factor=None,
        ntu_dark_count=None, chl_global_conversion=None,
        o2_salinity_setting=None, sbe16_mapping=False
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

    def test_smoke_no_chl_mapping(self):
        """
        SCENARIO:  Run the static summary plots.  There is no o2 mapping
        defined, so no dissolved oxygen data is produced.

        EXPECTED RESULT:  No errors.
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.txt',
                historical_ncfile=historical_ncfile
            )

        with StaticInitialSummaryPlots(self.reduced_path) as p:
            p.run()

    def test_smoke_chl_mapping_exists(self):
        """
        SCENARIO:  Run the static summary plots.  There is no o2 mapping
        defined, so no dissolved oxygen data is produced.

        EXPECTED RESULT:  No errors.
        """
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._processing_pipeline(
                'tests.data.mapco2.laparguera',
                'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
                chl_scale_factor=[9], chl_dark_count=[0.065],
                ntu_scale_factor=[5],
                ntu_dark_count=[0.076], chl_global_conversion=1,
                o2_salinity_setting=[0], sbe16_mapping=True,
                historical_ncfile=historical_ncfile
            )

        with StaticInitialSummaryPlots(self.reduced_path) as p:
            p.run()

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

        with StaticInitialSummaryPlots(self.reduced_path) as p:
            p.run()

    def test_kilonalu_no_sbe16_channels_0_and_2(self):
        """
        SCENARIO:  Run the static summary plots.  There was no channel 1 or 3,
        only 0 and 2.

        EXPECTED RESULT:  No errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.kilonalu',
            'dp09_20170203_20170830.0-2.txt',
            chl_scale_factor=[9], chl_dark_count=[0.065], ntu_scale_factor=[5],
            ntu_dark_count=[0.076], chl_global_conversion=1,
            o2_salinity_setting=[0], sbe16_mapping=True
        )

        with StaticInitialSummaryPlots(self.reduced_path) as p:
            p.run()

    def test_kilonalu_no_sbe16_channels_1_and_3(self):
        """
        SCENARIO:  Run the static summary plots.  There was no channel 0 or 2,
        only 1 and 3, so we have NTU, but no chl.

        EXPECTED RESULT:  No errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.kilonalu',
            'dp09_20170203_20170830.1-3.txt',
            chl_scale_factor=[9], chl_dark_count=[0.065], ntu_scale_factor=[5],
            ntu_dark_count=[0.076], chl_global_conversion=1,
            o2_salinity_setting=[0], sbe16_mapping=True
        )

        with StaticInitialSummaryPlots(self.reduced_path) as p:
            p.run()


class TestSuiteSailDrone(test_core.TestSuite):

    def _processing_pipeline(
        self, module, filename, historical_ncfile=None,
        chl_scale_factor=None, chl_dark_count=None, ntu_scale_factor=None,
        ntu_dark_count=None, chl_global_conversion=None,
        o2_salinity_setting=None, sbe16_mapping=False
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

    def test_smoke(self):
        """
        Scenario:  run static plot summaries on saildrone data

        Expected Result:  no errors
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        with StaticInitialSummaryPlots(self.reduced_path) as p:
            p.run()
