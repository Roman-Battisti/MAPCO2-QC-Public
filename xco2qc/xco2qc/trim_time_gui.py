"""
Create a jupyter notebook GUI that can select two time values to use to trim
the merged netCDF file.
"""
# standard library imports
import datetime as dt
import pathlib

# 3rd party library imports
from IPython.display import display
from ipywidgets.widgets import NaiveDatetimePicker, VBox, HBox
import xarray as xr

# local imports
from xco2qc import core


class TimeGUI(core.MapCO2core):
    """
    Create the GUI controls used by the jupyter notebook to QC the xco2 data.

    Attributes
    ----------
    ts : pandas.Series
        the netCDF file time series
    """

    def __init__(self, reduced_path):
        """
        Parameters
        ----------
        reduced_path : path or str
            directory of netCDF files
        """
        super().__init__()
        self.gui = None
        self.reduced_path = pathlib.Path(reduced_path)

    def run(self):

        beginning, end = self.determine_timeseries_bounds()
        self.beginning_datetime = beginning
        self.ending_datetime = end

        # Setup the GUI
        self._rows = []

        self.setup_beginning_datetime_gui()
        self.setup_ending_datetime_gui()

        self.gui = VBox(self._rows)

        display(self.gui)

    def determine_timeseries_bounds(self):
        """
        Determine a viable starting and stopping time for the trimming GUI.  We
        cannot just use the cycle headers first and last timestamp because the
        netCDF files do not have the same timeseries.
        """
        beginning = []
        end = []
        for name in [
            core.CYCLE_HEADER_NCFILE,
            core.SBE16_NCFILE,
            core.MET_NCFILE,
            core.SAMI_NCFILE,
            core.licor.APOFF_NCFILE,
            core.licor.APON_NCFILE,
            core.licor.EPOFF_NCFILE,
            core.licor.EPON_NCFILE,
            core.licor.ZPOFF_NCFILE,
            core.licor.ZPON_NCFILE,
            core.licor.ZPOSTCAL_NCFILE,
            core.licor.SPOFF_NCFILE,
            core.licor.SPON_NCFILE,
            core.licor.SPOSTCAL_NCFILE,
        ]:
            ncfile = self.reduced_path / name
            if ncfile.exists():
                with xr.open_dataset(ncfile) as ds:
                    ts = ds['time'].to_series()
                    beginning.append(ts.iloc[0])
                    end.append(ts.iloc[-1])

        return min(beginning), max(end)

    def setup_beginning_datetime_gui(self):
        """
        Use a date widget along with an hour slider to get a beginning
        datetime.
        """
        beginning_date = self.beginning_datetime + dt.timedelta(days=1)

        self.beginning_datetime_picker = NaiveDatetimePicker(
            disabled=False, description='Beginning',
        )
        self.beginning_datetime_picker.value = beginning_date

        callback = self.handle_beginning_date_change
        self.beginning_datetime_picker.observe(callback, names='value')

        # And finally, group them in a row.
        box = HBox([self.beginning_datetime_picker])

        self._rows.append(box)

    def setup_ending_datetime_gui(self):
        """
        Use a date widget along with an hour slider to get a ending datetime.
        """

        # Use midnite of the day after the final to be sure we get all the
        # data.
        ending_date = self.ending_datetime + dt.timedelta(days=1)
        self.ending_datetime_picker = NaiveDatetimePicker(
            disabled=False, description='Ending',
        )
        self.ending_datetime_picker.value = ending_date

        callback = self.handle_ending_date_change
        self.ending_datetime_picker.observe(callback, names='value')

        # And finally, group them in a row.
        box = HBox([self.ending_datetime_picker])

        self._rows.append(box)

    def handle_beginning_date_change(self, change):
        """
        This callback validates the change recorded by the beginning date
        picker
        """
        beginning = self.beginning_datetime_picker.value
        ending = self.ending_datetime_picker.value

        if beginning >= ending:
            # Not allowed, set the beginning date back.
            self.beginning_datetime_picker.value = change.old
            return

    def handle_ending_date_change(self, change):
        """
        This callback validates the change recorded by the ending date
        picker
        """
        beginning = self.beginning_datetime_picker.value
        ending = self.ending_datetime_picker.value

        if beginning >= ending:
            # Not allowed, set the ending date back.
            self.ending_datetime_picker.value = change.old
            return

    def gather_kwargs(self):
        """
        Returns
        -------
        dictionary of keyword arguments for start and end time
        """
        fmt = '%Y-%m-%dT%H:%M:%S'
        start = self.beginning_datetime_picker.value.strftime(fmt)
        end = self.ending_datetime_picker.value.strftime(fmt)
        kwargs = {'start': start, 'stop': end}
        return kwargs
