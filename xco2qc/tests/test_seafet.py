# standard library imports
import importlib.resources as ir
import unittest

# 3rd party library imports
import pandas as pd

# local imports
from xco2qc import seafet


class TestSuite(unittest.TestCase):

    def test_smoke(self):
        """
        SCENARIO:  parse a SeaFET string in long format that comes from
        SeaFET-V1.

        EXPECTED RESULT:  the dataframe is validated
        """

        with ir.as_file(ir.files('tests.data.mapco2.seafet').joinpath('dabob.txt')) as p:
            txt = p.read_text()

        with ir.as_file(ir.files('tests.data.mapco2.seafet').joinpath('expected_data.h5')) as p:
            with pd.HDFStore(p) as store:
                expected = store['smoke']

        actual = seafet.process_cycle(txt)

        pd.testing.assert_frame_equal(actual, expected)

    def test_rebooting(self):
        """
        SCENARIO:  strange "rebooting data"

        EXPECTED RESULT:  None
        """

        text = (
            " Seafet D/rS"
            "Rebooting"
            "Going into operating state. "
            "Rebooting"
            "Going into operating state. "
            "Rebooting"
            "Going into operating state. End Seafet Data"
        )

        with self.assertWarns(UserWarning):
            actual = seafet.process_cycle(text)
        self.assertIsNone(actual)

    def test_short_frame(self):
        """
        SCENARIO:  Parse a short frame format section.  This example is taken
        from the seafet manual.

        EXPECTED RESULT:  the data is initialized
        """

        text = (
            "Seafet D s"
            "SATPHB0001,2014083,13.0932646,7.80829,7.78879,20.5221,20.5038,"
            "32.6027,4.669,10.523,0x0000,234\n"
            "End Seafet Data"
        )

        actual = seafet.process_cycle(text)

        expected = {
            'header': 'SATPHB0001',
            'ph_int': 7.80829,
            'ph': 7.78879,
            'temp': 20.5221,
            'temp_ctd': 20.5038,
            's_ctd': 32.6027,
            'o_ctd': 4.669,
            'p_ctd': 10.523,
            'status': 0,
            'check_sum': 234,
            'seafet_time': pd.Timestamp('2014-03-24T13:05:35.752560').as_unit('ns')
        }
        
        expected = pd.DataFrame(expected, index=[0])
        pd.testing.assert_frame_equal(actual, expected)

    def test_cce1_uninitialized(self):
        """
        SCENARIO:  Parse a SeaFET string that is all zeroes that comes from
        SeaFET-V1.

        EXPECTED RESULT:  reject the data, returns None
        """

        with ir.as_file(ir.files('tests.data.mapco2.seafet').joinpath('cce1.txt')) as p:
            txt = p.read_text()

        actual = seafet.process_cycle(txt)

        self.assertIsNone(actual)

    def test_empty(self):
        """
        SCENARIO:  Parse a SeaFET string that is completely empty.

        EXPECTED RESULT:  the return value is None
        """

        with ir.as_file(ir.files('tests.data.mapco2.seafet').joinpath('tiburon.txt')) as p:
            txt = p.read_text()

        actual = seafet.process_cycle(txt)

        self.assertIsNone(actual)
