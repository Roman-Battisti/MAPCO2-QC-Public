# standard library imports
import collections
import functools
import pathlib

# 3rd party library imports
from IPython.display import display
import ipywidgets as widgets
import netCDF4

# local imports
from xco2qc import core
from xco2qc.feature_plots import FeaturePlots


class FeaturePlotsGUI(core.MapCO2core):
    """
    Create the GUI controls used by the jupyter notebook to select features
    to plot, two at a time.

    Attributes
    ----------
    gui : ipywidgets.VBox
        The metadata GUI
    path : path or str
        Path to directory with netCDF files.
    nrows : integer
        Number of rows in the GUI
    window : list of ipywidgets.HBox
        Each HBox has a pair of dual selectors.  Each pair has a file type
        selector and a feature list selector.  When the file type is selected,
        a callback populates the feature list with eligible data variables.
    """

    def __init__(self, path, verbosity='CRIT'):
        super().__init__()

        self.path = pathlib.Path(path)

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

        self._html_box_width = '40%'
        self._html_box_border = 'solid 1px'

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

        self.nrows = 3

        self.setup_windows()
        self.setup_plot_button()

        rows = self.window + [self.button_row]
        # Setup all the rows of the GUI, arranged as a single column.
        self.gui = widgets.VBox(rows)

        display(self.gui)

    def setup_plot_button(self):
        """
        Below the list of feature selectors, we need a button to actually
        set forth the plottng.
        """
        button = widgets.Button(description='Plot', tooltip='Click me')
        button.on_click(self.plot_features)
        self.button_row = widgets.HBox([button])

    def plot_features(self, event):
        """
        Ok, the features have been selected, now collect the netcdf-file /
        data-variable pairs and create the plots.
        """
        # collect the pairs of features
        pairs = []
        for idx in range(self.nrows):
            window = self.window[idx]

            feature1 = window.children[0]
            label = feature1.children[0].value
            ncfile = self.label2file[label]
            variable = feature1.children[1].value
            pair1 = (ncfile, variable)

            feature2 = window.children[1]
            label = feature2.children[0].value
            ncfile = self.label2file[label]
            variable = feature2.children[1].value
            pair2 = (ncfile, variable)

            pairs.append((pair1, pair2))

        with FeaturePlots(self.path, pairs, verbosity=self.verbosity) as p:
            p.run()

    def setup_windows(self):
        """
        Set up the rows of paired features
        """
        self.window = []

        for row in range(self.nrows):

            feature1_box = self.create_feature_box()
            feature2_box = self.create_feature_box()

            layout = widgets.Layout(margin='2px', border='solid 1px')
            children = [feature1_box, feature2_box]
            row = widgets.HBox(children, layout=layout)
            self.window.append(row)

    def create_feature_box(self):
        """
        Create a container for a file type selector and a feature selector.
        """

        file_type_selector = widgets.Select(
            options=self.file_types, value=self.file_types[0],
            description='File Type'
        )

        feature_selector = widgets.Select(
            options=['NA'], value='NA', description='Feature'
        )

        # If a value in the file selector is chosen, the feature selector
        # needs to be updated
        callback = functools.partial(
            self.update_features, feature_selector=feature_selector
        )
        file_type_selector.observe(callback, names='value')

        layout = widgets.Layout(border='solid 1px')
        items = [file_type_selector, feature_selector]
        feature_box = widgets.HBox(items, layout=layout)

        # poke the file type selector into populating the feature selector.
        # this doesn't change the currently chosen file type.
        # the callback isn't active yet, so we will trick it.
        Change = collections.namedtuple('Change', ['old', 'new'])
        c = Change(old='NA', new=self.file_types[0])
        self.update_features(c, feature_selector=feature_selector)

        return feature_box

    def update_features(self, change, feature_selector=None):
        """
        A file type has been chosen.  Update the available features for that
        file type.
        """

        file_type = change.new

        ncfile = self.label2file[file_type]

        # Ok, get a list of data variables and use it to populate the
        # feature selector
        lst = []
        with netCDF4.Dataset(ncfile) as nc:
            data_variables = nc.variables.keys()

            for data_variable in data_variables:
                ncvar = nc[data_variable]

                # Is it a QC variable?  If so, skip it.
                if (
                    hasattr(ncvar, 'standard_name')
                    and ncvar.standard_name == 'status_flag'
                ):
                    continue

                # Is it a time variable?  If so, skip it.
                if hasattr(ncvar, 'calendar'):
                    continue
                try:
                    if ncvar.standard_name == 'time':
                        continue
                except AttributeError:
                    pass

                # never consider these two variables from the historical
                # file
                if data_variable in ('rowSize', 'station_id'):
                    continue

                lst.append(data_variable)

        # and finally, set the feature selector list
        feature_selector.options = sorted(lst)
        feature_selector.value = lst[0]
