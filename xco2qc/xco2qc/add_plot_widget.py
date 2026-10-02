import os
from pathlib import Path
import time

from IPython.display import display
import ipywidgets as widgets
from ipywidgets import HBox, Box, Layout, Button, Dropdown, Text, Label, GridspecLayout
import pandas as pd
import plotly.offline as po
import yaml

from .netcdf_to_pandas import netCDFaccess
from .qc_flagging_plotly import PlotlyPlotter, add_plots_to_plot_dict
from .multi_year_plotter import MultiYearPlotter
# reference html: https://stackoverflow.com/questions/70564974/how-to-create-a-dynamic-dependent-dropdown-menu-using-ipywidgets

curr_path = os.path.dirname(os.path.abspath(__file__))
standard_qc_plots_path = os.path.join(curr_path, 'core', 'data', 'standard_plots_multipage.yml')
standard_multiyear_plots = ['xCO2_air', 'pCO2_sw', 'SST', 'SSS', 'ph_sw', 'CHL', 'NTU', 'dissolved_oxygen']


class AdditionalPlotsGUI:
    """
        Interface to view and add plots using dropdown widgets.
        
        :param standard_plots_path: (Path or str) path to the .yml file containing the standard QC plots.
        :param standard_multiyear_plots: (List[str]) list of parameters (columns) contained in the merge.nc.
                                         Parameters not included in merge.nc will be removed automatically.
        :param folder_path: path to the qc folder containing .nc files in the trimmed subfolder and merge.nc
                            file in the merge subfolder.
        :param site_id: (str) cannonical name of the site being QC'ed.
        :param isMobile) (bool) whether the site is a mobile site (ex SailDrone) or a stationary site (ex. mooring).
    """
    
    def __init__(self, merged_folder_path, trimmed_folder_path, site_id, config, standard_plots_path=standard_qc_plots_path, standard_multiyear_plots=standard_multiyear_plots, use_colorblind=False, isMobile=False):
        if type(merged_folder_path) != Path:
            self.merge_folder = Path(merged_folder_path)
        else:
            self.merge_folder = merged_folder_path
        if type(trimmed_folder_path) != Path:
            self.trim_folder = Path(trimmed_folder_path)
        else:
            self.trim_folder = trimmed_folder_path
        self.site_id = site_id.lower()
        self.config = config
        merge_path = os.path.join(self.merge_folder, 'merge.nc')
        
        # build data access object
        self.data = netCDFaccess(merge_path, self.trim_folder, self.site_id, self.config)
        
        # build plot groups for various buttons
        plot_groups = plot_dicts_from_file(standard_plots_path, self.data, isMobile)
        plot_groups['multi_year'] = {'multi_year': standard_multiyear_plots}
        
        # build plotter
        self.plotter = Plotter(plot_groups, self.data, use_colorblind)
        
        # build dropdown options
        self.cols = ['col_1', 'col_2', 'col_3']
        self._available_plotting_dict()
        self.plot_mapping_keys = ['x_source', 'x_data', 'y1_source', 'y1_data', 'y1_color_source',
                                  'y1_color_data', 'y2_source', 'y2_data', 'y2_color_source',
                                  'y2_color_data']
        self.plot_types = ['Scatter']
        self.plot_mapping = {'Scatter': self._scatter_plot_options()}
        
        if isMobile:
            self.plot_types.append('Map')
            self._map_plot_options()
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass
    
    def _available_plotting_dict(self):
        """
            Build dictionaries (one without a 'None' option, one with) which provide the
            data options in the dropdown menus.
        """
        self.avail_plots = {}
        data_sources = self.data.available_data_sources()
        for k in data_sources:
            d = self.data.available_data_in_source(k)
            d.sort()
            self.avail_plots[k] = d
        self.avail_plots_with_null = self.avail_plots.copy()
        self.avail_plots_with_null['None'] = [None]
        
    def _scatter_plot_options(self):
        """Set x, y, and color parameter options when scatter type plot selected."""
        opts = {}
        options = list(self.avail_plots.keys())
        options_with_none = ['None'] + options
        for k1, k2 in zip(self.plot_mapping_keys[::2], self.plot_mapping_keys[1:][::2]):
            if k1 not in ['x_source', 'y1_source']:
                opts[k1] = options_with_none
                opts[k2] = self.avail_plots_with_null
            else:
                opts[k1] = options
                opts[k2] = self.avail_plots
        return opts
    
    def _map_plot_options(self):
        """Preset x and y to be lat/long and set color parameter options when map plot selected."""
        values = [['header'], {'header': ['longitude']}, ['header'], {'header': ['latitude']}, self.plot_mapping['Scatter'][self.plot_mapping_keys[4]],
                  self.avail_plots_with_null, ['None'], {'None': [None]}, ['None'], {'None': [None]}]
        map_options = {}
        for k, v in zip(self.plot_mapping_keys, values):
            map_options[k] = v
        self.plot_mapping['Map'] = map_options
    
    def _build_dropdown_dict(self):
        """Build various dropdowns"""
        self.width = '125px'
        drop_options = self.plot_mapping['Scatter']
        self.dropdowns = {
                          'plots': Dropdown(options=self.plot_types, layout=Layout(width=self.width)),
                          'cols': Dropdown(options=self.cols, layout=Layout(width=self.width))
                         }
        
        # plot_mapping_keys are ordered in pairs. Iterate through the pairs to build the dropdowns.
        for k1, k2 in zip(self.plot_mapping_keys[::2], self.plot_mapping_keys[1:][::2]):
            self.dropdowns[k1] = Dropdown(options=drop_options[k1], layout=Layout(width=self.width))
            self.dropdowns[k2] = Dropdown(options=drop_options[k2][drop_options[k1][0]], layout=Layout(width=self.width))
    
    def _build_dropdown_handler_dict(self):
        """Build the various handlers for the dropdown menus."""
        self.dropdown_handlers = {'plots': self._dropdown_plots_handler_generator()}
        for k1, k2 in zip(self.plot_mapping_keys[::2], self.plot_mapping_keys[1:][::2]):
            self.dropdown_handlers[k1] = self._dropdown_handler_generator(self.plot_mapping[self.plot_types[0]][k1], self.dropdowns[k2], self.plot_mapping[self.plot_types[0]][k2]) 
    
    def _dropdown_plots_handler_generator(self):
        """
            Set up the source and data dropdown updates when the plot type (ex. scatter, map) are changed.
            Updates x_source, x_data, y_param_source, y_param_data, y_color_source, y_color_data, etc.
        """
        def handler(change):
            self.plot_types = change.new
            for k1, k2 in zip(self.plot_mapping_keys[::2], self.plot_mapping_keys[1:][::2]):
                self.dropdowns[k1].options = self.plot_mapping[self.plot_types][k1]
                self.dropdowns[k2].options = self.plot_mapping[self.plot_types][k2][self.dropdowns[k1].value]
        return handler
    
    def _dropdown_handler_generator(self, input, option, option_dict):
        """
            Set up data dropdown updates when associated source dropdown changed.
            ex. x_source change updates x_data options.
        """
        def handler(change):
            input = change.new
            option.options = option_dict[input]
        return handler
    
    def _buttons(self):
        """
        Creates various button widgets:
        button for adding plots to the qc_plots data page,
        button for displaying qc plots,
        button for displaying multi_year plots.
        """
        
        self.add_button = widgets.Button(description='Add Plot')
        self.plot_button = widgets.Button(description='Plot Quality Control')
        self.multiyear_button = widgets.Button(description='Plot Multi-Year')
        self.to_excel_button = widgets.Button(description='Data to Excel')

    def _swap_button_disable(self):
        for b in [self.add_button, self.plot_button, self.multiyear_button, self.to_excel_button]:
            b.disabled = not b.disabled
    
    def _add_button_response_generator(self):
        def on_add_button_click(b):
            """Builds a plot dictionary and adds it to the plotter based on user input."""
            self._swap_button_disable()
            plot_params = {'type': self.dropdowns['plots'].value.lower()}
            
            # build axes information
            plot_params['x'] = ' '.join([self.dropdowns['x_source'].value, self.dropdowns['x_data'].value])
            plot_params['y1'] = [build_y_axis_dict(
                                                   self.dropdowns['plots'].value,
                                                   self.dropdowns['y1_source'].value,
                                                   self.dropdowns['y1_data'].value,
                                                   self.dropdowns['y1_color_source'].value,
                                                   self.dropdowns['y1_color_data'].value
                                                  )]
            if self.dropdowns['y2_source'].value != 'None':
                plot_params['y2'] = [build_y_axis_dict(
                                                       self.dropdowns['plots'].value,
                                                       self.dropdowns['y2_source'].value,
                                                       self.dropdowns['y2_data'].value,
                                                       self.dropdowns['y2_color_source'].value,
                                                       self.dropdowns['y2_color_data'].value
                                                      )]
            
            # create plot name
            plot_params['name'] = build_plot_name(
                                                  self.dropdowns['plots'].value,
                                                  self.dropdowns['x_source'].value,
                                                  self.dropdowns['x_data'].value,
                                                  self.dropdowns['y1_source'].value,
                                                  self.dropdowns['y1_data'].value,
                                                  self.dropdowns['y1_color_source'].value,
                                                  self.dropdowns['y1_color_data'].value
                                                 )
            
            # add plot
            self.plotter.add_plot('qc_plots', 'data', {self.dropdowns['cols'].value: {1: plot_params}})
            
            self.add_button.description = "Plot Added"
            time.sleep(1)
            self.add_button.description = "Add Plot"
            self._swap_button_disable()
        
        return on_add_button_click
    
    def _plot_button_response_generator(self):
        def on_plot_button_click(b):
            """Saves and opens the qc_plots plotly html plots windows."""
            self._swap_button_disable()
            figs = self.plotter.plot_figs('qc_plots')
            for fig_name, fig in figs.items():
                save_path = os.path.join(self.merge_folder, self.site_id.upper() + ' ' + fig_name + '.html')
                po.plot(fig, filename=save_path)
            # fig.show(renderer='browser')  # config={'displayModeBar': True, 'showLink': True, 'plotlyServerURL': "https://chart-studio.plotly.com"})
            self._swap_button_disable()
        return on_plot_button_click
    
    def _multiyear_plot_button_response_generator(self):
        def on_mulityear_button_click(b):
            """Saves and opens the multi_year plots window."""
            self._swap_button_disable()
            figs = self.plotter.plot_figs('multi_year')
            for fig_name, fig in figs.items():
                save_path = os.path.join(self.merge_folder, self.site_id.upper() + ' ' + fig_name + '.html')
                po.plot(fig, filename= save_path) # .show(config={'displayModeBar': True, 'showLink': True, 'plotlyServerURL': "https://chart-studio.plotly.com"}))
            self._swap_button_disable()
        return on_mulityear_button_click
    
    def _to_excel(self):
        def to_excel_button_click(b):
            self._swap_button_disable()
            self.to_excel_button.description = "Saving Data..."
            try:
                save_path = os.path.join(self.merge_folder, self.site_id.upper() + ' data.xlsx')
                with pd.ExcelWriter(save_path) as writer:
                    for k, v in self.data.data.items():
                        v.df.to_excel(writer, sheet_name=f'{k}', index=False)
            except PermissionError as e:
                raise e
            finally:
                self.to_excel_button.description = "Data to Excel"
                self._swap_button_disable()
        return to_excel_button_click
    
    def run(self):
        """Show the grid with dropdowns to allow users to add figures and plot."""
        # build various dropdowns
        self._build_dropdown_dict()
        self._build_dropdown_handler_dict()
        for k, v in self.dropdown_handlers.items():
            self.dropdowns[k].observe(v, names='value')

        # build various buttons
        self._buttons()
        self.add_button.on_click(self._add_button_response_generator())
        self.plot_button.on_click(self._plot_button_response_generator())
        self.multiyear_button.on_click(self._multiyear_plot_button_response_generator())
        self.to_excel_button.on_click(self._to_excel())
        
        # build and populate grid
        plot_type_container = widgets.VBox(
            [
             Label("Plot Type", anchor='center', layout=Layout(width=self.width)),
             self.dropdowns['plots'],
             Label("Column", anchor='center', layout=Layout(width=self.width)),
             self.dropdowns['cols']
            ]
        )
        
        x_axis_container = widgets.VBox(
            [
             Label("X", layout=Layout(width=self.width)),
             self.dropdowns['x_source'],
             self.dropdowns['x_data']
            ]
        )
        
        primary_y_container = widgets.VBox(
            [
             Label("Primary Y-axis", anchor='center', layout=Layout(width=self.width)),
             self.dropdowns['y1_source'],
             self.dropdowns['y1_data']
            ]
        )
        
        primary_color_container = widgets.VBox(
            [
             Label("Primary Y Color", anchor='center', layout=Layout(width=self.width)),
             self.dropdowns['y1_color_source'],
             self.dropdowns['y1_color_data']
            ]
        )
        
        secondary_y_container = widgets.VBox(
            [
             Label("Secondary Y-axis", anchor='center', layout=Layout(width=self.width)),
             self.dropdowns['y2_source'],
             self.dropdowns['y2_data']
            ]
        )
        
        secondary_color_container = widgets.VBox(
            [
             Label("Secondary Y Color", anchor='center', layout=Layout(width=self.width)),
             self.dropdowns['y2_color_source'],
             self.dropdowns['y2_color_data']
            ]
        )
        
        button_container = widgets.HBox(
            [
             self.add_button,
             self.plot_button,
             self.multiyear_button,
             self.to_excel_button
            ]
        )
        container = widgets.VBox([
            widgets.HBox([
                          plot_type_container,
                          x_axis_container,
                          primary_y_container,
                          primary_color_container,
                          secondary_y_container,
                          secondary_color_container,
                         ]),
            button_container
        ])

        return display(container)


# widget helper functions
def plot_dicts_from_file(path, data_access_object: netCDFaccess, isMobile: bool=False) -> dict:
    """Provided a file with standard plots (always should be plotted),
    auxillary plots (data that may or may not exist based on system set-up),
    and mobile plots (whether system on a mobile platform or not), build a 
    structured dictionary based on available data.
    
    :param path: (Path or str) file path to a yml file with plotting information.
    :param data_access_object: (netCDFaccess) object to access available data.
                               Used to determine whether auxillary plots should be added.
    :param isMobile: (bool) Determine whether to add mobile plots to output.
    
    :output: (dict) primary key groups the various plots. Secondary key sets the 'page'
             of the plots (each page will produce a different plotly figure). Dictionary
             within the secondary key is the appropriate plotting metadata.
    """
    
    assert os.path.exists(path) and path.endswith(".yml")
    with open(path) as f:
        all_plots = yaml.load(f, yaml.SafeLoader)
    plot_groups = {'qc_plots': {}}
    for page in ['data', 'diagnostic']:
        p = all_plots.get('standard_plots_' + page, None)
        if p:
            plot_groups['qc_plots'][page] = p
    
    aux_plots = all_plots.get('aux_plots', {})
    
    available_aux_data = [s.lower() for s in data_access_object.available_merge_columns() if s.lower() in ['ph_sw', 'chl', 'ntu', 'dissolved_oxygen']]
    for aux_param, aux_dict in aux_plots.items():
        if aux_param.lower() in available_aux_data:
            for k, v in aux_dict.items():
                plot_groups['qc_plots']['data'] = add_plots_to_plot_dict(plot_groups['qc_plots']['data'], v, k)
    
    if isMobile:
        mobile_plots = all_plots.get('mobile_plots', {})
        plot_groups['qc_plots']['maps'] = mobile_plots
    
    return plot_groups


def build_y_axis_dict(plot_type: str, y_param_source: str, y_param_data: str, y_color_source: str, y_color_data: str) -> dict:
    """
    Builds the y-axis portion of an add_plot dictionary. Set up for both first and second y-axes.
    
    :param plot_type: (str) what type of plot is being created (currently either Scatter or Map)
    :param y_param_source: (str) The data source from which y_param_data is being drawn (ex. merge, zpon, zpoff, etc.)
    :param y_param_data: (str) The variable to be plotted (ex. SST, SSS, xCO2 Air, etc.)
    :param y_color_source: (str) The data source which y_color_data is being drawn (usually same source pool as y_param_source).
                           Defaults to 'None' when no color selected ('None' rather than None for dict key stability)
    :param y_color_data: (str) The variable to use for coloring the y_param_data (usually from same data pool as y_param_data).
                         Defaults to None when no color selected.
    
    :output: dict
    """
    
    y = ' '.join([y_param_source, y_param_data])
    y_dict = {}
    if plot_type.lower() == 'map':
        y_dict['hovertemplate'] = "%{text}"
        y_dict['text'] = "MERGE TIME"
    else:
        y_dict['hovertemplate'] = f"<b>{y}</b>: " + "%{y}"
    if y_color_source != 'None':
        y_c = ' '.join([y_color_source, y_color_data])
        y_dict['marker'] = {'color': y_c}
        y_dict['hovertemplate'] += f"<br><b>{y_c} (color)</b>: " + "%{marker.color}"            
    y_dict['hovertemplate'] += "<extra></extra>"
    return {y: y_dict}


def build_plot_name(plot_type: str, x_param_source: str, x_param_data: str, y_param_source: str, y_param_data: str, y_color_source: str, y_color_data: str) -> str:
    """
    Builds the y-axis portion of an add_plot dictionary. Set up for both first and second y-axes.
    
    :param plot_type: (str) what type of plot is being created (currently either Scatter or Map)
    :param x_param_source: (str) The data source from which x_param_data is being drawn (ex. merge, zpon, zpoff, etc.)
    :param x_param_data: (str) The x-variable to be plotted (ex. SST, SSS, xCO2 Air, etc.)
    :param y_param_source: (str) The data source which y_param_data is being drawn (usually same source pool as x_param_source).
    :param y_param_data: (str) The y-variable to be plotted (usually from same data pool as x_param_data).
    :param y_color_source: (str) The data source which y_color_data is being drawn (usually same source pool as x_param_source and y_param_source).
                           Defaults to 'None' when no color selected ('None' rather than None for dict key stability)
    :param y_color_data: (str) The variable to use for coloring the y_param_data (usually from same data pool as x_param_data and y_param_data).
                         Defaults to None when no color selected.
    
    :output: str
    """
    
    if plot_type.lower() == 'scatter':
        name = ' '.join([x_param_source, x_param_data]) + ' vs ' if x_param_data.lower() != 'time' else ''
        name += ' '.join([y_param_source, y_param_data])
    elif plot_type.lower() == 'map':
        if y_color_source != 'None':
            name = ' '.join([y_color_source, y_color_data])
        else:
            name = 'Location'
    
    return name

plotter_catalog = {
                   'default': PlotlyPlotter,
                   'multi_year': MultiYearPlotter,
                   }

class Plotter:
    """
    Universal container for the various plotting objects (eg. PlotlyPlotter and MultiYearPlotter).
    Available plotting objects to the Plotter are maintained in the plotter_catalog.
    
    :param standard_plots: (dict) primary keys are the different groupings of the plotting objects.
                           This allows multiple figures to be passed in a dictionary when plot_figs is called.
    :param data_access_object: (netCDFaccess) the data access object used by the plotters to build their figures.
                               The data access object must be the same between plotting objects.
    """
    
    def __init__(self, standard_plots: dict, data_access_object: netCDFaccess, use_colorblind=False):
        self.standard_plots = standard_plots
        self.dao = data_access_object
        self.use_colorblind = use_colorblind
        self._initialize_plot_objects()
        
    def _initialize_plot_objects(self):
        """
            Initialize a dictionary which houses the various plotting objects.
            Available plotting objects determined by plotter_catalog.
        """
        
        self.plot_groups = {}
        for group, page in self.standard_plots.items():
            self.plot_groups[group] = {}
            for p, plot_specs in page.items():
                self.plot_groups[group][p] = plotter_catalog.get(p, plotter_catalog['default'])(plot_specs, self.dao, self.use_colorblind)
    
    def get_plot_groups_and_pages(self) -> dict:
        """Return the plot groups and their associated pages."""
        return {k: list(self.plot_groups[k].keys()) for k in self.plot_groups.keys()}
    
    def add_plot(self, plot_group: str, plot_page: str, new_plot_specs: dict):
        """
            Use the add_plot interface of plotting objects to add a plot.
            Plotting object selected by which plot group and page selected.
        """
        if plot_group in self.plot_groups and plot_page in self.plot_groups[plot_group]:
            self.plot_groups[plot_group][plot_page].add_plots(new_plot_specs)
        # TODO: determine error handling.
    
    def plot_figs(self, group: str) -> dict:
        """Returns a dictionary with keys as the pages of the selected plot_group and plotly figures as the values."""
        if group in self.plot_groups:
            return {k: p.plot() for k, p in self.plot_groups[group].items()}
        else:
            # TODO: determine error handling
            return {}
