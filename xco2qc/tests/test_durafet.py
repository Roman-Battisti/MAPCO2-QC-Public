# standard library imports
import datetime as dt
import importlib.resources as ir

# 3rd party library imports
import numpy as np
import pandas as pd
import xarray as xr

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from . import test_core


class TestSuite(test_core.TestSuite):

    def _processing_chain(
        self, module, filename,
        verbosity='CRITICAL'
    ):

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(
                inputfile,
                dst_dir=self.raw_path,
                verbosity=verbosity
            ) as p0:
                p0.run()

            with XCO2Reduce(
                self.raw_path,
                self.reduced_path,
                verbosity=verbosity
            ) as p:
                p.run()

    def test_smoke(self):
        """
        SCENARIO:  the data file has durafet data

        EXPECTED RESULT:  The reduced data is verified.
        """

        self._processing_chain(
            'tests.data.mapco2.asv', 'ctd_with_durafet.3.txt'
        )

        # Test the raw file.
        ncfile = self.raw_path / core.DURAFET_NCFILE
        with xr.open_dataset(ncfile) as ds:
            # The "durafet_time" is an odd case, it doesn't look like it gives
            # us much.
            actual = ds['durafet_time'].to_series()

            data = np.array([
                dt.datetime(2017, 8, 23, 1, 47, 9),
                dt.datetime(2017, 8, 23, 1, 47, 9),
                dt.datetime(2017, 8, 23, 1, 47, 9),
            ], dtype='datetime64[ns]')
            expected = pd.Series(
                data,
                index=ds[core.TIME].to_series().index,
                name='durafet_time'
            )
            pd.testing.assert_series_equal(actual, expected)

        # Test the reduced file.
        ncfile = self.reduced_path / core.DURAFET_NCFILE
        with xr.open_dataset(ncfile) as ds:

            np.testing.assert_allclose(
                ds['ph_int'],
                np.array([7.994916, 7.994916, 7.994916])
            )

            np.testing.assert_allclose(
                ds['ph_ext'],
                np.array([7.988058, 7.988058, 7.988058])
            )
