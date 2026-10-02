# standard library imports
import importlib.resources as ir

# 3rd party library imports
import netCDF4
import numpy as np
import pandas as pd

# local imports
from xco2qc import core
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.manual_qc_regression import ManualRegressionQC
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.static_initial_summary_plots import StaticInitialSummaryPlots
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.merge import XCO2Merge
from xco2qc.adjustments import XCO2Adjustments
from xco2qc.socat import SocatWriter
from xco2qc.trim_netcdf import TrimXCO2netCDF
from xco2qc.socat_qc import SocatQC
from xco2qc.metadata_conventions import MetadataWriter
from xco2qc.socat_ph import PHSocatWriter
import tests.test_core


class TestSuite(tests.test_core.TestSuite):

    def _processing_chain(
        self, module, filename,
        spanconc=0, loss_of_span=False,
        mbl_correction=0.0,
        models_file=None,
        num_points_eachside=1,
        mobility='stationary'
    ):

        cycle_header_ncfile = (
            self.reduced_path / core.CYCLE_HEADER_NCFILE
        )

        # Run the processing up until xco2 computations
        with ir.as_file(ir.files(module).joinpath(filename)) as inputfile:

            with RawTextToRawNC(inputfile, dst_dir=self.raw_path) as p0:
                p0.run()

            with XCO2Reduce(self.raw_path, self.reduced_path) as p1:
                p1.run()

            if loss_of_span:
                # Rewrite the loss of span flag appropriately.
                with netCDF4.Dataset(cycle_header_ncfile, mode='r+') as nc:
                    nc['span_flag'][2:] = np.uint8(255)

            with PreXCO2Calc(self.reduced_path) as p2:
                p2.run()

            with StaticInitialSummaryPlots(self.reduced_path) as p:
                p.run()

            with TrimXCO2netCDF(self.reduced_path, self.trimmed_path) as p:
                p.run()

            with ManualRegressionQC(
                self.trimmed_path, models_file=models_file
            ) as p:
                p.run()

            with PostXCO2Calc(self.trimmed_path) as p3:
                p3.run()

            with QCChecker(
                self.trimmed_path,
                initial_span_cal=spanconc,
                num_points_eachside=num_points_eachside
            ) as p4:
                p4.run()

            with XCO2Merge(self.trimmed_path, self.merge_ncfile) as m:
                m.run()

            with SocatQC(ncfile=self.merge_ncfile) as p:
                p.run()

            with MetadataWriter(self.merge_ncfile, stationary_mobile=mobility) as m:
                m.run()

            with SocatWriter(
                ncfile=self.merge_ncfile,
                xmlfile=self.socat_xml_file,
                csvfile=self.socat_csv_file,
            ) as p:
                p.run()

            with SocatQC(ncfile=self.merge_ncfile) as p:
                p.run()

            with XCO2Adjustments(
                self.trimmed_path, self.merge_ncfile,
                mbl_correction=mbl_correction
            ) as mp:
                mp.run()

    def test_smoke(self):
        """
        SCENARIO:  Generate the socat XML, CSV files.  This is a case where we
        know we have good SAMI PH.

        EXPECTED RESULT:  The licor pressure correction value is found in the
        XML file.
        """
        
        self._processing_chain(
            'tests.data.mapco2.stratus',
            '0156_dp11_20180410_20190424.4.txt'
        )
        
        with PHSocatWriter(
            ncfile=self.merge_ncfile, csvfile=self.socat_csv_file / 'Stratus_85W_20S_Jun2018_Jun2018.csv'
        ) as p:
            p.run()
        
        df = pd.read_csv(self.socat_csv_file / 'Stratus_85W_20S_Jun2018_Jun2018.csv', index_col=None, skiprows=4)

        expected = pd.Series(
            [8.103380, 8.061230, 8.058725, 8.060641], name='pH (total scale)'
        )
        pd.testing.assert_series_equal(df[core.socat.PH], expected)
