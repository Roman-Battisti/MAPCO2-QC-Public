# standard library imports
import datetime as dt
import importlib.resources as ir
import io
import logging
import pathlib
import platform
import unittest

# 3rd party library imports
from dateutil.parser import parse
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr

# local imports
import xco2qc
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.raw_text_conversion import UnhandledDataStreamError
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline(
        self, test_module, test_file, verbosity='critical',
        deployment_number=None
    ):
        """
        Shortcut for running just the raw text conversion.
        """
        with ir.as_file(ir.files(test_module).joinpath(test_file)) as inputfile:
            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity=verbosity,
                deployment_number=deployment_number
            ) as p:
                p.run()

    def test_sbe16_time(self):
        """
        SCENARIO:  SBE16 time starts 6:45 = 405s after the beginning of each
        cycle.

        EXPECTED RESULT:  the cycle header times and the sbe166 times differ
        by 405 seconds.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        cycle_ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(cycle_ncfile) as nc:
            cycle_time = nc[core.TIME][:]

        sbe16_ncfile = self.raw_path / core.SBE16_NCFILE
        with netCDF4.Dataset(sbe16_ncfile) as nc:
            sbe16_time = nc[core.TIME][:]

        delta = sbe16_time - cycle_time
        expected = np.full((len(delta),), 405)
        np.testing.assert_equal(delta, expected)

    def test__no_deployment_number(self):
        """
        SCENARIO:  Read a single observation Alawai file where there is no
        deployment number provided and one cannot be taken from the filename.

        EXPECTED RESULT:  The deployment number attribute is -1.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'met.zero_sample.txt'
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            self.assertEqual(ds.deployment_number, -1)

    def test__deployment_number_in_filename(self):
        """
        SCENARIO:  The deployment number is not provided.

        EXPECTED RESULT:  The site ID is parsed from the mapco2 headers.  The
        deployment number attribute is empty.  The system number is parsed from
        the mapco2 headers.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1',
            '0108_dp11_20181113_20190509.txt',
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            self.assertEqual(nc.site_id, 'cce1')
            self.assertEqual(nc.deployment_number, 11)
            self.assertEqual(nc.system_number, 108)

    def test_bad_site_id(self):
        """
        SCENARIO:  The site ID does not match any known ID.

        EXPECTED RESULT:  A warning is printed.
        """
        expected_log_messages = [
            'WARNING:xco2qc.raw2nc:cce1_11 was not found in the list of known '
            'sites'
        ]
        with ir.as_file(ir.files(
                'tests.data.mapco2.cce1'
                ).joinpath(
                '0108_dp11_20181113_20190509.bad_site_id.txt',
        )) as inputfile:
            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity='INFO'
            ) as p:
                with self.assertLogs(p.logger, level=logging.WARNING) as cm:
                    p.run()

                    self.assertEqual(cm.output, expected_log_messages)

    def test_site_id_deployment_number(self):
        """
        SCENARIO:  The site ID and deployment number is provided.

        EXPECTED RESULT:  The netCDF files have this information stored as
        global attributes.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1',
            '0108_dp11_20181113_20190509.txt',
            deployment_number=11
        )

        ncfile = self.raw_path / core.SEAFET_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            self.assertEqual(nc.site_id, 'cce1')
            self.assertEqual(nc.deployment_number, 11)

    def test_seafet_smoke(self):
        """
        SCENARIO:  A raw file has seafet data.

        EXPECTED RESULT:  The seafet netcdf file is produced and the text data
        is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce1',
            '0108_dp11_20181113_20190509.txt'
        )

        ncfile = self.raw_path / core.SEAFET_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['time'].to_series()

            dates = [
                dt.datetime(2018, 11, 14, 9, 30),
                dt.datetime(2018, 11, 14, 12, 0),
                dt.datetime(2018, 11, 14, 15, 0),
            ]
            dates = [item for item in dates for y in range(6)]
            expected = pd.Series(dates, name='time', index=dates)
            expected.index.name = 'time'

            pd.testing.assert_series_equal(actual, expected)

            # just look at ph_int
            actual = ds['ph_int'].values

            expected = np.array([
                8.0304, 8.03012, 8.03018, 8.03065, 8.03011, 8.03028, 8.03008,
                8.03038, 8.03021, 8.03073, 8.03039, 8.03029, 8.02714, 8.02698,
                8.02701, 8.02688, 8.02727, 8.02701
            ])

            np.testing.assert_allclose(actual, expected, rtol=1e-4)

    def test_seafet_vba(self):
        """
        SCENARIO:  A raw file has seafet data in an undocumented format.

        EXPECTED RESULT:  The seafet netcdf file is produced and the text data
        is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce2.depl_09',
            'mapco2_cce2_0109_dp09_20170815_20180315.txt'
        )

        ncfile = self.raw_path / core.SEAFET_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['time'].to_series()

            dates = [
                dt.datetime(2017, 8, 15, 5, 30),
                dt.datetime(2017, 8, 15, 6, 0, 6),
                dt.datetime(2017, 8, 15, 6, 30),
                dt.datetime(2017, 8, 15, 7, 0),
            ]
            dates = [item for item in dates for y in range(6)]
            expected = pd.Series(dates, name='time', index=dates)
            expected.index.name = 'time'

            pd.testing.assert_series_equal(actual, expected)

            # just look at ph_int
            actual = ds['ph_int'].values

            expected = np.array([
                8.09744, 8.09780, 8.09800, 8.09789, 8.09738, 8.09806, 8.09683,
                8.09649, 8.09751, 8.09803, 8.09658, 8.09758, 8.09608, 8.09541,
                8.09544, 8.09509, 8.09548, 8.09588, 8.09546, 8.09470, 8.09451,
                8.09475, 8.09513, 8.09453
            ])

            np.testing.assert_allclose(actual, expected, rtol=1e-4)

    @unittest.skipIf(
        platform.system() == 'Darwin' and platform.machine() == 'arm64',
        'See issue https://github.com/pydata/xarray/issues/6191'
    )
    def test_sami_smoke(self):
        """
        SCENARIO:  A raw file has sami data.

        EXPECTED RESULT:  The sami netcdf file is produced and the text data
        is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.raw_path / core.SAMI_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['sami_time'].to_series()

            dates = [
                dt.datetime(2013, 11, 5, 18, 30),
                dt.datetime(2013, 11, 5, 19, 0),
                dt.datetime(2013, 11, 5, 19, 30),
                dt.datetime(2013, 11, 5, 20, 0),
            ]
            index = pd.DatetimeIndex(dates, name='time')
            expected = pd.Series(
                [pd.NaT] * 4, index=index, name='sami_time'
            )

            pd.testing.assert_series_equal(actual, expected)

            # validate the sami hex strings, they should all be uninitialized
            actual = ds['hex_string'].values

            expected = np.empty((4,), 'O')
            for j in range(4):
                expected[j] = '0' * 455

            np.testing.assert_array_equal(actual, expected)

    @unittest.skipIf(
        platform.system() == 'Darwin' and platform.machine() == 'arm64',
        'See issue https://github.com/pydata/xarray/issues/6191'
    )
    def test_malformed_sami_section(self):
        """
        SCENARIO:  A sami section is missing the end of sami token.  There are
        three sections, a good sami, the malformed sami, and an all-zeros
        sami.

        EXPECTED RESULT:  The sami netcdf file is produced and the text data
        is verified.  Two of the sami timestamps are NaTs.
        """
        self._processing_pipeline(
            'tests.data.mapco2.whots',
            '0179_dp11_20170727_20180928.malformed_sami.txt'
        )

        ncfile = self.raw_path / core.SAMI_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['sami_time'].to_series()

            dates = [
                dt.datetime(2018, 8, 31, 21, 0),
                dt.datetime(2018, 9, 1, 0, 0),
                dt.datetime(2018, 9, 1, 3, 0),
            ]
            index = pd.DatetimeIndex(dates, name='time')
            expected = pd.Series(
                [pd.Timestamp('2018-08-31T21:04:49'), pd.NaT, pd.NaT],
                index=index, name='sami_time'
            )

            pd.testing.assert_series_equal(actual, expected)

            # validate the sami hex strings, they should all be uninitialized
            actual = ds['hex_string'].values

            self.assertEqual(len(actual[0]), 465)
            self.assertEqual(len(actual[1]), 455)
            self.assertEqual(len(actual[2]), 455)

    def test_sami_transition(self):
        """
        SCENARIO:  The sami hex strings transition from uninitialied to
        initialized.

        EXPECTED RESULT:  Don't error out.  The sami strings have different
        lengths.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            '0143_dp12_20180609_20190906.2samistrs.txt'
        )

        ncfile = self.raw_path / core.SAMI_NCFILE
        with xr.open_dataset(ncfile) as ds:
            self.assertEqual(len(ds['hex_string'].values[0]), 455)
            self.assertEqual(len(ds['hex_string'].values[1]), 465)

    def test_missing_sami_observation(self):
        """
        SCENARIO:  One mapco2 cycle is missing the sami observation.

        EXPECTED RESULT:  there's no fill value in this case, the entire record
        gets skipped.  There are four mapco2 cycles here, so the number of
        parsed sami records is 3.
        """
        self._processing_pipeline(
            'tests.data.mapco2.stratus',
            '0156_dp11_20180410_20190424.4.missing_a_sami.txt'
        )

        ncfile = self.raw_path / core.SAMI_NCFILE
        with xr.open_dataset(ncfile) as ds:
            self.assertEqual(len(ds['hex_string']), 3)

    def test__crimp2_dp01__invalid_h3_line(self):
        """
        SCENARIO:  A raw file has what looks to be an entirely invalid header
        line 3.

        EXPECTED RESULT:  The cycle should be processed, but the header line 3
        items will all be null.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.crimp2'
            ).joinpath(
            'dp01_0009_20080417_20090608.invalid_h3.txt',
        )) as inputfile:
            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path
            ) as p:
                line = "14.2 -49330.832263 0.740974 0000"
                m = xco2qc.regex.header_line3_regex.match(line)
                d3 = p.extract_header_line_3_items(m, 3)

        for varname in [
            'battery_logic',
            'battery_trans',
            'zero_coefficient',
            'span_coefficient',
            'span_flag',
            'zero_flag'
        ]:
            self.assertTrue(np.isnan(d3[varname]))

    def test_nh_met_smoke(self):
        """
        SCENARIO:  Read a file for NH with met data.

        EXPECTED RESULT:  met data is verified.  The data_source is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.no_depl.txt'
        )

        ncfile = self.raw_path / core.MET_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # Should be three observations.
            data = nc[core.TIME][:]
            self.assertEqual(len(data), 4)

            # 3 samples of sstc, cond, sss
            self.assertEqual(nc['sstc'].shape, (4, 3, 3))

            self.assertEqual(nc.data_source, 'MET')

    def test__alawai__met_with_no_data(self):
        """
        SCENARIO:  Read a single observation Alawai file where the met buffer
        has sstc and wind buffers, but number of samples is zero.

        EXPECTED RESULT:  The met buffer is ignored since there are no
        observations.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'met.zero_sample.txt'
        )

        ncfile = self.raw_path / core.SBE16_NCFILE
        self.assertFalse(ncfile.exists())

    def test__laparguera_10__gps_lat_lon(self):
        """
        SCENARIO:  A raw mapco2 file has a valid gps data_source.

        EXPECTED RESULT:  The existance of LATITUDE and gps_longitud
        variables in output netCDF files is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            '0020_dp10_20170119_20180219.2-cycles.txt'
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # latitude
            actual = nc['latitude'][:]
            expected = np.array([0.0, 17.953733])

            actual = nc['longitude'][:]
            expected = np.array([0.0, -67.05113])
            np.testing.assert_allclose(actual, expected)

    def test__ndbcwa_09__numeric_header_mode(self):
        """
        SCENARIO:  Read a file for NDBCWA that has 3502 as a header mode, which
        was unexpected.  The Li and O2 buffers differ in their sample sizes.

        EXPECTED RESULT:  The header mode is written to file.  The Li and O2
        dimension sizes in the netCDF file are verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.ndbcwa',
            'dp01_0003_20060621_20070518.header_mode.txt'
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['mode'].getncattr('categories')
            expected = '3502'
            self.assertEqual(actual, expected)

        ncfile = self.raw_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            self.assertEqual(nc.dimensions['li_max_sample_size'].size, 58)
            self.assertEqual(nc.dimensions['o2_max_sample_size'].size, 59)
            self.assertEqual(nc.data_source, 'LICOR')

    def test__tiburon__pressure(self):
        """
        SCENARIO:  Read a file for Tiburon where the sbe16 pressure buffer has
        data.

        EXPECTED RESULT:  The pressure data is verified.  The data_source is
        verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.tiburon',
            'mapco2_tiburon_0131_dp01_20180221_20181202.pressure.txt'
        )

        ncfile = self.raw_path / core.SBE16_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['pressure'][:]

            data_source = nc.data_source

        expected = np.array([[0.96500, 0.96600, 0.976]])
        np.testing.assert_allclose(actual, expected)

        self.assertEqual(data_source, 'SBE16')

    def test__cce2_header(self):
        """
        SCENARIO:  Read a single observation CCE2 file.  The span and zero
        flags should not be interpreted as char.

        EXPECTED RESULT:  The span and zero flags are retrievable from
        any of the output netCDF files.  The span flag indicates loss of span.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cce2',
            'header.txt'
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['span_flag'][:]
            expected = np.array([255])
            np.testing.assert_allclose(actual, expected)

            actual = nc['zero_flag'][:]
            expected = np.array([0])
            np.testing.assert_allclose(actual, expected)

    def test__empty_met_section(self):
        """
        SCENARIO:  Read a file for OARC where the Met section is empty.

        EXPECTED RESULT:  Should run to completion.
        """
        self._processing_pipeline(
            'tests.data.mapco2',
            'oarc1.txt'
        )

        # There is no SBE16 data, so there should be no SBE16 file
        ncfile = self.raw_path / core.SBE16_NCFILE
        self.assertFalse(ncfile.exists())

        # Read the Excel file from which we compare data.
        with ir.as_file(ir.files('tests.data.mapco2').joinpath('oarc.xlsx')) as path:  # noqa : E501
            df = pd.read_excel(path, sheet_name='Data')

        expected_time = pd.Timestamp(df.iloc[9]['Time'])

        outputfile = self.raw_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(outputfile) as nc:
            offset = nc[core.TIME][:].data[0]
            base_time = parse(nc[core.TIME].units.split(' ')[2])
            base_time = pd.Timestamp(base_time)
            actual_time = base_time + pd.Timedelta(offset, 's')

        self.assertEqual(actual_time, expected_time)

    def test__empty_sbe_section(self):
        """
        SCENARIO:  Read a file for Alawai where the SBE section never has data.

        EXPECTED RESULT:  Should run to completion.  An SBE16 netCDF file is
        not produced.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            'no_sbe.txt'
        )

        # There is no SBE16 data, so there should be no SBE16 file
        ncfile = self.raw_path / core.SBE16_NCFILE
        self.assertFalse(ncfile.exists())

    def test__alawai_header(self):
        """
        SCENARIO:  Read a file for Alawai where the header for the next cycle
        is not matched

        EXPECTED RESULT:  Should run to completion.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            '0017_dp06_20141008_20160121.header.txt'
        )

        self.assertTrue(True)

    def test__alawai_header_line2(self):
        """
        SCENARIO:  Read a file for Alawai where the gps_qf field has no digits
        past the decimal point.

        EXPECTED RESULT:  Should run to completion.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            '0107_dp05_20130417_20140728.header_line2.txt'
        )

        self.assertTrue(True)

    def test__alawai__sbe63__lowercase(self):
        """
        SCENARIO:  Read a file for Alawai where the SBE63 buffer is lower
        cased.

        EXPECTED RESULT:  Should run to completion.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            '0107_dp05_20130417_20140728.sbe63_lowercase.txt'
        )

        self.assertTrue(True)

    def test__hogreef__sbe_channel_0_samples(self):
        """
        SCENARIO:  Read a file for Hog Reef where the SBE16 channel 1 samples
        are 5 rather than the expected 3.

        EXPECTED RESULT:  Should run to completion.
        """
        self._processing_pipeline(
            'tests.data.mapco2.hogreef',
            'mapco2_hogreef_dp1_20101129_20120227.5_sbe_samples.txt'
        )

        ncfile = self.raw_path / core.SBE16_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            data = nc['channel_0'][:]

        self.assertEqual(data.shape[1], 5)

    def test__stratus__wetlabs_has_data(self):
        """
        SCENARIO:  Read a file for Stratus where the wetlabs buffer actually
        has data.  But we don't know how to read it.

        EXPECTED RESULT:  Wetlabs data is ignored.
        """
        self._processing_pipeline(
            'tests.data.mapco2.stratus',
            'mapco2_stratus_0156_dp11_20180410_20190424.wetlabs_buffer.txt'
        )

        ncfile = self.raw_path / core.SBE16_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            self.assertTrue('Wetlabs' not in nc.variables.keys())

    def test__papa__gtd_measurement_missing_one_sample(self):
        """
        SCENARIO:  Read a file for PAPA with a GTD data stream, which is
        missing one value.

        EXPECTED RESULT:  The GTD buffer is verified with a NaN.
        """
        self._processing_pipeline(
            'tests.data.mapco2.papa',
            'dp12_0027_20180721_20190702.gtd_sample_one_nan.txt'
        )

        ncfile = self.raw_path / core.SBE16_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['gtd'][:]

        expected = np.array([[
            [13.4180, 1048.63904],
            [13.4220, 1048.40198],
            [13.4260, np.nan]
        ]])
        np.testing.assert_allclose(actual, expected)

    def test__papa__gtd_sample(self):
        """
        SCENARIO:  Read a file for PAPA with a GTD buffer

        EXPECTED RESULT:  The GTD buffer is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.papa',
            'dp12_0027_20180721_20190702.gtd_sample.txt'
        )

        ncfile = self.raw_path / core.SBE16_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            actual = nc['gtd'][:]

        expected = np.array([[
            [13.4180, 1048.63904],
            [13.4220, 1048.40198],
            [13.4260, 1048.82495]
        ]])
        np.testing.assert_allclose(actual, expected)

    def test__ndbcwa_09__bad_leading_lines(self):
        """
        SCENARIO:  Read a file for NDBCWA that has garbage leading up to the
        first header.

        EXPECTED RESULT:  The garbage is ignored and we do not error out.
        """
        self._processing_pipeline(
            'tests.data.mapco2.ndbcwa',
            'dp09_0156_20140702_20150306.leading_lines.txt'
        )

        self.assertTrue(True)

    def test__ndbcwa_dp01__no_li_buffer(self):
        """
        SCENARIO:  Read a file for NDBCWA where the Li buffer completely fails
        on the last cycle.

        EXPECTED RESULT:  Should not error out.  That last cycle is masked out.
        """
        self._processing_pipeline(
            'tests.data.mapco2.ndbcwa',
            'dp01_0003_20060621_20070518.no_li_data.txt'
        )

        ncfile = self.raw_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # look at the last time slice
            data = nc['li'][-1, :, :]

            actual = data.mask.sum()

            # 58 maximum obs for 5 variables, all masked
            expected = 58 * 5
            self.assertEqual(actual, expected)

    def test__cheeca__optode(self):
        """
        SCENARIO:  Read a file for Cheeca with optode data.

        EXPECTED RESULT:  The optode sample dimension is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.cheeca',
            'mapco2_cheeca_dp02_0024_20121208_20140224.optode.txt'
        )

        ncfile = self.raw_path / core.SBE16_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc.dimensions['optode_max_sample_size'].size
            expected = 3
            self.assertEqual(actual, expected)

    def test__laparguera__header(self):
        """
        SCENARIO:  Read a file for Laparguera.

        EXPECTED RESULT:  No errors are issued.
        """
        self._processing_pipeline(
            'tests.data.mapco2.laparguera',
            'dp3_0013_20100121_20110112.header.txt'
        )

        ncfile = self.raw_path / core.licor.APOFF_NCFILE
        self.assertTrue(ncfile.exists())

    def test__dabob__seafet_in_met(self):
        """
        SCENARIO:  Read a file for Dabob where there is Seafet data in the met
        buffer.

        EXPECTED RESULT:  the Seafet data is ignored
        """
        self._processing_pipeline(
            'tests.data.mapco2.dabob',
            'mapco2_dabob_0010_dp08_20170331_20180130.seafet.txt'
        )

        self.assertTrue(True)

    def test__kilonalu__sbe38(self):
        """
        SCENARIO:  Read a file for Kilonalu where the sbe38 data stream has
        actual values.

        EXPECTED RESULT:  We have never actually seen this yet, so we expect
        an exception to be raised.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.kilonalu'
            ).joinpath(
            'dp09_20170203_20170830.sbe38.txt'
        )) as inputfile:
            obj = RawTextToRawNC(inputfile, dst_dir=self.raw_path)
            with self.assertRaises(UnhandledDataStreamError):
                obj.run()

    def test__kilonalu__sbe50(self):
        """
        SCENARIO:  Read a file for Kilonalu where the sbe50 data stream has
        actual values.

        EXPECTED RESULT:  We have never actually seen this yet, so we expect
        an exception to be raised.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.kilonalu'
            ).joinpath(
            'dp09_20170203_20170830.sbe50.txt'
        )) as inputfile:
            obj = RawTextToRawNC(inputfile, dst_dir=self.raw_path)
            with self.assertRaises(RuntimeError):
                obj.run()

    def test__kilonalu__dual_gdt(self):
        """
        SCENARIO:  Read a file for Kilonalu where dual gdt data stream has
        actual values.

        EXPECTED RESULT:  We have never actually seen this yet, so we expect
        an exception to be raised.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.kilonalu'
            ).joinpath(
            'dp09_20170203_20170830.dual_gdt.txt'
        )) as inputfile:
            with self.assertRaises(RuntimeError):
                with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:  # noqa : E501
                    p.run()

    def test__kilonalu__sound_velocity(self):
        """
        SCENARIO:  Read a file for Kilonalu where sound velocity has actual
        values.

        EXPECTED RESULT:  We have never actually seen this yet, so we expect
        an exception to be raised.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.kilonalu'
            ).joinpath(
            'dp09_20170203_20170830.sound.txt'
        )) as inputfile:
            with self.assertRaises(RuntimeError):
                with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p:  # noqa : E501
                    p.run()

    def test__kilonalu__RH__missing_samples(self):
        """
        SCENARIO:  Read a file for Kilonalu where an observation for the RH
        variable is missing two values.  It should have 58 samples, but only
        56 are recorded.

        EXPECTED RESULT:  The 57th and 58th samples are verified to be masked.
        """
        self._processing_pipeline(
            'tests.data.mapco2.kilonalu',
            'dp09_20170203_20170830.rh_nan.txt'
        )

        ncfile = self.raw_path / core.licor.SPOSTCAL_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            np.testing.assert_allclose(
                nc['rh'][:].mask[0, 56:58], np.array([True, True])
            )

    def test__kilonalu__truncated_last_cycle(self):
        """
        SCENARIO:  Read a file for Kilonalu the last cycle is truncated between
        sensor sections.

        EXPECTED RESULT:  The licor files have two timestamps because all
        of their data is valid.  The SBE16 file has 0 observations in the
        first cycle and is missing the 2nd cycle, so it is not written.
        """
        self._processing_pipeline(
            'tests.data.mapco2.kilonalu',
            'dp04_0111_20111019_20131013.truncated_last_cycle.txt'
        )

        ncfile = self.raw_path / core.licor.SPOSTCAL_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            self.assertEqual(nc.dimensions[core.TIME].size, 2)

        ncfile = self.raw_path / core.SBE16_NCFILE
        self.assertTrue(ncfile.exists() is False)

    def test__ndbcga__truncated_last_cycle(self):
        """
        SCENARIO:  Read a file for ndbcga where the last cycle is truncated
        badly.

        EXPECTED RESULT:  Both cycles are read.  The last SBE16 cycle is
        salvageable.
        """
        self._processing_pipeline(
            'tests.data.mapco2.ndbcga',
            'mapco2_ndbcga_dp07_0003_20110930_20130123.serial_g.txt',
        )

        ncfile = self.raw_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            data = nc[core.TIME][:]

            self.assertEqual(len(data), 2)

        ncfile = self.raw_path / core.SBE16_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            data = nc[core.TIME][:]

            self.assertEqual(len(data), 2)

    def test__sbe16_variable_with_single_sample(self):
        """
        SCENARIO:  Extract a measurement from a string that has just a single
        value.  We almost always have more than one value.  This can happen
        in sbe16.

        EXPECTED RESULT:  The data is verified.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.nh'
            ).joinpath(
            'dp09_0014_20131105_20140802.met.txt'
        )) as inputfile:
            obj = RawTextToRawNC(inputfile, dst_dir=self.raw_path)
            data = obj.read_mapco2_data_buffer('0.1164', 1, n_params=1)

        np.testing.assert_allclose(data, np.array([[0.1164]]))

    def test__nh__valve_pulse__span_flag__zero_flag(self):
        """
        SCENARIO:  Read a file for NH.  The valve pulse has no data.  The span
        and zero flags should all be zero

        EXPECTED RESULT:  The valve pulse variable should be all fill values.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            actual = nc['valve_pulse'][:]
            self.assertTrue(actual.all() is np.ma.masked)

            expected = np.zeros((6, ))
            actual = nc['span_flag'][:]
            np.testing.assert_allclose(actual, expected)

            actual = nc['zero_flag'][:]
            np.testing.assert_allclose(actual, expected)

    def test__nh__licor_data_source(self):
        """
        SCENARIO:  Read a file for NH with met SSTC data.

        EXPECTED RESULT:  The data_source for the licor data files is correctly
        identified.  The pump mode attribute is verified.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        # verify the data_source attribute
        for ncfile in pathlib.Path(self.raw_path).glob('licor*.nc'):
            with netCDF4.Dataset(ncfile) as nc:
                self.assertEqual(nc.data_source, 'LICOR')

        # verify the pump mode attribute
        for ncfile in pathlib.Path(self.raw_path).glob('licor*.nc'):
            with netCDF4.Dataset(ncfile) as nc:
                if core.licor.APOFF in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'air pump off')
                elif core.licor.APON in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'air pump on')
                elif core.licor.EPOFF in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'equil pump off')
                elif core.licor.EPON in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'equil pump on')
                elif core.licor.SPOSTCAL in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'span post cal')
                elif core.licor.SPOFF in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'span pump off')
                elif core.licor.SPON in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'span pump on')
                elif core.licor.ZPOSTCAL in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'zero post cal')
                elif core.licor.ZPOFF in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'zero pump off')
                elif core.licor.ZPON in str(ncfile):
                    self.assertEqual(nc.pump_mode, 'zero pump on')
                else:
                    raise RuntimeError('Whuuuuut?  Unhandled case')

    def test__nh_dp9__truncated_last_section(self):
        """
        SCENARIO:  Read a file for NH where the last cycle is missing the start
        of the section.

        EXPECTED RESULT:  We can salvage the data, although that third
        cycle is mostly bad for Licor.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.truncated_start_of_cycle.txt'
        )

        ncfile = self.raw_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            self.assertEqual(nc.dimensions[core.TIME].size, 3)

    def test__nh_dp10__no_span2_coeff_but_firmware_vnum_gt_6(self):
        """
        SCENARIO:  A raw file has a firmware version > 6 but still has no
        span2 coefficient.

        EXPECTED RESULT:  The span2 coefficient should be given as all NaNs.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'mapco2_nh10_0129_dp02_20141011_20150317.5-item-h3-line.txt'
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            data = nc['span2_coefficient'][:]
            self.assertTrue(data.all() is np.ma.masked)

    def test__crimp2_dp09__truncated_li_buffer(self):
        """
        SCENARIO:  A raw file has its last cycle truncated in the middle of
        the Li buffer.  There is a valid cycle preceding it.

        EXPECTED RESULT:  The last cycle is discarded, so only one cycle was
        recorded.
        """
        self._processing_pipeline(
            'tests.data.mapco2.crimp2',
            'dp05_0010_20121102_20140112.truncated_li_buffer.txt'
        )

        ncfile = self.raw_path / core.licor.APOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:
            self.assertEqual(nc.dimensions[core.TIME].size, 1)

    def test__papa12__missing_entire_gtd_section(self):
        """
        SCENARIO:  A raw file has a missing GTD section in the 2nd cycle.

        EXPECTED RESULT:  The bad cycle should be processed and the GTD
        sections should be filled in with NaNs.  The number of samples
        should be set to zero.
        """
        self._processing_pipeline(
            'tests.data.mapco2.papa',
            'dp12_0027_20180721_20190702.missing_gtd_samples.txt'
        )

        ncfile = self.raw_path / core.SBE16_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # Use netCDF4's propensity for using masks to verify the data
            # itself.  The mask will be false for the entire first timestep
            # (all the data is there) and true for the 2nd (all the data is
            # missing).
            actual = nc['gtd'][:]
            self.assertEqual(actual.mask[0].sum(), 0)
            self.assertEqual(actual.mask[1].sum(), 6)

    def test__ndbcga_07__missing_two_entire_o2_sections(self):
        """
        SCENARIO:  A raw file has missing O2 sections so corrupt that
        nothing can be reasonable recovered.  The Li, RH, and Rh temp
        sections are good, though.

        EXPECTED RESULT:  The bad cycles should be processed and the O2
        sections should be filled in with NaNs.  The number of samples
        should be set to zero.
        """
        self._processing_pipeline(
            'tests.data.mapco2.ndbcga',
            'dp07_0003GA2012data.missing_2_o2_sections.txt'
        )

        ncfile = self.raw_path / core.licor.EPOFF_NCFILE
        with netCDF4.Dataset(ncfile) as nc:

            # Use netCDF4's propensity for using masks to verify the data
            # itself.  The mask will be true for the entire first and 3rd
            # timesteps and false for the others.
            actual = nc['o2'][:]
            self.assertEqual(actual.mask[0].sum(), 58)
            self.assertEqual(actual.mask[2].sum(), 58)
            self.assertEqual(actual.mask[1].sum(), 0)
            self.assertEqual(actual.mask[3].sum(), 0)
            self.assertEqual(actual.mask[4].sum(), 0)

    @unittest.skipIf(
        platform.system() == 'Darwin' and platform.machine() == 'arm64',
        'See issue https://github.com/pydata/xarray/issues/6191'
    )
    def test__xarray_compat(self):
        """
        SCENARIO:  The netCDF files must be readable by xarray,
        including all time variables.  "sys_dtime2" in this case
        has all 0000\00\00 values and should be NaT.

        EXPECTED RESULT:  All the netCDF files load without
        throwing any errors.
        """
        self._processing_pipeline(
            'tests.data.mapco2.alawai',
            '0017_dp06_20141008_20160121.header.txt'
        )

        expected = np.array(['NaT', 'NaT'], dtype='datetime64[ns]')
        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        ds = xr.open_dataset(ncfile)

        np.testing.assert_equal(
            ds['sys_dtime2'].values, expected
        )

    def test__duplicate_gps_time(self):
        """
        SCENARIO:  Read a file for NH with duplicate gps times at
        2013/11/05 19:00:00.

        EXPECTED RESULT:  The netCDF files only have monotonic
        time coordinate values, i.e. the duplicate time is thrown out.
        """
        self._processing_pipeline(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.dups.txt'
        )

        ncfile = self.raw_path / core.CYCLE_HEADER_NCFILE
        ds = xr.open_dataset(ncfile)
        expected = np.array([
            '2013-11-05T15:00:01',
            '2013-11-05T18:00:01',
            '2013-11-05T18:30:00',
            '2013-11-05T19:00:00',
            '2013-11-05T19:30:00',
            '2013-11-05T20:00:00',
        ], dtype='datetime64[ns]')
        np.testing.assert_equal(ds[core.TIME].values, expected)

    @unittest.skip('blah')
    def test_unhandled_sbe16_data_stream(self):
        """
        SCENARIO:  An unrecognized SBE16 serial data stream shows up.

        EXPECTED RESULT:  An exception is raised.
        """
        inputpath = self.raw_path / 'bogus_input.txt'
        with inputpath.open(mode='wt') as f:
            f.write("Serial XXXX samples  0")

        obj = RawTextToRawNC(inputpath, dst_dir=self.raw_path)

        with self.assertRaises(RuntimeError):
            obj.read_sbe16_section()

    def test_time_is_not_monotonic(self):
        """
        SCENARIO:  An input file does not have monotonic time.

        EXPECTED RESULT:  Errors out.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.laparguera'
            ).joinpath(
            '0143_dp12_20180609_20190906.txt'
        )) as ifile:
            with RawTextToRawNC(ifile, dst_dir=self.raw_path) as p:
                with self.assertRaises(RuntimeError):
                    p.run()

    def test_time_is_not_monotonically_increasing(self):
        """
        SCENARIO:  An input file does not have monotonically increasing time.

        EXPECTED RESULT:  Errors out.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.laparguera'
            ).joinpath(
            '0143_dp12_20180609_20190906.constant.txt'
        )) as ifile:
            with RawTextToRawNC(ifile, dst_dir=self.raw_path) as p:
                with self.assertRaises(RuntimeError):
                    p.run()

    def test_epoff_time_is_monotonic_increasing(self):
        """
        SCENARIO:  An EPOFF time is known to be monotonic increasing.

        EXPECTED RESULT:  The time series is monotonic increasing.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.alawai'
            ).joinpath(
            'dp2_0110_20091108_20101028.50.txt',
        )) as ifile:
            with RawTextToRawNC(ifile, dst_dir=self.raw_path) as p:
                p.run()

        ncfile = self.raw_path / core.licor.EPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            time = ds['time']
        idx = np.nonzero(np.diff(time).astype(np.int64) < 0)[0]

        self.assertEqual(len(idx), 0)

    def test_epoff_time(self):
        """
        SCENARIO:  An EPOFF time is known to be monotonic increasing.

        EXPECTED RESULT:  The time series is monotonic increasing.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.nh'
            ).joinpath(
            'dp09_0014_20131105_20140802.met.txt'
        )) as ifile:
            with RawTextToRawNC(ifile, dst_dir=self.raw_path) as p:
                p.run()

        ncfile = self.raw_path / core.licor.EPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            time = ds['time'].to_series()

        dti = pd.to_datetime([
            "2013/11/05 15:00:00", "2013/11/05 18:00:00",
            "2013/11/05 18:47:00", "2013/11/05 19:17:00",
            "2013/11/05 19:47:00", "2013/11/05 20:17:00",
        ])
        idx = pd.DatetimeIndex(dti, name='time')
        expected = pd.Series(dti, index=idx, name='time')
        pd.testing.assert_series_equal(time, expected)

    def test_met_wind(self):
        """
        SCENARIO:  An input raw text file has met wind where the number of
        samples is greater than 0.

        EXPECTED RESULT:  A RuntimeError is issued.  We do not know how to
        handle wind data, as we have no working examples.
        """
        sf = io.StringIO(
            "**************************************** Met Data\n"
            "SSTC samples 00\n"
            "Wind samples 0001\n"
        )

        with ir.as_file(ir.files(
            'tests.data.mapco2.laparguera'
            ).joinpath(
            '0143_dp12_20180609_20190906.txt'
        )) as ifile:
            with RawTextToRawNC(ifile, dst_dir=self.raw_path) as p:
                with self.assertRaises(RuntimeError):
                    p.parse_met_cycle(sf)

    def test_too_few_licor_measurements(self):
        """
        Scenario:  The input raw text file has a licor section with fewer than
        30 measurements.

        Expected result:  A warning is logged.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.cce1'
            ).joinpath(
            '0108_dp11_20181113_20190509.too_few_licor_measurements.txt',
        )) as ifile:
            with RawTextToRawNC(ifile, dst_dir=self.raw_path) as p:
                with self.assertLogs(p.logger, level=logging.WARNING):
                    with self.assertWarns(UserWarning):
                        p.run()
