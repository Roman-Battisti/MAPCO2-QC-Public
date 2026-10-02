# standard library imports
import importlib.resources as ir

# 3rd party library imports
import pandas as pd

# local imports
from . import core


class CHLClimatology(core.MapCO2core):
    """
    PMEL excel-based climatology
    """

    def __init__(self, site_id, verbosity=None):

        super().__init__(
            require_config_in_output_directory_tree=False,
            verbosity=verbosity,
            logger_name='chl-climatology'
        )

        data_module = 'xco2qc.core.climatology.chl.data'
        excel_file = 'Performance.of.NNI.for.GMIS.Chl.xlsx'
        self.excel_climatology = ir.files(data_module).joinpath(excel_file)

        self.site_id = site_id

    def get_climatology(self):

        self.logger.debug(f'get climatology for {self.site_id}')

        df = pd.read_excel(self.excel_climatology, 'Sheet1')

        # restrict to just the rows for this site
        df = df.query(f'Site == "{self.site_id}"')

        if len(df) == 0:
            msg = f"Could not find climatology data for {self.site_id}."
            self.logger.warning(msg)
            raise KeyError(msg)

        # This is currently a time series.  Turn it into a climatology
        # The index here is the month number.
        df = df.groupby('Mon').mean(numeric_only=True)

        return df['Chl']

    def interpolate(self, ts):
        """
        Get a time series for a climatology

        Parameters
        ----------
        ts: pd.DatetimeIndex
            series of dates

        Returns
        -------
        climatology is interpolated onto the time series
        """
        # rename the index, just to make it clear
        ts.name = 'time'

        climatology = self.get_climatology()

        df = pd.DataFrame(index=ts, data={'Chl': 0.})
        df = df.reset_index()

        # replace each CHL point with the climatology value that matches
        # its month
        for month_num, month_chl_value in climatology.items():
            df.loc[df.loc[:, 'time'].dt.month == month_num, 'Chl'] = month_chl_value

        s = df.set_index('time')
        return s
