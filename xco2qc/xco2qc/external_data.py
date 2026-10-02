"""
This module tries to load an external CSV data file, which can be either SAMI,
MET, or SBE63.
"""

# standard library imports
import pathlib

# local imports
from xco2qc import core
from xco2qc.external_met import ImportExternalMET
from xco2qc.external_sbe63 import ImportExternalSBE63
from xco2qc.external_sami import ImportExternalSAMI
from xco2qc.external_seafet import ImportExternalSeafet


class ImportExternalData(core.MapCO2core):
    def __init__(self, csvfile, dst_dir, **kwargs):
        super().__init__(
            dst_dir=dst_dir, logger_name='import_external_data', **kwargs
        )

        self.csvfile = pathlib.Path(csvfile)

    def run(self):

        # Don't run if given a directory
        if self.csvfile.is_dir():
            self.logger.info("No external data will be imported.")
            return

        # It must be a CSV file.
        try:
            with self.csvfile.open() as f:
                text = f.read(1000).lower()

        except UnicodeDecodeError as e:
            msg = (
                f"An error was encountered trying to read {self.csvfile}.  "
                f"Check that the file is a tab-delimited CSV file.  "
                f"The original error was"
                f"\n\n"
                f"{e}"
            )
            raise RuntimeError(msg)

        if 'satfhr' in text:
            self.logger.info('Importing external seafet data...')
            with ImportExternalSeafet(
                self.csvfile, self.dst_dir
            ) as p:
                p.run()
        elif 'sc_o2_umolkg' in text:
            self.logger.info('Importing external SBE63 data...')
            with ImportExternalSBE63(self.csvfile, self.dst_dir) as p:
                p.run()
        elif 'sami2-ph' in text:
            self.logger.info('Importing external SAMI data...')
            with ImportExternalSAMI(self.csvfile, self.dst_dir) as p:
                p.run()
        elif (
            'SSS' in text
            or 'sss' in text
            or 'salinity' in text
            or 'SST' in text
            or 'sst' in text
            or 'temp' in text
            or 'temperature' in text
        ):
            self.logger.info('Importing external met data...')
            with ImportExternalMET(self.csvfile, self.dst_dir) as p:
                p.run()
