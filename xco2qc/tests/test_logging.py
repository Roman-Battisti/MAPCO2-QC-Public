"""
Test suite for the logging facility.
"""
# standard library imports
import importlib.resources as ir
import platform
import unittest

# local imports
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.file_logging import XCO2SetupLogFile
from . import test_core


class TestSuite(test_core.TestSuite):

    def _run_application(self, module, testfile, verbosity='critical'):

        with ir.as_file(ir.files(module).joinpath(testfile)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity=verbosity
            ) as p:
                p.run()

    def test_logging_to_stdout_at_INFO_level(self):
        """
        SCENARIO:  An application is run at the INFO level.

        EXPECTED RESULTS:  Log messages are verified to exist.
        """
        with self.assertLogs('xco2qc.raw2nc', level='INFO'):

            self._run_application(
                'tests.data.mapco2.nh',
                'dp09_0014_20131105_20140802.met.txt',
                verbosity='info'
            )

    @unittest.skipIf(platform.system() == 'Windows', 'See issue#46')
    def test_logging_to_file_at_INFO_level(self):
        """
        SCENARIO:  An application is run at the INFO level.

        EXPECTED RESULTS:  Log messages are verified to exist.  The log file
        should contain messages from the raw text converter.
        """
        logfile = self.root / 'log.txt'
        XCO2SetupLogFile(logfile).run()

        self._run_application(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
            verbosity='info'
        )

        with open(logfile, mode='rt') as f:
            logdata = f.read()
        self.assertIn('raw2nc', logdata)
