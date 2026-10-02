# standard library imports
import importlib.resources as ir
import shutil

# 3rd party library imports
import pandas as pd

# local imports
import xco2qc
from xco2qc.external_data import ImportExternalData
from xco2qc import core
from . import test_core


class TestSuite(test_core.TestSuite):

    def setUp(self):
        super().setUp()

        with ir.as_file(ir.files(xco2qc.core.data).joinpath('default_qc_config.yml')) as path:
            shutil.copyfile(path, self.config_file)

    def test_sami(self):
        """
        SCENARIO:  The generic data import tool is given an external SAMI data
        file.

        EXPECTED RESULTS:  A raw sami netCDF file is produced.
        """
        with ir.as_file(ir.files(
            'tests.data.mapco2.stratus'
            ).joinpath(
            'sami_stratus_P0042_dp11_20180410_20190410_out.txt'
        )) as inputfile:
            with ImportExternalData(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE
            self.assertTrue(ncfile.exists())

            ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
            self.assertFalse(ncfile.exists())

            ncfile = self.raw_path / core.EXTERNAL_SBE63_NCFILE
            self.assertFalse(ncfile.exists())

    def test_sbe63(self):
        """
        SCENARIO:  The generic data import tool is given an external SBE63 data
        file.

        EXPECTED RESULTS:  A raw sbe63 netCDF file is produced.
        """
        with ir.as_file(ir.files('tests.data.mapco2.whots.depl08').joinpath('sbe63.txt')) as csvfile:
            with ImportExternalData(csvfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SBE63_NCFILE
            self.assertTrue(ncfile.exists())

            ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
            self.assertFalse(ncfile.exists())

            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE
            self.assertFalse(ncfile.exists())

    def test_sbe63_comma_delimited(self):
        """
        SCENARIO:  The generic data import tool is given an external SBE63 data
        file, comma delimited.

        EXPECTED RESULTS:  A raw sbe63 netCDF file is produced.
        """
        with ir.as_file(ir.files('tests.data.external.whots.depl12').joinpath('sbe63.txt')) as path:
            with ImportExternalData(path, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SBE63_NCFILE
            self.assertTrue(ncfile.exists())

            ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
            self.assertFalse(ncfile.exists())

            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE
            self.assertFalse(ncfile.exists())

    def test_seafet(self):
        """
        SCENARIO:  The generic data import tool is given an external SEAFET
        data file.

        EXPECTED RESULTS:  A raw met netCDF file is produced.
        """
        with ir.as_file(ir.files(
            'tests.data.external.chuuk'
            ).joinpath(
            'seafet.satphp0094.txt'
        )) as inputfile:
            with ImportExternalData(inputfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_SEAFET_NCFILE
            self.assertTrue(ncfile.exists())

            ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
            self.assertFalse(ncfile.exists())
            ncfile = self.raw_path / core.EXTERNAL_SBE63_NCFILE
            self.assertFalse(ncfile.exists())
            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE
            self.assertFalse(ncfile.exists())

    def test_met(self):
        """
        SCENARIO:  The generic data import tool is given an external MET data
        file.

        EXPECTED RESULTS:  A raw met netCDF file is produced.
        """
        with ir.as_file(ir.files('tests.data.external').joinpath('met.csv')) as csvfile:
            with ImportExternalData(csvfile, self.raw_path) as p:
                p.run()

            ncfile = self.raw_path / core.EXTERNAL_MET_NCFILE
            self.assertTrue(ncfile.exists())

            ncfile = self.raw_path / core.EXTERNAL_SBE63_NCFILE
            self.assertFalse(ncfile.exists())
            ncfile = self.raw_path / core.EXTERNAL_SAMI_NCFILE
            self.assertFalse(ncfile.exists())

    def test_excel_file(self):
        """
        SCENARIO:  The generic data import tool is given an external MET data
        file but it's in excel format.

        EXPECTED RESULTS:  RuntimeError
        """
        with ir.as_file(ir.files('tests.data.external').joinpath('met.csv')) as csvfile:

            df = pd.read_csv(csvfile)
            excel_file = self.root / 'met.xlsx'
            df.to_excel(excel_file)

            with self.assertRaises(RuntimeError):
                with ImportExternalData(excel_file, self.raw_path) as p:
                    p.run()
