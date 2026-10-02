# standard library imports
import datetime as dt
import importlib.resources as ir
import shutil

# 3rd party library imports
import netCDF4
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from xco2qc.metadata_conventions import MetadataWriter
from xco2qc.core import vardefs
from . import test_core


class TestSuite(test_core.TestSuite):

    def _process(
        self, module, filename, num_points_eachside=1, historical_file=None,
        citation_list=None, link_citation=None, mobility='stationary'
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p:
                p.run()

            if historical_file is not None:
                dst = self.raw_path / core.HISTORICAL_NCFILE
                shutil.copyfile(historical_file, dst)

            with XCO2Reduce(self.raw_path, self.reduced_path) as p:
                p.run()

            with PreXCO2Calc(self.reduced_path) as p:
                p.run()

            with CalcO2Concentration(self.reduced_path) as p:
                p.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with ManualRegressionQC(self.reduced_path) as p:
                p.run()

            with PostXCO2Calc(self.reduced_path) as p:
                p.run()

            with QCChecker(
                self.reduced_path, num_points_eachside=num_points_eachside
            ) as qc:
                qc.run()

            merge_ncfile = self.merge_path / 'merge.nc'
            with XCO2Merge(self.reduced_path, merge_ncfile) as p:
                p.run()

            self.metadata_attrs = {}
            self.metadata_attrs['creator_name'] = 'name'
            self.metadata_attrs['creator_type'] = 'type'
            self.metadata_attrs['creator_email'] = 'email'
            self.metadata_attrs['creator_url'] = 'url'
            self.metadata_attrs['infoUrl'] = 'url'
            self.metadata_attrs['institution'] = "c'est moi"
            self.metadata_attrs['keywords'] = 'Cheeca keywords'
            self.metadata_attrs['license'] = 'MIT'
            self.metadata_attrs['references'] = 'my references'
            self.metadata_attrs['standard_name_vocabulary'] = 'my vocab'
            self.metadata_attrs['summary'] = 'Cheeca summary'
            self.metadata_attrs['title'] = 'Cheeca rocks'
            self.metadata_attrs['stationary_mobile'] = mobility
            if citation_list is not None:
                self.metadata_attrs['contributors_citation'] = citation_list
            if link_citation is not None:
                self.metadata_attrs['link_citation'] = link_citation
            with MetadataWriter(merge_ncfile, **self.metadata_attrs) as m:
                m.run()

    def assert_OceanSITES_compliance(self, ncfile):
        """
        These checks only cherry-pick a subset of OceanSITES compliance.
        """
        with netCDF4.Dataset(ncfile) as nc:
            self.assertTrue(nc.geospatial_lon_min >= -180
                            and nc.geospatial_lon_min < 180)
            self.assertTrue(nc.geospatial_lon_max >= -180
                            and nc.geospatial_lon_max < 180)

            self.assertTrue(nc.geospatial_lat_min >= -90
                            and nc.geospatial_lat_min < 90)
            self.assertTrue(nc.geospatial_lat_max >= -90
                            and nc.geospatial_lat_max < 90)

            self.assertTrue(hasattr(nc, 'geospatial_lat_units'))
            self.assertTrue(hasattr(nc, 'geospatial_lon_units'))

            self.assertTrue(hasattr(nc, 'time_coverage_start'))
            self.assertTrue(hasattr(nc, 'time_coverage_end'))

    def assert_cf_compliance(self, ncfile):
        """
        Add any tests for CF compliance.
        """
        with netCDF4.Dataset(ncfile) as nc:
            self.assertIn('CF', nc.Conventions)

            for varname in nc.variables.keys():

                # Quality variables must have the flag values and flag meanings
                # attributes.
                if varname.endswith('_qc'):

                    qc_data = nc[varname][:]
                    if len(qc_data.compressed()) == 0:

                        # Don't bother with check if it is all fill value
                        continue

                    # All quality values must be listed in the attribute.
                    # The quality values must all be less than the maximum
                    # value of the flag masks * 2
                    flag_masks = nc[varname].flag_masks
                    max_val = flag_masks.max() * 2

                    msg = (
                        f"{qc_data.max()} not less that {max_val} "
                        f"for {varname}"
                    )
                    self.assertTrue(qc_data.max() < max_val, msg)

    def assert_acdd_compliance(self, ncfile):

        with netCDF4.Dataset(ncfile) as nc:
            self.assertIn('ACDD', nc.Conventions)
            self.assertEqual(nc.geospatial_bounds_crs, 'EPSG:4326')
            self.assertEqual(nc.cdm_data_type, "TimeSeries")
            self.assertEqual(nc.date_created, f"{dt.date.today()}")

    def assert_metadata_compliance(self, ncfile):
        """
        Verify that metadata standards are met.
        """
        self.assert_cf_compliance(ncfile)
        self.assert_OceanSITES_compliance(ncfile)
        self.assert_acdd_compliance(ncfile)

    def test__flag_masks__flag_meanings(self):
        """
        Verify that there are only single spaces in the list of flag meanings.
        Verify that there are no newlines at the end of the flag_meanings
        attribute.  Verify that the flag value count matches up with the flag
        meanings count.
        """
        for source, vars in vardefs.data_dict.items():
            for varname, metadata in vars.items():

                if (
                    'flag_masks' in metadata['attributes']
                    and 'flag_meanings' in metadata['attributes']
                ):

                    flag_masks = metadata['attributes']['flag_masks']
                    flag_meanings = metadata['attributes']['flag_meanings']

                    self.assertTrue('  ' not in flag_meanings.split())

                    self.assertEqual(
                        flag_meanings,
                        flag_meanings.rstrip(),
                        f"{source} {varname}"
                    )

                    self.assertEqual(
                        len(flag_meanings.split()),
                        len(flag_masks),
                        f"{source} {varname}"
                    )

                elif (
                    'flag_values' in metadata['attributes']
                    and 'flag_meanings' in metadata['attributes']
                ):
                    flag_values = metadata['attributes']['flag_values']
                    flag_meanings = metadata['attributes']['flag_meanings']

                    self.assertTrue('  ' not in flag_meanings.split())

                    self.assertEqual(
                        flag_meanings,
                        flag_meanings.rstrip(),
                        f"{source} {varname}"
                    )

                    self.assertEqual(
                        len(flag_meanings.split()),
                        len(flag_values),
                        f"{source} {varname}"
                    )

    def test__xco2__spostcal_span_in_range__flagging(self):
        """
        SCENARIO:

        EXPECTED RESULT:
        """
        # This is not quite enough to snare the first xco2 value, but it will
        # get the next three.
        self.config['QC']['initial_span_cal'] = 490

        self._process(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        ncfile = self.merge_path / 'merge.nc'

        with netCDF4.Dataset(ncfile) as nc:
            self.assertEqual(nc.site_code, 'NH')

        self.assert_metadata_compliance(ncfile)

    def test_historical_ncfile(self):
        """
        SCENARIO:  There is a PMEL ERDDAP historical netCDF file.

        EXPECTED RESULT:  Several ACDD attributes are copied from the
        historical file.
        """

        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._process(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.txt',
                historical_file=historical_ncfile,
                citation_list='Smith, A., B. Liu, C. Ahmed',
                link_citation='https://test.org'
            )

        merge_ncfile = self.merge_path / 'merge.nc'

        with xr.open_dataset(merge_ncfile) as ds:
            for attr_name, attr_val in self.metadata_attrs.items():
                self.assertEqual(getattr(ds, attr_name), attr_val)

            self.assertEqual(ds.time_coverage_duration, 'P0DT5H17M0S')
    
    def test_no_citation_or_link(self):
        
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._process(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.txt',
                historical_file=historical_ncfile,
            )

        merge_ncfile = self.merge_path / 'merge.nc'

        with netCDF4.Dataset(self.merge_ncfile) as nc:
            with self.assertRaises(AttributeError):
                nc.contributors_citation
            with self.assertRaises(AttributeError):
                nc.link_citation
    
    def test_mobility(self):
        
        with ir.as_file(ir.files('tests.data.netcdf').joinpath('nh.nc')) as historical_ncfile:
            self._process(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.txt',
                historical_file=historical_ncfile,
                mobility='mobile'
            )

        merge_ncfile = self.merge_path / 'merge.nc'

        with netCDF4.Dataset(self.merge_ncfile) as nc:
            self.assertEqual(nc.stationary_mobile, 'mobile')