# standard library imports
import importlib.resources as ir
import pathlib
import shutil
import tempfile

# 3rd party library imports
import netCDF4
import numpy as np
import xarray as xr

# local imports
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc import core
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_pipeline1(
        self, test_module, test_file, verbosity='critical',
    ):
        """
        Shortcut for running just the raw text conversion.
        """
        with ir.as_file(ir.files(test_module).joinpath(test_file)) as inputfile:
            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity=verbosity,
            ) as p:
                p.run()

    def _processing_pipeline(
        self, test_module, test_file, verbosity='critical',
    ):
        """
        Shortcut for running just the raw text conversion.
        """
        with ir.as_file(ir.files(test_module).joinpath(test_file)) as inputfile:
            input_dir = inputfile.parents[0]
            with RawTextToRawNC(
                input_dir,
                dst_dir=self.raw_path,
                verbosity=verbosity,
            ) as p:
                p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

    def test_smoke(self):
        """
        SCENARIO:  we have saildrone, not mapco2 text
        cycle.

        EXPECTED RESULT:  no errors.  The data source is 'MAPCO2'.
        """
        self._processing_pipeline(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        # Verify the cycle header netCDF file
        ncfile = self.reduced_path / core.CYCLE_HEADER_NCFILE
        with xr.open_dataset(ncfile) as ds:
            actual = ds['latitude'].values
            expected = np.array([57.000573, 57.013446, 57.044527])
            np.testing.assert_allclose(actual, expected, rtol=1e-6)

            self.assertEqual(ds.data_source, 'MAPCO2')
            self.assertEqual(ds.platform, 'saildrone')

        # Verify the LICOR APOFF netCDF file
        ncfile = self.reduced_path / core.licor.APOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:

            actual = ds['xco2_wet'].values
            expected = np.array([398.970481, 398.978519, 399.052111])
            np.testing.assert_allclose(actual, expected, rtol=1e-6)

            actual = ds['xco2_wet'].values
            expected = np.array([398.99, 398.99, 399.06])
            np.testing.assert_allclose(actual, expected, rtol=1e-4)

            actual = ds['xco2_dry_air_asvco2_qc'].values.astype(np.uint32)
            expected = np.array([
                core.quality.GOOD, core.quality.GOOD, core.quality.GOOD
            ])
            np.testing.assert_allclose(actual, expected, rtol=1e-6)

            self.assertEqual(ds.data_source, 'LICOR')
            self.assertEqual(ds.platform, 'saildrone')
            self.assertEqual(ds.pump_mode, 'air pump off')

    def test_no_data(self):
        """
        SCENARIO:  There is no data to mark the beginning of the cycles.

        EXPECTED RESULT:  RuntimeError
        """
        with (
            tempfile.TemporaryDirectory() as tdir,
            ir.as_file(ir.files(
                'tests.data.saildrone'
                ).joinpath(
                'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
            )) as src_ncfile,
        ):
            # create a copy of the netCDF source file
            dest_ncfile = pathlib.Path(tdir) / src_ncfile.name
            shutil.copyfile(src_ncfile, dest_ncfile)

            # alter the netCDF file to blank the critical data
            with netCDF4.Dataset(dest_ncfile, mode='r+') as nc:
                existing = nc['CO2DETECTOR_SPAN_COEFFICIENT_ASVCO2'][:]
                span_coef = np.full(existing.shape, fill_value=np.nan)
                nc['CO2DETECTOR_SPAN_COEFFICIENT_ASVCO2'][:] = span_coef

            with RawTextToRawNC(
                dest_ncfile,
                dst_dir=self.raw_path,
            ) as p:
                p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                with self.assertRaises(RuntimeError):
                    p1.run()
