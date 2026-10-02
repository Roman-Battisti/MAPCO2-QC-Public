# standard library imports

# 3rd party library imports

# local imports
from xco2qc.netcdf import NetCDFWriter
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_string_for_src_ncfile(self):
        """
        SCENARIO:  a string is passed into the constructor for the source
        netcdf file name instead of a path

        EXPECTED RESULT:  should not error out
        """
        srcfile = str(self.root / 'test.nc')
        NetCDFWriter(srcfile)
        self.assertTrue(True)
