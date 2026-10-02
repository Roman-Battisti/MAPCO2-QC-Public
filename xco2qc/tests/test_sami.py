# standard library imports
import datetime as dt
import importlib.resources as ir
import unittest
import warnings

# 3rd party library imports
import numpy as np
import pandas as pd

# local imports
from xco2qc import core
from xco2qc import sami


class TestSuite(unittest.TestCase):

    @unittest.skip('matlab/octave code does not match vba')
    def test_smoke_ocean_observatories_initiative(self):
        """
        SCENARIO:  test the smoke case given in "Data Product Specification For
        PH of Seawater" for the ocean observatories initiative.  This is from
        a PDF found online.

        SCENARIO:  the results match up with what octave produces.  The
        document itself seems to have a mismatch of the number of records
        being tested, so octave's results are what I trust here.
        """
        with ir.as_file(ir.files('tests.data.mapco2.sami').joinpath('ooi_smoke.dat')) as inputfile:
            sami_strings = inputfile.read_text().splitlines()

        actual = sami.process_sami_strings(sami_strings)

        # This is what the matlab code tells us
        expected = {
            'date': [
                3400736699, 3400747499, 3400758299, 3400769099, 3400779899,
                3400790699
            ],
            'temperature': [
                25.92040, 25.84741, 25.80100, 25.75134, 25.73212, 25.75464
            ],
            'ph': [
                8.00792, 8.02538, 8.05459, 8.05287, 8.06366, 8.05719
            ]
        }
        expected = pd.DataFrame(expected)

        cols = ['ph', 'temperature']
        pd.testing.assert_frame_equal(
            actual[cols], expected[cols],
            check_exact=False, check_less_precise=3
        )

    def test_uninitialized_data(self):
        """
        SCENARIO:  the sami hex string is all zeros

        EXPECTED RESULTS:  the dataframe is all fill value, but the quality
        flag reflects missing data. this is because the 455 length string is
        less than the usual 465 length.
        """
        sami_data = '0' * 455

        sami_strings = [sami_data]

        actual = sami.process_sami_strings(sami_strings)

        expected = {
            'temperature': core.DEFAULT_FILLVALUE,
            'slope': core.DEFAULT_FILLVALUE,
            'r2': core.DEFAULT_FILLVALUE,
            'ph': core.DEFAULT_FILLVALUE,
            'ph_qc': core.quality.MISSING_DATA,
            'battery': core.DEFAULT_FILLVALUE,
            'sami_time': np.datetime64("NaT"),
        }
        expected = pd.DataFrame([expected])

        pd.testing.assert_frame_equal(actual, expected)

    def test_smoke(self):
        """
        SCENARIO:  use vba test case

        EXPECTED RESULTS:  the values are verified against vba results, and the
        quality flag is good
        """
        with ir.as_file(ir.files('tests.data.mapco2.sami').joinpath('smoke.dat')) as inputfile:
            text = inputfile.read_text()

        sami_data = ''.join(text.splitlines()[3:9])

        sami_strings = [sami_data]

        actual = sami.process_sami_strings(sami_strings)

        expected = {
            'temperature': 8.822861,
            'slope': -763.3398,
            'r2': 0.987917,
            'ph': 8.0167,
            'ph_qc': core.quality.GOOD,
            'battery': 10.2114,
            'sami_time': dt.datetime(
                2012, 6, 28, 6, 4, 59, tzinfo=dt.timezone.utc
            )
        }
        expected = pd.DataFrame([expected])

        pd.testing.assert_frame_equal(actual, expected, check_exact=False)

    def test_blank_absorbances_all_zero(self):
        """
        SCENARIO:  some of the blank absorbances are zero

        EXPECTED RESULTS:  temperature is set, the quality variable is set for
        flagged input, but the rest of the dataframe is fill value
        """
        with ir.as_file(ir.files('tests.data.mapco2.sami').joinpath('smoke.dat')) as inputfile:
            text = inputfile.read_text()

        sami_data = ''.join(text.splitlines()[3:9])

        # set false ref values (the denominator in the blank absorbances)
        sami_data = sami_data[:27] + '0000' + sami_data[31:]

        sami_strings = [sami_data]

        actual = sami.process_sami_strings(sami_strings)

        expected = {
            'temperature': 8.822861,
            'slope': core.DEFAULT_FILLVALUE,
            'r2': core.DEFAULT_FILLVALUE,
            'ph': core.DEFAULT_FILLVALUE,
            'ph_qc': core.quality.INVALID_434_578_MEASUREMENT,
            'battery': 10.2114,
            'sami_time': dt.datetime(2012, 6, 28, 6, 4, 59, tzinfo=dt.timezone.utc)  # noqa : E501
        }
        expected = pd.DataFrame([expected])

        pd.testing.assert_frame_equal(actual, expected)

    def test_zero_blank434(self):
        """
        SCENARIO:  the blank 434 value is zero

        EXPECTED RESULTS:  temperature is set, the quality variable is set for
        flagged input, but the rest of the dataframe is fill value
        """
        with ir.as_file(ir.files('tests.data.mapco2.sami').joinpath('smoke.dat')) as inputfile:
            text = inputfile.read_text()

        sami_data = ''.join(text.splitlines()[3:9])

        # set false sig values (the numerator in the blank434 absorbance
        # calculation
        sami_data = sami_data[:23] + '0000' + sami_data[27:]
        sami_data = sami_data[:39] + '0000' + sami_data[43:]
        sami_data = sami_data[:55] + '0000' + sami_data[59:]
        sami_data = sami_data[:71] + '0000' + sami_data[75:]

        sami_strings = [sami_data]

        with warnings.catch_warnings(record=True) as w:
            actual = sami.process_sami_strings(sami_strings)
            self.assertEqual(len(w), 0)

        expected = {
            'temperature': 8.822861,
            'slope': core.DEFAULT_FILLVALUE,
            'r2': core.DEFAULT_FILLVALUE,
            'ph': core.DEFAULT_FILLVALUE,
            'ph_qc': core.quality.INVALID_434_578_MEASUREMENT,
            'battery': 10.2114,
            'sami_time': dt.datetime(2012, 6, 28, 6, 4, 59, tzinfo=dt.timezone.utc)  # noqa : E501
        }
        expected = pd.DataFrame([expected])

        pd.testing.assert_frame_equal(actual, expected)

    def test_zero_blank578(self):
        """
        SCENARIO:  the blank 578 value is zero

        EXPECTED RESULTS:  temperature is set, the quality variable is set for
        flagged input, but the rest of the dataframe is fill value
        """
        with ir.as_file(ir.files('tests.data.mapco2.sami').joinpath('smoke.dat')) as inputfile:
            text = inputfile.read_text()

        sami_data = ''.join(text.splitlines()[3:9])

        # set false sig values (the numerator in the blank578 absorbance
        # calculation
        sami_data = sami_data[:31] + '0000' + sami_data[35:]
        sami_data = sami_data[:47] + '0000' + sami_data[51:]
        sami_data = sami_data[:63] + '0000' + sami_data[67:]
        sami_data = sami_data[:79] + '0000' + sami_data[83:]

        sami_strings = [sami_data]

        actual = sami.process_sami_strings(sami_strings)

        expected = {
            'temperature': 8.822861,
            'slope': core.DEFAULT_FILLVALUE,
            'r2': core.DEFAULT_FILLVALUE,
            'ph': core.DEFAULT_FILLVALUE,
            'ph_qc': core.quality.INVALID_434_578_MEASUREMENT,
            'battery': 10.2114,
            'sami_time': dt.datetime(2012, 6, 28, 6, 4, 59, tzinfo=dt.timezone.utc)  # noqa : E501
        }
        expected = pd.DataFrame([expected])

        pd.testing.assert_frame_equal(actual, expected)

    def test_zero_denominator_a434_absorbance(self):
        """
        SCENARIO:  the a434 absorbance calculation has a zero denominator, but
        that observation is thrown out and we still get a good calculation

        EXPECTED RESULTS:  the data is good, verified
        """
        with ir.as_file(ir.files('tests.data.mapco2.sami').joinpath('smoke.dat')) as inputfile:
            text = inputfile.read_text()

        sami_data = ''.join(text.splitlines()[3:9])

        # fake a zero value
        sami_data = sami_data[:83] + '0000' + sami_data[87:]

        sami_strings = [sami_data]

        actual = sami.process_sami_strings(sami_strings)

        expected = {
            'temperature': 8.822861,
            'slope': -763.339769,
            'r2': 0.987917,
            'ph': 8.016742,
            'ph_qc': core.quality.GOOD,
            'battery': 10.2114,
            'sami_time': dt.datetime(2012, 6, 28, 6, 4, 59, tzinfo=dt.timezone.utc)  # noqa : E501
        }
        expected = pd.DataFrame([expected])

        pd.testing.assert_frame_equal(actual, expected)

    def test_zero_denominator_abs434(self):
        """
        SCENARIO:  the abs434 value is zero, threatens a divide by zero

        EXPECTED RESULTS:  we still get a good calculation because it's only
        the first value that is bad
        """
        with ir.as_file(ir.files('tests.data.mapco2.sami').joinpath('smoke.dat')) as inputfile:
            text = inputfile.read_text()

        sami_data = ''.join(text.splitlines()[3:9])

        # want to get a zero value for a434, implying that i434 should be the
        # same as ref434
        sami_data = sami_data[:87] + sami_data[83:87] + sami_data[91:]

        # want to get a zero value for a434blank, which implies blank434 is 1.
        # That can happen if blank434[ABCD] are all 1.
        # That can happen if sig434[abcd] are the same as ref434[abcd]
        sami_data = sami_data[:19] + sami_data[23:27] + sami_data[23:]
        sami_data = sami_data[:35] + sami_data[39:43] + sami_data[39:]
        sami_data = sami_data[:51] + sami_data[55:59] + sami_data[55:]
        sami_data = sami_data[:67] + sami_data[71:75] + sami_data[71:]

        sami_strings = [sami_data]

        actual = sami.process_sami_strings(sami_strings)

        expected = {
            'temperature': 8.822861,
            'slope': 9041.851064,
            'r2': 0.81461,
            'ph': 7.358139,
            'ph_qc': core.quality.GOOD,
            'battery': 10.2114,
            'sami_time': dt.datetime(2012, 6, 28, 6, 4, 59, tzinfo=dt.timezone.utc)  # noqa : E501
        }
        expected = pd.DataFrame([expected])

        pd.testing.assert_frame_equal(actual, expected)
