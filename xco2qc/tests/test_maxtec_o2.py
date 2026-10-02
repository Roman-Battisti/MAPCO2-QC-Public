# standard library imports
import importlib.resources as ir
import io

# 3rd party library imports
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc.science_algorithms import percentO2_to_O2conc
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.external_met import ImportExternalMET
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.o2_concentration import CalcO2Concentration
from xco2qc import core
from . import test_core


class TestSuite(test_core.TestSuite):

    def __processing_chain(self, module, filename, external_metfile=None):

        # Run the processing up until the xco2 processing
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p0:
                p0.run()

            if external_metfile is not None:
                with ImportExternalMET(external_metfile, self.raw_path) as p:
                    p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

    def test_smoke(self):
        """
        SCENARIO:  compute o2 concentration from raw numbers

        EXPECTED RESULT:  no errors
        """
        o2 = np.array([0.21])
        sss = np.array([32.32])
        sst = np.array([13.4])
        lat = np.array([50])
        lon = np.array([-144])
        pressure = np.array([0.5])
        actual = percentO2_to_O2conc(o2, sss, sst, lat, lon, pressure)
        expected = np.array([54.622815])
        np.testing.assert_array_almost_equal(actual, expected, decimal=6)

    def test_compute_dissolved_oxygen_epoff(self):
        """
        Scenario:  compute o2 concentration from EPOFF

        Expecte Results:  no errors
        """
        self.__processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
        )

        with CalcO2Concentration(self.reduced_path) as p:
            p.run()

        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            df = ds.load().to_dataframe()

        actual = df['dissolved_oxygen']

        data = np.array([
            np.nan, np.nan,
            55.60576929864659, 55.65618950512943,
            55.71895796160648, 55.902100715399776
        ])
        expected = pd.Series(
            data, index=actual.index, name='dissolved_oxygen'
        )
        pd.testing.assert_series_equal(actual, expected)

        actual = df['dissolved_oxygen_qc'].astype(np.uint32)
        data = np.full(6, core.quality.GOOD, dtype=np.uint32)
        expected = pd.Series(
            data, index=actual.index, name='dissolved_oxygen_qc'
        )
        pd.testing.assert_series_equal(actual, expected)

    def test_compute_dissolved_oxygen_epon(self):
        """
        Scenario:  compute o2 concentration from EPON

        Expecte Results:  no errors
        """
        self.__processing_chain(
            'tests.data.mapco2.nh',
            'dp09_0014_20131105_20140802.met.txt',
        )

        with CalcO2Concentration(self.reduced_path) as p:
            p.run()

        ncfile = self.reduced_path / core.licor.EPON_NCFILE
        with xr.open_dataset(ncfile) as ds:
            df = ds.load().to_dataframe()

        actual = df['dissolved_oxygen']

        data = np.array([
            np.nan, np.nan,
            51.76592495298874, 51.79066930462432,
            51.785370119263696, 51.98959068359588
        ])
        expected = pd.Series(
            data, index=actual.index, name='dissolved_oxygen'
        )
        pd.testing.assert_series_equal(actual, expected)

        actual = df['dissolved_oxygen_qc'].astype(np.uint32)
        data = np.full(6, core.quality.GOOD, dtype=np.uint32)
        expected = pd.Series(
            data, index=actual.index, name='dissolved_oxygen_qc'
        )
        pd.testing.assert_series_equal(actual, expected)

    def test_compute_dissolved_oxygen_met_csv(self):
        """
        Scenario:  compute o2 concentration from EPON but a met CSV file must
        be provided.

        Expecte Results:  no errors
        """
        text = (
                "time,salinity,temperature\n"
                "2010-12-07 22:01:00,33,22\n"
                "2010-12-07 22:31:00,34,23\n"
        )
        metfile = io.StringIO(text)

        self.__processing_chain(
            'tests.data.mapco2.alawai',
            'dp3_0027_20101207_20120206.txt',
            external_metfile=metfile
        )

        with CalcO2Concentration(self.reduced_path) as p:
            p.run()

        ncfile = self.reduced_path / core.licor.EPON_NCFILE
        with xr.open_dataset(ncfile) as ds:
            df = ds.load().to_dataframe()

        actual = df['dissolved_oxygen']

        data = np.array([43.563294, 43.491758])
        expected = pd.Series(
            data, index=actual.index, name='dissolved_oxygen'
        )
        pd.testing.assert_series_equal(actual, expected)

        actual = df['dissolved_oxygen_qc'].astype(np.uint32)
        data = np.full(2, core.quality.GOOD, dtype=np.uint32)
        expected = pd.Series(
            data, index=actual.index, name='dissolved_oxygen_qc'
        )
        pd.testing.assert_series_equal(actual, expected)

    def test_compute_dissolved_oxygen_no_met_data_at_all(self):
        """
        Scenario:  compute o2 concentration from EPON but no met data is
        provided at all.

        Expecte Results:  no dissolved oxygen variable is created
        """
        self.__processing_chain(
            'tests.data.mapco2.alawai', 'dp3_0027_20101207_20120206.txt'
        )

        with CalcO2Concentration(self.reduced_path) as p:
            p.run()

        ncfile = self.reduced_path / core.licor.EPON_NCFILE
        with xr.open_dataset(ncfile) as ds:
            df = ds.load().to_dataframe()

        self.assertNotIn('dissolved_oxygen', df.columns)


class TestSuiteSailDrone(test_core.TestSuite):

    def _processing_chain(self, module, filename, external_metfile=None):

        # Run the processing up until the xco2 processing
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:
            input_dir = inputfile.parents[0]

            with RawTextToRawNC(
                input_dir, dst_dir=self.raw_path
            ) as p0:
                p0.run()

            if external_metfile is not None:
                with ImportExternalMET(external_metfile, self.raw_path) as p:
                    p.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

    def test_smoke(self):
        """
        Scenario:  run max-tec o2 processing on saildrone data

        Expected Result:  there is no met data, so no data is produced
        """
        self._processing_chain(
            'tests.data.saildrone',
            'saildrone-gen_6-arctic_ocs_single_beam_2021-sd1067.nc'
        )

        with CalcO2Concentration(self.reduced_path) as p:
            p.run()

        ncfile = self.reduced_path / core.licor.EPOFF_NCFILE
        with xr.open_dataset(ncfile) as ds:
            self.assertNotIn('dissolved_oxygen', ds)
