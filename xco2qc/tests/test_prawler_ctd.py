# standard library imports
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
        SCENARIO:  the data file has prawler CTD data

        EXPECTED RESULT:  The reduced data is verified.
        """

        self._processing_chain('tests.data.mapco2.asv', 'pco2asv_sd1006.3.txt')

        ncfile = self.reduced_path / core.PRAWLER_CTD_NCFILE
        with xr.open_dataset(ncfile) as ds:
            np.testing.assert_allclose(
                ds['temperature'],
                np.array([20.08215, 20.13532, 20.14853])
            )
            np.testing.assert_allclose(
                ds['pressure'], np.array([0.57, 0.57, 0.57])
            )
            np.testing.assert_allclose(
                ds['conductivity'],
                np.array([4.07338, 4.077169, 4.079117])
            )
            pd.testing.assert_index_equal(
                ds[core.TIME].to_index(),
                pd.DatetimeIndex([
                    '2017-08-24 06:30:00',
                    '2017-08-24 07:00:00',
                    '2017-08-24 07:30:00'
                ], name='time')
            )

    def test_section_parsing(self):
        """
        SCENARIO:  the data file has prawler CTD data and durafet.  We just
        want to make sure that the durafet data does not bleed into the ctd
        data.

        EXPECTED RESULT:  No errors.
        """
        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(
            'tests.data.mapco2.asv'
            ).joinpath(
            'ctd_with_durafet.3.txt'
        )) as inputfile:

            with RawTextToRawNC(
                inputfile, dst_dir=self.raw_path
            ) as p0:
                p0.run()
