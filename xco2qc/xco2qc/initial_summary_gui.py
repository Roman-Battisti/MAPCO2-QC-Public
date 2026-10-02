# standard library imports
import pathlib

# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets
import matplotlib.pyplot as plt
import netCDF4
import numpy as np
import xarray as xr

# local imports
from xco2qc import core


HTML_COLUMN_WIDTH = '30%'
COMMON_BORDER = 'solid 1px'

MATPLOTLIB_BACKEND = 0
PLOTLY_BACKEND = 1


class InitialSummaryGUI(core.MapCO2core):
    """
    Create the GUI controls used by the jupyter notebook to select features
    for the initial summary.

    Attributes
    ----------
    gui : ipywidgets.VBox
        The metadata GUI
    path : path or str
        Path to directory with netCDF files.
    window : list of ipywidgets.HBox
        Each HBox has a pair of dual selectors.  Each pair has a file type
        selector and a feature list selector.  When the file type is selected,
        a callback populates the feature list with eligible data variables.
    figsize : tuple
        width and height of plots in inches
    """

    def __init__(self, path, figsize=(6, 6)):
        super().__init__()

        self.path = pathlib.Path(path)

        self.figsize = figsize

        # map the licor pump modes to simple strings for display
        self.licor_map = {
            core.licor.APOFF: 'APOFF',
            core.licor.APON: 'APON',
            core.licor.EPOFF: 'EPOFF',
            core.licor.EPON: 'EPON',
            core.licor.SPOFF: 'SPOFF',
            core.licor.SPON: 'SPON',
            core.licor.SPOSTCAL: 'SPOSTCAL',
            core.licor.ZPOFF: 'ZPOFF',
            core.licor.ZPON: 'ZPON',
            core.licor.ZPOSTCAL: 'ZPOSTCAL',
        }

        self.get_file_types()

        self._gui_rows = []

    def get_file_types(self):
        """
        Given the source directory of netCDF files, retrieve a list of file
        type labels.

        Set up top-level list of file types, plus a mapping from the file type
        label to the path of the netCDF file from whence it came.

        """
        file_types = []
        label2file = {}

        for ncfile in self.path.glob('*.nc'):

            with netCDF4.Dataset(ncfile) as nc:
                data_source = nc.data_source
                try:
                    # Licor only
                    pump_mode = nc.pump_mode.replace(' ', '-')
                except AttributeError:
                    # met, sbe16, sami, etc.
                    pump_mode = None

            if data_source == 'LICOR':
                label = self.licor_map[pump_mode]
            else:
                label = data_source

            file_types.append(label)
            label2file[label] = ncfile

        file_types = sorted(file_types)

        self.file_types = file_types
        self.label2file = label2file

    def run(self):

        self.setup_selectors()
        self.setup_plot_button()

        # Setup all the rows of the GUI, arranged as a single column.
        self.gui = widgets.VBox(self._gui_rows)

        display(self.gui)

    def setup_plot_button(self):
        """
        Below the list of feature selectors, we need a button to actually
        set forth the plottng.
        """
        button = widgets.Button(description='Plot', tooltip='Click me')
        button.on_click(self.plot_features)
        button_row = widgets.HBox([button])
        self._gui_rows.append(button_row)

    def plot_features(self, event):
        """
        Ok, the features have been selected, now collect the netcdf-file /
        variables and create the plots.

        Parameters
        ----------
        event :
            Currently unused, but is passed anyway from ipywidgets.
        """
        # the number of rows of selectors is one less than the number of rows
        # of gui elements (one row for the button)
        nrows = len(self.gui.children) - 1

        self.axes = []

        for j in range(nrows):

            # each child element is a row of selectors
            row = self.gui.children[j]

            for k in range(len(row.children)):

                # determine the file from the gui element label
                nc_elt = row.children[k]
                label = nc_elt.children[0].value
                ncfile = self.label2file[label]
                self.plot_single_variable(nc_elt, ncfile, label)

        # share the x axis between all the plots
        if len(self.axes) > 1:
            # self.axes[0].get_shared_x_axes().join(*self.axes)
            for ax in self.axes[1:]:
                try:
                    ax.sharex(self.axes[0])
                except ValueError:
                    # x axis has already been shared in a previous step
                    continue
                

    def plot_single_variable(self, nc_elt, ncfile, label):
        """
        Parameters
        ----------
        nc_elt : gui widget
            the selector
        ncfile : str
            The path to the netCDF file
        label : str
            label identifying the source
        """

        varlist = nc_elt.children[1].value

        with xr.open_dataset(ncfile) as ds:

            # If this is the historical dataset, we need to drop a few
            # variables.
            if ds.data_source == 'historical' and 'obs' in ds.coords:
                ds = ds.drop('station_id')
                ds = ds.drop('rowSize')

            for var in varlist:
                self.plot_variable(ds, var, label)

    def plot_variable(self, ds, varname, data_source):
        """
        Plot the variable.

        Parameters
        ----------
        ds : xarray.DataSet
            the netCDF file contents
        varname : str
            name of netCDF variable we wish to plot
        data_source : str
            If the source netcdf file comes from LICOR, then this is the
            pump mode, otherwise it is the data_source itself.  Use this as
            part of the figure title.
        """
        fig, ax = plt.subplots(constrained_layout=True, figsize=self.figsize)
        self.axes.append(ax)

        # If the units are unknown, they are not present as an attribute.
        # But we need something.
        try:
            units = ds[varname].units
        except AttributeError:
            units = ''
        ax.plot(ds['time'], ds[varname])
        if varname in ['ph', 'SSS']:
            # no label, people don't like the standard names table units for
            # salinity
            pass
        elif varname == 'ntu':
            ax.set_ylabel('NTU')
        else:
            ax.set_ylabel(units)

        for label in ax.get_xticklabels():
            label.set_rotation(35)
            label.set_horizontalalignment('right')

        title = f"{data_source} {varname}: {ds[varname].long_name}"
        fig.suptitle(title)
        fig.tight_layout()

    def setup_selectors(self):
        """
        Set up the rows of selectors.  Most of the time, a selector corresponds
        to a netCDF file.
        """

        selectors = []

        # Right now, we always take APOFF and EPOFF.
        ncfile = self.path / core.licor.APOFF_NCFILE
        selector = self.create_feature_box(ncfile, label='APOFF')
        selectors.append(selector)

        ncfile = self.path / core.licor.EPOFF_NCFILE
        selector = self.create_feature_box(ncfile, label='EPOFF')
        selectors.append(selector)

        ncfile = self.path / core.CYCLE_HEADER_NCFILE
        selector = self.create_feature_box(ncfile)
        selectors.append(selector)

        ncfile = self.path / core.MET_NCFILE
        if ncfile.exists():
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        ncfile = self.path / core.EXTERNAL_MET_NCFILE
        if ncfile.exists():
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        ncfile = self.path / core.DURAFET_NCFILE
        if ncfile.exists():
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        ncfile = self.path / core.SAMI_NCFILE
        if ncfile.exists():
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        ncfile = self.path / core.SEAFET_NCFILE
        if ncfile.exists():
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        ncfile = self.path / core.EXTERNAL_SEAFET_NCFILE
        if ncfile.exists():
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        ncfile = self.path / core.EXTERNAL_SAMI_NCFILE
        if ncfile.exists():
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        ncfile = self.path / core.EXTERNAL_SBE63_NCFILE
        if ncfile.exists():
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        ncfile = self.path / core.SBE16_NCFILE
        if ncfile.exists():
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        ncfile = self.path / core.HISTORICAL_NCFILE
        if ncfile.exists():
            # Make the first time series variable the default choice.
            selector = self.create_feature_box(ncfile)
            selectors.append(selector)

        layout = widgets.Layout(margin='2px', border='solid 1px')

        if len(selectors) <= 3:
            row = widgets.HBox(selectors, layout=layout)
            self._gui_rows.append(row)
        else:
            # Split the selectors into rows of 3
            for idx in range(int(np.ceil(len(selectors) / 3))):
                start = idx * 3
                stop = min((idx + 1) * 3, len(selectors))
                items = selectors[slice(start, stop)]

                row = widgets.HBox(items, layout=layout)
                self._gui_rows.append(row)

    def create_feature_box(self, ncfile, label=None):
        """
        Create a container for a file type selector and a feature selector.

        Parameters:
        -----------
        ncfile : str or path
            identifies a netCDF file
        label : str or None
            doubles as descriptive text and as a key to identify the associated
            netCDF file later on
        """

        layout = widgets.Layout(width=HTML_COLUMN_WIDTH)

        if label is None:
            with xr.open_dataset(ncfile) as ds:
                label = ds.data_source
        html = widgets.HTML(label, layout=layout)

        varlist = self.get_variable_list(ncfile)

        # Do not provide a default set of choices.
        feature_selector = widgets.SelectMultiple(
            options=varlist, value=[], description=''
        )

        layout = widgets.Layout(border=COMMON_BORDER)
        items = [html, feature_selector]
        feature_box = widgets.VBox(items, layout=layout)

        return feature_box

    def get_variable_list(self, ncfile):
        """
        We only want 1-D data variables along the unlimited dimension, usually
        "time" or "obs" in the case of PMEL ERDDAP files.
        """

        lst = []

        # If this is the PMEL ERDDAP historical file, then the list of
        # variables consists of the data variables
        with xr.open_dataset(ncfile) as ds:
            variables = list(ds.keys())

            for varname in variables:

                # Is it a QC variable?  If so, skip it.
                if (
                    hasattr(ds[varname], 'standard_name')
                    and ds[varname].standard_name == 'status_flag'
                ):
                    continue

                # Is it a time variable?  If so, skip it.
                if hasattr(ds[varname], 'calendar'):
                    continue

                # never consider these two, they are not "true" time series
                # variables
                if varname in ('rowSize', 'station_id'):
                    continue

                lst.append(varname)

        return lst
