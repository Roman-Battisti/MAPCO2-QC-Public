# standard library imports
import importlib.resources as ir

# local imports
import tests.test_core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.trim_netcdf import TrimXCO2netCDF
from xco2qc.post_trim_plots import XCO2PostTrimPlots


class TestSuite(tests.test_core.TestSuite):

    def _processing_chain(self, module, filename):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path
            ) as p0:
                p0.run()

            with XCO2Reduce(
                self.raw_path,
                self.reduced_path,
            ) as p1:
                p1.run()

            with TrimXCO2netCDF(self.reduced_path, self.trimmed_path) as p:
                p.run()

    def test_ssst(self):
        """
        SCENARIO:  The processing includes the met buffer.

        EXPECTED RESULTS:  no errors
        """

        self._processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt'
        )

        p = XCO2PostTrimPlots(self.reduced_path, self.trimmed_path)
        p.run()

    def test_no_ssst(self):
        """
        SCENARIO:  The processing does not include the met buffer.

        EXPECTED RESULTS:  no errors
        """

        self._processing_chain(
            'tests.data.mapco2.alawai',
            'dp3_0027_20101207_20120206.txt'
        )

        p = XCO2PostTrimPlots(self.reduced_path, self.trimmed_path)
        p.run()
