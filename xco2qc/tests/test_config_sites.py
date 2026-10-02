# standard library tests
import importlib.resources as ir

# 3rd party library imports
import yaml

# local imports
from . import test_core


class TestSuite(test_core.TestSuite):

    def test_chuuk_k1(self):
        """
        SCENARIO:  load the site metadata for CHUUK K1

        EXPECTED RESULT:  no errors
        """

        with ir.as_file(ir.files('xco2qc.core.data').joinpath('sites.yml')) as ifile:
            d = yaml.safe_load(ifile.open())
            item = d['chuuk_k1']

        self.assertTrue(isinstance(item, dict))

    def test_coastal_la(self):
        """
        SCENARIO:  load the site metadata for COASTAL LA

        EXPECTED RESULT:  no errors
        """

        with ir.as_file(ir.files('xco2qc.core.data').joinpath('sites.yml')) as ifile:
            d = yaml.safe_load(ifile.open())
            item = d['cola']

        self.assertTrue(isinstance(item, dict))

    def test_grays_reef(self):
        """
        SCENARIO:  load the site metadata for Gray's Reef

        EXPECTED RESULT:  no errors
        """

        with ir.as_file(ir.files('xco2qc.core.data').joinpath('sites.yml')) as ifile:
            d = yaml.safe_load(ifile.open())
            item = d['ndbcga']

        self.assertTrue(isinstance(item, dict))
