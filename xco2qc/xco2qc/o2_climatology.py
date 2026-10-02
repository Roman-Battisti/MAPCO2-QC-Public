"""
O2 Climatology for at least some of the sites.
"""
# standard library imports
import importlib.resources as ir

# 3rd party library imports
import pandas as pd

# local imports
from . import core


class O2Climatology(core.MapCO2core):
    def __init__(self, site_id, verbosity=None):
        super().__init__(verbosity=verbosity, logger_name='o2-climatology')
        self.site_id = site_id

        data_module = 'xco2qc.core.climatology.o2.data'
        excel_file = 'WOA18_Statistics_V2.xlsx'
        self.excel_climatology = ir.files(data_module).joinpath(excel_file)

    def get_climatology(self):

        df = pd.read_excel(
            self.excel_climatology, sheet_name='Stats Summary', skiprows=1
        )

        # lowercase the Site column and remove any spaces
        df['Site'] = df['Site'].str.lower()
        df['Site'] = df['Site'].str.rstrip()
        df[' Month '] = df[' Month '].str.strip()

        # restrict to just the rows for this site
        query = f"Site.str.contains('{self.site_id}')"
        df = df.query(query, engine='python')

        if len(df) == 0:
            msg = f"Could not find climatology data for {self.site_id}."
            self.logger.warning(msg)
            raise RuntimeError(msg)

        s = df['Avg O2 (umolg/kg)']
        s.index = range(1, 13)

        return s

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

        df = pd.DataFrame(index=ts, data={'O2': 0.})
        df = df.reset_index()

        # replace each O2 point with the climatology value that matches
        # its month
        for month_num, month_o2_value in climatology.items():
            df.loc[df['time'].dt.month == month_num, 'O2'] = month_o2_value

        s = df.set_index('time')
        return s
