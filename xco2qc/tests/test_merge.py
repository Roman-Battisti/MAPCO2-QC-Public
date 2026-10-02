# standard library imports
import importlib.resources as ir
import warnings

# 3rd party library imports
import netCDF4
import numpy as np
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.external_seafet import ImportExternalSeafet
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

    def _processing_pipeline(
        self, module, filename,
        initial_span_cal=0,
        num_points_eachside=1,
        calculate_post_xco2=True,
        sbe16_mapping=False,
        external_seafet=None
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path
            ) as p:
                p.run()

            if external_seafet is not None:
                with ir.as_file(ir.files(module).joinpath(external_seafet)) as seafet_csv:
                    with ImportExternalSeafet(seafet_csv, self.raw_path) as p:
                        p.run()

            with XCO2Reduce(
                self.raw_path, self.reduced_path, sbe16_mapping=sbe16_mapping
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

            with PostXCO2Calc(
                self.reduced_path, calculate_post_xco2=calculate_post_xco2
            ) as p:
                p.run()

            with QCChecker(
                self.reduced_path,
                initial_span_cal=initial_span_cal,
                num_points_eachside=1
            ) as p:
                p.run()

    def test_clobber_existing_file(self):
        """
        SCENARIO:  The target merge file already exists

        EXPECTED RESULT:  the existing file is clobbered, we do not error out
        """

        # Run the processing chain up until the merge.
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # Run the merge.
        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        # Now run it again.  We should not error out.
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

    def test_parent_directory_to_netcdf_file_must_exist(self):
        """
        SCENARIO:  the parent directory to the merge file does not exist

        EXPECTED RESULT:  the parent directory is created
        """
        ncfile = self.root / 'doesnotexist' / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            self.assertTrue(mp.merge_ncfile.parents[0].exists())

    def test_smoke(self):
        """
        SCENARIO:  An NH file is processed to completion.

        EXPECTED RESULT:  The datasets are verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with xr.open_dataset(ncfile) as ds:

            actual = ds['SSS'][:]
            expected = np.array([32.172267, 32.181, 32.188, 32.188])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['SST'][:]
            expected = np.array([11.46, 11.39, 11.35, 11.35])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['xco2_sw_wet'][:]
            expected = np.array([377.4918, 370.7789, 369.4921, 365.9608])
            np.testing.assert_allclose(actual, expected, rtol=1e-6)

            actual = ds['xco2_air_wet'][:]
            expected = np.array([402.2051, 401.2363, 400.5888, 400.016])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['xCO2_sw'][:]
            expected = np.array([378.2279, 371.3937, 370.1228, 366.6057])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['xCO2_air'][:]
            expected = np.array([402.7984, 401.7153, 401.073, 400.5114])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['o2_ratio'][:]
            expected = np.array([0.9963, 0.9968, 0.9971, 1.0008])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['o2_ratio_qc'][:]
            expected = np.array([
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD
            ])
            np.testing.assert_allclose(actual, expected)

            actual = ds['temperature'][:]
            expected = np.array([13.56, 14.07, 14.27, 14.31])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['atm_pressure'][:]
            expected = np.array([1028.728, 1028.501, 1028.111, 1027.858])
            np.testing.assert_allclose(actual, expected, rtol=1e-5)

            actual = ds['atm_pressure_qc'][:]
            expected = np.full((4,), core.quality.GOOD)
            np.testing.assert_allclose(actual, expected)

            actual = ds['vapor_pressure_sw'][:]
            expected = np.array([1.848418, 1.579811, 1.621606, 1.638268])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['vapor_pressure_air'][:]
            expected = np.array([1.47286, 1.1643, 1.2042, 1.23694])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['pCO2_air'][:]
            expected = np.array([403.82, 402.74953, 401.7216, 401.0726])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['pCO2_sw'][:]
            expected = np.array([379.009737, 372.1148, 370.7213, 367.1194])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['latitude'][:]
            expected = np.array([43.022, 43.022, 43.022, 43.022])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['longitude'][:]
            expected = np.array([-70.543, -70.543, -70.543, -70.543])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['fCO2_air'][:]
            expected = np.array([402.0729, 400.97, 400.1384, 399.4877])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['fCO2_sw'][:]
            expected = np.array([377.556, 370.6812, 369.28, 365.6662])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            # verify that the QC variables exist
            for var in [
                'o2_ratio', 'SST', 'SSS',
                'xco2_sw_wet', 'xco2_air_wet',
                'xCO2_sw', 'xCO2_air',
                'fCO2_air', 'fCO2_sw'
            ]:
                qcvar = self.get_qc_mask_varname(ds, var)
                self.assertIn(qcvar, ds.variables)

            # Quality for the rest are all good.
            expected = np.array([
                core.quality.GOOD, core.quality.GOOD, core.quality.GOOD,
                core.quality.GOOD
            ])

            actual = ds['latitude_qc'][:]
            np.testing.assert_allclose(actual, expected)

            actual = ds['longitude_qc'][:]
            np.testing.assert_allclose(actual, expected)

            # Verify the site ID, site code, system number, and deployment
            # attributes.
            self.assertEqual(ds.site_code, 'NH')
            self.assertEqual(ds.site_id, 'nh')
            self.assertEqual(ds.system_number, 14)
            self.assertEqual(ds.deployment_number, -1)

            # verify that xCO2_sw has the proper flags
            actual = ds['xCO2_sw_qc'].flag_meanings
            expected = (
                'quality_good missing_data out_of_range '
                'spike_detected manually_flagged trend_stddev_out_of_range '
                'raw_stddev_out_of_range excess_pressure_off_difference '
                'air_pump_pressure_difference '
                'equilibriator_pump_pressure_difference '
                'span_pump_pressure_difference excess_rh_stddev '
                'excess_rh_temp_stddev out_of_span_range'
            )
            self.assertEqual(actual, expected)

    def test_seafet(self):
        """
        SCENARIO:  A CCE1 file with seafet is processed to completion.

        EXPECTED RESULT:  ph is present in the merge file
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1.depl_11',
            'mapco2_cce1_0108_dp11_20181113_20190509.txt'
        )

        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with xr.open_dataset(ncfile) as ds:
            actual = ds['pH_sw'][:]
            expected = np.array([
                8.09700, 8.09991, 8.1006, 8.09894, 8.0980, 8.09964,
                8.09847, 8.09854
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

    def test_seafet_external(self):
        """
        SCENARIO:  A CCE1 file with external seafet is processed to completion.

        EXPECTED RESULT:
            ph is present in the merge file.
            The source of the ph is verified to be external seafet.
            The qc attributes are verified to match that of external seafet.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1.depl_11',
            'mapco2_cce1_0108_dp11_20181113_20190509.txt',
            external_seafet='seafet.csv'
        )

        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with xr.open_dataset(ncfile) as ds:
            actual = ds['pH_sw'][:]
            expected = np.array([
                np.nan, 8.085, 8.086, np.nan, np.nan, np.nan, np.nan, np.nan
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            self.assertEqual(ds['pH_sw'].source, 'external-seafet')

            expected = [1, 2, 4, 8, 64, 256, 8192, 16384]
            actual = ds['pH_sw_qc'].flag_masks
            np.testing.assert_array_equal(actual, expected)

    def test_smoke_doxy(self):
        """
        SCENARIO:  A laparguera file with dissolved is processed thru the
        merge.

        EXPECTED RESULT:  DOXY is verified.  Nighttime CHL should also be
        there.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'mapco2_laparguera_0143_dp12_20180609_20190906.fixed.txt',
            sbe16_mapping=True
        )

        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with xr.open_dataset(ncfile) as ds:

            actual = ds['dissolved_oxygen'][:]
            expected = np.array([
                188.196473, 186.496686, 185.362686, 184.063436
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['chl_nighttime'][:]
            expected = np.array([np.nan, 0.4145, 0.39, np.nan])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

    def test_sbe16_mapping_but_no_o2_or_o2_temp(self):
        """
        SCENARIO:  A whots file has only channel 0 and channel 1.

        EXPECTED RESULT:  no errors
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots.depl12',
            'mapco2_whots_0132_dp12_20180922__20191011.txt',
            sbe16_mapping=True
        )

        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with xr.open_dataset(ncfile) as ds:
            self.assertNotIn('o2', ds)
            self.assertNotIn('o2_temp', ds)

    def test_merge_with_no_post_xco2(self):
        """
        SCENARIO:  An NH file is processed to completion.

        EXPECTED RESULT:  Results are the same as the smoke test, but the pre
        xco2 is substituted for the post xco2, so those results are different.
        There is no vapor pressure.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            calculate_post_xco2=False
        )

        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with xr.open_dataset(ncfile) as ds:

            actual = ds['SSS'][:]
            expected = np.array([32.172267, 32.181, 32.188, 32.188])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['SST'][:]
            expected = np.array([11.46, 11.39, 11.35, 11.35])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['xco2_sw_wet'][:]
            expected = np.array([377.5325, 370.6768, 369.4493, 366.0832])
            np.testing.assert_allclose(actual, expected, rtol=1e-6)

            actual = ds['xco2_air_wet'][:]
            expected = np.array([402.2, 401.2, 400.6, 400])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['xCO2_sw'][:]
            expected = np.array([378.2279, 371.3937, 370.1228, 366.6057])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['xCO2_air'][:]
            expected = np.array([402.7984, 401.7153, 401.0730, 400.5144])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['o2_ratio'][:]
            expected = np.array([0.9963, 0.9968, 0.9971, 1.0008])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['o2_ratio_qc'][:]
            expected = np.array([
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD,
                core.quality.GOOD
            ])
            np.testing.assert_allclose(actual, expected)

            actual = ds['temperature'][:]
            expected = np.array([13.56, 14.07, 14.27, 14.31])
            np.testing.assert_allclose(actual, expected, rtol=1e-3)

            actual = ds['atm_pressure'][:]
            expected = np.array([1028.728, 1028.501, 1028.111, 1027.858])
            np.testing.assert_allclose(actual, expected, rtol=1e-5)

            actual = ds['atm_pressure_qc'][:]
            expected = np.full((4,), core.quality.GOOD)
            np.testing.assert_allclose(actual, expected)

            # vapor pressure should still be there
            self.assertIn('vapor_pressure_air', ds)
            self.assertIn('vapor_pressure_sw', ds)

            actual = ds['latitude'][:]
            expected = np.array([43.022, 43.022, 43.022, 43.022])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['longitude'][:]
            expected = np.array([-70.543, -70.543, -70.543, -70.543])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            # verify that the QC variables exist
            for var in [
                'o2_ratio', 'SST', 'SSS',
                'xco2_sw_wet', 'xco2_air_wet',
                'xCO2_sw', 'xCO2_air',
            ]:
                qcvar = self.get_qc_mask_varname(ds, var)
                self.assertIn(qcvar, ds.variables)

            # Quality for the rest are all good.
            expected = np.array([
                core.quality.GOOD, core.quality.GOOD, core.quality.GOOD,
                core.quality.GOOD
            ])

            actual = ds['latitude_qc'][:]
            np.testing.assert_allclose(actual, expected)

            actual = ds['longitude_qc'][:]
            np.testing.assert_allclose(actual, expected)

    def test_missing_met_section(self):
        """
        SCENARIO:  An NH file is processed to completion, but the met data
        is missing all but the last section.

        EXPECTED RESULT:  The datasets are verified.  The data re-alignment of
        salinity fills the 3rd location, but the 1st two are empty.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.missing_3.txt'
        )

        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            with warnings.catch_warnings():
                # suppress a runtimewarning due to invalid data
                warnings.simplefilter('ignore', category=RuntimeWarning)
                mp.run()

        with xr.open_dataset(ncfile) as ds:

            actual = ds['SSS'][:]
            expected = np.array([np.nan, np.nan, 32.188, 32.188133])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['SSS_qc'][:]
            expected = np.array([
                core.quality.MISSING_DATA, core.quality.MISSING_DATA,
                core.quality.GOOD, core.quality.GOOD
            ])
            np.testing.assert_allclose(actual, expected)

            actual = ds['fCO2_sw_qc'][:]
            expected = np.array([
                core.quality.MISSING_DATA, core.quality.MISSING_DATA,
                core.quality.GOOD, core.quality.GOOD
            ])
            np.testing.assert_allclose(actual, expected)

            actual = ds['xco2_sw_wet'][:]
            expected = np.array([377.4918, 370.7789, 369.4921, 365.9608])
            np.testing.assert_allclose(actual, expected, rtol=1e-6)

    def test_nh_bad_gps(self):
        """
        SCENARIO:  An NH file is processed to completion.  There is a bad GPS
        datum.

        EXPECTED RESULT:  The bad QC does NOT result in the xCO2 QC being
        flagged.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        # Fake a bad GPS reading
        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        qc = np.array([
            core.quality.MANUALLY_FLAGGED, core.quality.GOOD,
            core.quality.GOOD, core.quality.GOOD
        ])
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            nc['latitude_qc'][:] = qc
            nc['longitude_qc'][:] = qc

        # run the merge against the modified data
        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['xco2_sw_wet_qc'][:]
            actual = np.bitwise_and(actual, core.quality.BAD_GPS)

            # there should be no BAD_GPS
            expected = np.array([0, 0, 0, 0])

            np.testing.assert_allclose(actual, expected)

    def test_nh_bad_sstc_for_fugacity_and_pCO2(self):
        """
        SCENARIO:  An NH file is processed to completion.  There is a bad SSS
        and a bad SST datum (not the same).

        EXPECTED RESULT:  The out-of-range for SSST results in the fugacity
        variables having the BAD_SSTC bit set.  Same for pCO2_sw and dpCO2
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            initial_span_cal=490
        )

        # Fake the bad SSS and SST data
        # This will get shifted one index back due to the differing
        # time series between the MET file and the merge file.
        ncfile = self.reduced_path / core.MET_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            qc = np.array([
                core.quality.GOOD, core.quality.OUT_OF_RANGE,
                core.quality.GOOD, core.quality.GOOD
            ])
            nc['SSS_qc'][:] = qc

            qc = np.array([
                core.quality.GOOD, core.quality.GOOD,
                core.quality.OUT_OF_RANGE, core.quality.GOOD,
            ])
            nc['SST_qc'][:] = qc

        # run the merge against the modified data
        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with xr.open_dataset(ncfile) as ds:
            df = ds.to_dataframe()
            fCO2_air_qc = df['fCO2_air_qc'].astype(np.uint32)
            fCO2_sw_qc = df['fCO2_sw_qc'].astype(np.uint32)
            pCO2_air_qc = df['pCO2_air_qc'].astype(np.uint32)
            pCO2_sw_qc = df['pCO2_sw_qc'].astype(np.uint32)

        # fugacity
        actual = np.bitwise_and(fCO2_air_qc, core.quality.BAD_SSTC)
        expected = np.array([
            core.quality.BAD_SSTC, core.quality.BAD_SSTC, 0, 0
        ])
        np.testing.assert_allclose(actual, expected)

        actual = np.bitwise_and(fCO2_sw_qc, core.quality.BAD_SSTC)
        expected = np.array([
            core.quality.BAD_SSTC, core.quality.BAD_SSTC, 0, 0
        ])
        np.testing.assert_allclose(actual, expected)

        # pCO2
        actual = np.bitwise_and(pCO2_air_qc, core.quality.BAD_SSTC)
        expected = np.array([
            core.quality.BAD_SSTC, core.quality.BAD_SSTC, 0, 0
        ])
        np.testing.assert_allclose(actual, expected)

        actual = np.bitwise_and(pCO2_sw_qc, core.quality.BAD_SSTC)
        expected = np.array([
            core.quality.BAD_SSTC, core.quality.BAD_SSTC, 0, 0
        ])
        np.testing.assert_allclose(actual, expected)

    def test_nh_bad_sstc(self):
        """
        SCENARIO:  An NH file is processed to completion.  There is a bad SSS
        and a bad SST datum (not the same).

        EXPECTED RESULT:  The bad QC results in the xCO2 QC being flagged
        appropriately.  Bad SSTC should NOT be reflected in the xCO2.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt',
            initial_span_cal=490
        )

        # Fake the bad SSS and SST data
        # This will get shifted one index back due to the differing
        # time series between the MET file and the merge file.
        ncfile = self.reduced_path / core.MET_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            qc = np.array([
                core.quality.GOOD, core.quality.OUT_OF_RANGE,
                core.quality.GOOD, core.quality.GOOD
            ])
            nc['SSS_qc'][:] = qc

            qc = np.array([
                core.quality.GOOD, core.quality.GOOD,
                core.quality.OUT_OF_RANGE, core.quality.GOOD,
            ])
            nc['SST_qc'][:] = qc

        # Put one bad measurement in here
        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            qc = np.array([
                core.quality.GOOD, core.quality.MANUALLY_FLAGGED,
                core.quality.GOOD, core.quality.GOOD
            ])
            nc['xco2_wet_qc'][:] = qc

        # run the merge against the modified data
        ncfile = self.merge_path / 'merged.nc'
        with XCO2Merge(self.reduced_path, ncfile) as mp:
            mp.run()

        with netCDF4.Dataset(ncfile) as nc:

            xco2qc = nc['xco2_sw_wet_qc'][:]

            actual = np.bitwise_and(xco2qc, core.quality.GOOD)
            expected = np.array([
                core.quality.GOOD, 0, core.quality.GOOD, core.quality.GOOD
            ])
            np.testing.assert_allclose(actual, expected)

            # now make sure that BAD_SSTC is NOT present.
            actual = np.bitwise_and(xco2qc, core.quality.BAD_SSTC)
            expected = np.array([0, 0, 0, 0])
            np.testing.assert_allclose(actual, expected)

    def test_nh_qc_out_of_span_range_bits(self):
        """
        SCENARIO:  An Alawai file is processed to completion.  There are
        various QC bits set in the licor files.

        EXPECTED RESULT:  The QC bits are verified in the merge file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'dp2_0110_20091108_20101028.50.txt',
            initial_span_cal=430,
            num_points_eachside=16,
        )

        # flip an OUT_OF_SPAN_RANGE flag in spostcal
        ncfile = self.reduced_path / core.licor.SPOSTCAL_NCFILE
        idx = 10
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            qc = nc['xco2_wet_qc'][:]
            qc[idx] |= core.quality.OUT_OF_SPAN_RANGE
            nc['xco2_wet_qc'][:] = qc

        # run the merge against the modified data
        with XCO2Merge(self.reduced_path, self.merge_ncfile) as mp:
            mp.run()

        with netCDF4.Dataset(self.merge_ncfile) as nc:

            for xco2_var in [
                'xco2_sw_wet_qc', 'xCO2_sw_qc',
                'xco2_air_wet_qc', 'xCO2_air_qc',
            ]:
                qc = nc[xco2_var][:]

                # verify the span range flag
                actual = np.bitwise_and(qc, core.quality.OUT_OF_SPAN_RANGE)

                # some duplicates are removed, so idx no longer tells us what
                # is bad
                expected = np.full((47,), 0)
                expected[7] = core.quality.OUT_OF_SPAN_RANGE

                np.testing.assert_allclose(actual, expected)

    def test_nh_qc_trend_stddev_bits(self):
        """
        SCENARIO:  An Alawai file is processed to completion.  There are
        various QC bits set in the licor files.

        EXPECTED RESULT:  The TREND STDDEV QC bits are verified in the merge
        file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'dp2_0110_20091108_20101028.50.txt',
            initial_span_cal=430,
            num_points_eachside=16,
        )

        # flip a TREND_STDDEV_OUT_OF_RANGE flag in apoff
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        idx = 11
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            qc = nc['xco2_wet_qc'][:]
            qc[idx] |= core.quality.TREND_STDDEV_OUT_OF_RANGE
            nc['xco2_wet_qc'][:] = qc

        # run the merge against the modified data
        with XCO2Merge(self.reduced_path, self.merge_ncfile) as mp:
            mp.run()

        with netCDF4.Dataset(self.merge_ncfile) as nc:

            qc = nc['xco2_sw_wet_qc'][:]

            # verify the trend stddev flag
            actual = np.bitwise_and(qc, core.quality.TREND_STDDEV_OUT_OF_RANGE)
            expected = np.full((47,), 0)
            expected[idx] = core.quality.TREND_STDDEV_OUT_OF_RANGE
            np.testing.assert_allclose(actual, expected)

    def test_nh_qc_raw_stddev(self):
        """
        SCENARIO:  An Alawai file is processed to completion.  There are
        various QC bits set in the licor files.

        EXPECTED RESULT:  The RAW_STDDEV QC bits are verified in the merge
        file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'dp2_0110_20091108_20101028.50.txt',
            initial_span_cal=430,
            num_points_eachside=16,
        )

        # flip a RAW_STDDEV_OUT_OF_RANGE flag in epoff
        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        idx = 12
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            qc = nc['xco2_wet_qc'][:]
            qc[idx] |= core.quality.RAW_STDDEV_OUT_OF_RANGE  # noqa : E501
            nc['xco2_wet_qc'][:] = qc

        # run the merge against the modified data
        with XCO2Merge(self.reduced_path, self.merge_ncfile) as mp:
            mp.run()

        with netCDF4.Dataset(self.merge_ncfile) as nc:

            qc = nc['xco2_sw_wet_qc'][:]

            # verify the raw stddev flag
            actual = np.bitwise_and(qc, core.quality.RAW_STDDEV_OUT_OF_RANGE)
            expected = np.full((47,), 0)
            expected[idx] = core.quality.RAW_STDDEV_OUT_OF_RANGE
            np.testing.assert_allclose(actual, expected)

    def test_nh_pressure_off_difference(self):
        """
        SCENARIO:  An Alawai file is processed to completion.  There are
        various QC bits set in the licor files.

        EXPECTED RESULT:  The MAX_PRESSURE_OFF bits are verified in the merge
        file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'dp2_0110_20091108_20101028.50.txt',
            initial_span_cal=430,
            num_points_eachside=16,
        )

        # flip a EXCESS_PRESSURE_OFF_DIFFERENCE flag in epoff
        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        idx_sw = 13
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            qc = nc['pressure_qc'][:]
            qc[idx_sw] |= core.quality.EXCESS_PRESSURE_OFF_DIFFERENCE
            nc['pressure_qc'][:] = qc
        
        # flip a AIR_PUMP_PRESSURE_DIFFERENCE flag in apoff
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        idx_air = 14
        with netCDF4.Dataset(ncfile, mode='r+') as nc:
            qc = nc['pressure_qc'][:]
            qc[idx_air] |= core.quality.AIR_PUMP_PRESSURE_DIFFERENCE
            nc['pressure_qc'][:] = qc
        
        # run the merge against the modified data
        with XCO2Merge(self.reduced_path, self.merge_ncfile) as mp:
            mp.run()

        with netCDF4.Dataset(self.merge_ncfile) as nc:

            qc_sw = nc['xco2_sw_wet_qc'][:]
            qc_air = nc['xco2_air_wet_qc'][:]

            # verify the pressure difference flag
            actual_sw = np.bitwise_and(
                qc_sw, core.quality.EXCESS_PRESSURE_OFF_DIFFERENCE
            )
            actual_air = np.bitwise_and(
                qc_air, core.quality.AIR_PUMP_PRESSURE_DIFFERENCE
            )
            expected_sw = np.full((47,), 0)
            expected_sw[idx_sw] = core.quality.EXCESS_PRESSURE_OFF_DIFFERENCE
            np.testing.assert_allclose(actual_sw, expected_sw)
            
            expected_air = np.full((47,), 0)
            expected_air[idx_air] = core.quality.AIR_PUMP_PRESSURE_DIFFERENCE
            np.testing.assert_allclose(actual_air, expected_air)

            # there should be no GOOD quality at the idx location
            actual_sw = np.bitwise_and(qc_sw, core.quality.GOOD)
            expected_sw = 0
            self.assertEqual(actual_sw[idx_sw], expected_sw)
            
            actual_air = np.bitwise_and(qc_air, core.quality.GOOD)
            expected_air = 0
            self.assertEqual(actual_air[idx_air], expected_air)

    def test_pco2sys(self):
        """
        SCENARIO:  Calculate pH from pco2sys

        EXPECTED RESULT:  values are confirmed
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1.depl_11',
            'mapco2_cce1_0108_dp11_20181113_20190509.txt'
        )

        with XCO2Merge(self.reduced_path, self.merge_ncfile, region=2) as mp:
            mp.run()

        with netCDF4.Dataset(self.merge_ncfile) as nc:

            actual = nc['pH_pco2sys'][:]
            expected = np.array([
                8.06249, 8.064796, 8.064748, 8.065022, 8.064984, 8.064368,
                8.063962, 8.063958
            ])

            np.testing.assert_allclose(actual, expected)

    def test_durafet_ph_and_prawler_sss_sst(self):
        """
        SCENARIO:  We have durafet pH data and prawler CTD data

        EXPECTED RESULT:  The durafet pH data makes it into the merge file.
        The prawler SSS and SST makes it into the merge file.
        """
        self._processing_pipeline(
            'tests.data.mapco2.asv', 'pco2asv_sd1006.3.full.txt'
        )

        with XCO2Merge(self.reduced_path, self.merge_ncfile) as mp:
            mp.run()

        with xr.open_dataset(self.merge_ncfile) as ds:
            self.assertIn('pH_sw', ds)
            self.assertIn('SSS', ds)
            self.assertIn('SST', ds)

            self.assertEqual(ds['SSS'].source, 'prawler')
            self.assertEqual(ds['SST'].source, 'prawler')
