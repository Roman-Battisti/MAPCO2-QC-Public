# standard libraries
from copy import deepcopy
import os
import pathlib
from math import floor, ceil

# 3rd party libraries
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr
import yaml

# plotly
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.offline as po
import plotly

from .netcdf_to_pandas import netCDFaccess


# grab the appropriate parameter mappings for use when converting
# keywords to data
curr_path = os.path.dirname(os.path.abspath(__file__))
mapping_path = os.path.join(curr_path, 'core', 'param_mapping.yml')
with open(mapping_path) as f:
    param_mapping = yaml.load(f, yaml.SafeLoader)
nc_file_mapping = param_mapping.get('NC_file_mapping', {})
axes_params = param_mapping.get('AXES')
standard_colors = param_mapping.get('STANDARD_COLORS')
colorblind_colors = param_mapping.get('COLORBLIND_COLORS')


class PlotlyPlotter:
    """
        Standard plotter which takes a dictionary of plot metadata and will produce plotly figures.
        Can add plots to the end of any column (but cannot insert).
        
        :param standard_plots: (dict) contains metadata of the plots which will always be plotted by
                               the PlotlyPlotter object.
        :param data_access_object: (netCDFaccess) contains data which will be used as substitute for
                                   parameter keywords (such as x data, y data, and color data).
        :param plot_height: (int) individual plot height.
        :param plot_width: (int) individual plot width.
    """
    def __init__(self, standard_plots: dict, data_access_object: netCDFaccess, use_colorblind=False, plot_height=400, plot_width=600, colorscale='rainbow'):
        self.plots_dict = standard_plots
        self.data = data_access_object
        self.use_colorblind = use_colorblind
        if self.use_colorblind:
            colorscale = "bluered"
        # plot specs
        self.plot_specs = {'height': plot_height,
                           'width': plot_width,
                           'colorscale': colorscale}
        
    def _get_lat_lon_centers(self):
        """Estimates geographic center of data for map plots."""
        lat_center = round(np.nanmean(self.data.get_data('HEADER LATITUDE')), 2)
        lat_min = np.clip(
                          round(np.nanmin(self.data.get_data('HEADER LATITUDE')), 2) - 20, -90, 90
                          )
        lat_max = np.clip(
                          round(np.nanmax(self.data.get_data('HEADER LATITUDE')), 2) + 20, -90, 90
                          )
        lon_center = round(np.nanmean(self.data.get_data('HEADER LONGITUDE')), 2)
        lon_min = np.clip(
                          round(np.nanmin(self.data.get_data('HEADER LONGITUDE')), 2) - 20, -180, 180
                          )
        lon_max = np.clip(
                          round(np.nanmax(self.data.get_data('HEADER LONGITUDE')), 2) + 20, -180, 180
                          )
        output = {
            'center': {'lat': lat_center, 'lon': lon_center},
            'lataxis_range': [lat_min, lat_max],
            'lonaxis_range': [lon_min, lon_max],
        }
        
        adjusted_output = self._update_gps_range_for_aspect_ratio(output)
        
        return adjusted_output
    
    def _update_gps_range_for_aspect_ratio(self, gps_dict):
        aspect_ratio = 1.6
        lat_range = abs(gps_dict['lataxis_range'][0] - gps_dict['lataxis_range'][1])
        lon_range = abs(gps_dict['lonaxis_range'][0] - gps_dict['lonaxis_range'][1])
        
        if lon_range / lat_range < aspect_ratio:
            # adjust lon range
            new_lon_range = lat_range * aspect_ratio
            new_center = (gps_dict['lonaxis_range'][0] + gps_dict['lonaxis_range'][1]) / 2
            new_lon_min = np.clip(new_center - new_lon_range / 2, -180, 180)
            new_lon_max = np.clip(new_center + new_lon_range / 2, -180, 180)
            gps_dict['lonaxis_range'] = [new_lon_min, new_lon_max]
        else:
            # adjust lat range
            new_lat_range = lon_range / aspect_ratio
            new_center = (gps_dict['lataxis_range'][0] + gps_dict['lataxis_range'][1]) / 2
            new_lat_min = np.clip(new_center - new_lat_range / 2, -90, 90)
            new_lat_max = np.clip(new_center + new_lat_range / 2, -90, 90)
            gps_dict['lataxis_range'] = [new_lat_min, new_lat_max]
        
        return gps_dict
            
    def set_plot_parameter(self, param_name: str, param_update):
        """change one of the predefined plot_specs."""
        if param_name in self.plot_specs:
            self.plot_specs[param_name] = param_update
    
    def available_data_api(self):
        return self.data
    
    def available_plot_col_names(self):
        return list(self.plots_dict.keys())
    
    def add_plots(self, add_plot_dict):
        for k, v in add_plot_dict.items():
            self.plots_dict = add_plots_to_plot_dict(self.plots_dict, v, k)
        
        return self
            
    def plot(self):
        """
            Outputs a Plotly subplots fig object based on initial plot metadata provided
            and any added plots.
        
        """
        
        # get the appropriate subplot metadata.
        specs = SpecsParser(self.plots_dict, self.data, self.use_colorblind)
        initialize = specs.initialization()
        plot_height = self.plot_specs['height'] * initialize['rows']
        plot_width = self.plot_specs['width'] * initialize['cols']
        plots = specs.plots()
        x_axes = specs.x_axes()
        y_axes = specs.y_axes()
        
        plot_types = plots.get('type', None)
        plot_pos = plots.get('plot_pos', None)
        plot_params = plots.get('params', None)
        
        hasMaps = False  # keep track of whether a map plot is created for stylizing
        
        # initialize subplots fig object and populate.
        fig = make_subplots(**initialize)
        for p_type, pos, params, x, y in zip(plot_types, plot_pos, plot_params, x_axes, y_axes):
            for i in range(len(p_type)):
                if p_type[i] == 'scatter':
                    fig.add_trace(go.Scatter(**params[i]), **pos[i])
                elif p_type[i] == 'map':
                    hasMaps = True
                    params[i]['lon'] = params[i].pop('x')
                    params[i]['lat'] = params[i].pop('y')
                    fig.add_trace(go.Scattergeo(**params[i]), **pos[i])  # Scattermapbox
                else:
                    pass
            for i in range(len(y)):
                fig.update_yaxes(**y[i])
            fig.update_xaxes(**x)
        
        if hasMaps:
            geo_centers = self._get_lat_lon_centers()
            fig.update_geos(**geo_centers)  # update_mapboxes(style='open-street-map', center=geo_centers)
            fig.update_xaxes(matches='x')
            fig.update_yaxes(matches='y')
            plot_width *= 1.2
        
        # update layouts and styles.
        layout_update = {'height': plot_height, 'width': plot_width, 'hovermode': 'x', 'colorscale': {'sequential': self.plot_specs['colorscale']}}
        fig.update_layout(**layout_update)
        
        return fig


# PlotlyPlotter helper functions
def add_plots_to_plot_dict(plot_dict: dict, add_plot_dict: dict, plot_group: str) -> dict:
    """
        Add plot(s) to a key (plot_dict_key) in an existing plot_dict.
        If the key does not exist, one will be created.
        
        :param plot_dict: (dict) dictionary of plots. Top level keys represent grouping of related plots
        :param add_plot_dict: (dict) contains information of the plot. Top level key(s) are plot number of type int.
                              Top level key(s) will be reassigned so that existing entries are not replaced.
        :param plot_group: (normally str) the plot grouping (see plot_dict param) with which new plots are associated.
                           If key does not exist in top level of plot_dict, a new key will be formed.
        
        :output: (dict) modified dictionary
    """
    
    output = deepcopy(plot_dict)
    if plot_group in output:
        new_plot_num = max(list(output[plot_group].keys())) + 1
    else:
        output[plot_group] = {}
        new_plot_num = 1
    # currently assume plots is a list of plot params
    for k, v in add_plot_dict.items():
        output[plot_group][new_plot_num] = v
        new_plot_num += 1
    
    return output


class SpecsParser:
    """
        Converts a dictionary of plotting specs into a format that 
        is usable by plotly.
    """
    def __init__(self, metadata_dict, data, use_colorblind=False):
        self.metadata_dict = metadata_dict
        self.data = data
        self.colors = standard_colors if not use_colorblind else colorblind_colors
        self._get_inits()
        self._get_inits_plot_names()
        self._get_plots_and_axes()
        
    def _get_inits(self):
        """
            Provides a dictionary of metadata to initialize a plotly figure.
        """
        initialize = {'cols': len(self.metadata_dict.keys())}
        initialize['rows'] = max([max(list(v.keys())) for v in self.metadata_dict.values()])
        s = [[{'secondary_y': False} for _ in range(initialize['cols'])] for _ in range(initialize['rows'])]
        col = 0
        for k1, v1 in self.metadata_dict.items():
            for k2, v2 in v1.items():
                plot_type = v2.get('type', 'scatter')
                if plot_type == 'scatter' and 'y2' in v2:
                    s[k2 - 1][col] = {'secondary_y': True}
                elif plot_type == 'map':
                    s[k2 - 1][col] = {'type': 'scattergeo'}  # 'scattermapbox'
            col += 1
        initialize['specs'] = s
        initialize['horizontal_spacing'] = 0.11
        initialize['vertical_spacing'] = 0.1
        
        self.inits = initialize
    
    def _get_inits_plot_names(self):
        """Determine the names of each plot. Plotly orders names top to bottom, left to right."""
        plot_matrix = [['' for _ in range(self.inits['cols'])] for _ in range(self.inits['rows'])]
        col = 0
        for col_type, plot_dict in self.metadata_dict.items():
            for row_num, plot_param in plot_dict.items():
                plot_matrix[row_num - 1][col] = plot_param.get('name', '')
            col += 1
        self.inits['subplot_titles'] = [j for i in plot_matrix for j in i]
    
    def _get_plots_and_axes(self):
        """
            Get the metadata for each trace within the plotly figure.
            Different y-axes in the same plot must have their own trace.
        """
        self.plot_specs = {'type': [], 'params': [], 'plot_pos': []}
        self.x_axes_specs = []
        self.y_axes_specs = []
        self.link_x_axis = {}
        self.link_y_axis = {}  # not implemented
        
        plot_col = 0
        plot_count = 0
        for plot_col_name, figs in self.metadata_dict.copy().items():
            plot_col += 1
            for plot_row, plot_params in figs.items():
                plot_count += 1
                self._get_plots(plot_row, plot_col, plot_params)
                self._get_axes(plot_row, plot_col, plot_count, plot_params)
    
    def _get_plots(self, plot_row: int, plot_col: int, plot_params: dict):
        """
            Specify x, y, color data and additional metadata for the plot in position plot_row, plot_col.
            
            :param plot_row: (int) row of the plot
            :param plot_col: (int) column of the plot
            :param plot_params: (dict) contains metadata for each trace in the
                                plot located at plot_row, plot_col. This may
                                include multiple traces on the primary y-axis
                                and/or multiple traces on the secondary y-axis.
                                Each uses the same x-axis data.
        """
        
        # create the trace metadata for the x and y axes.
        x = plot_params.get('x', '')
        y1 = plot_params.get('y1', None)
        y2 = plot_params.get('y2', [])
        plot_type = plot_params.get('type', 'scatter')
        
        self.plot_specs['params'].append([self._y_params(p, x) for p in y1 + y2])
        
        # specify plot type for each plot
        self.plot_specs['type'].append([plot_type] * (len(y1) + len(y2)))
        
        # specify plot position
        plot_pos = [{'row': plot_row, 'col': plot_col} for _ in y1] +\
                   [{'secondary_y': True, 'row': plot_row, 'col': plot_col} for _ in y2]
        self.plot_specs['plot_pos'].append(plot_pos)

    def _y_params(self, p_info, x: str):
        """
            Sub x and y data keywords with actual data and add name and mode information.
            :param p_info: (dict or str) provides the information for y-axes.
                           If a dictionary is passed, there is additional metadata (ex. color) to handle.
                           Dictionary is expected to only have one key.
                           If a string is passed, then only the y-axis information provided.
                           Handles if nothing is provided by creating trace information with an empty y
            :param x: (str) x-axis keyword to be replaced with actual data. Each trace must have x data.
            
            :output: (dict)
        """
        
        y_params = {}
        if type(p_info) == dict:
            # y-axis may have additional metadata (such as color, text, etc.)
            k, v = next(iter(deepcopy(p_info).items()))  # make sure not to change original metadata_dict due to pass by reference
            y_params = self._sub_param_keywords_with_data(x, k, v)  # replace data keyword with actual data.
            if not (x.lower().endswith(('longitude', 'latitude')) and k.lower().endswith(('longitude', 'latitude'))):
                # handle if we're looking at a map plot, which will result in the trace being called 'latitude' or 'longitude'
                y_params['name'] = k  # specify name of trace
            else:
                y_params['name'] = p_info[k].get('marker', {}).get('color', None)
            y_params['mode'] = p_info[k].get('mode', 'markers')  # specify using markers, lines, etc.  # 'markers+lines'
            
        elif type(p_info) == str:
            # y-axis only has data, with no additional metadata
            y_params = self._sub_param_keywords_with_data(x, p_info, {})
            y_params['name'] = p_info
            y_params['mode'] = 'markers'
        else:
            # handle when no y-axis info is provided (eg trace with no y-data)
            y_params = self._sub_param_keywords_with_data(x, 'N/A', {})
            y_params['name'] = 'No data info provided'
            y_params['mode'] = 'markers'
        
        return y_params
    
    def _get_axes(self, plot_row: int, plot_col: int, plot_count: int, plot_params: dict):
        self._x_axes(plot_row, plot_col, plot_count, plot_params)
        self._y_axes(plot_row, plot_col, plot_params)
        
    def _x_axes(self, plot_row: int, plot_col: int, plot_count: int, plot_params: dict):
        """
            Define x axis metadata (not x data, but other important metadata info).
        
            :param plot_row: (int) row of the plot
            :param plot_col: (int) column of the plot
            :param plot_count: (int) number of plot being processed (top to bottom, left to right order).
                               This is used to determine linkages between x-axis (for linked panning/zooming)
                               since Plotly doesn't use row/column info but the plot number to link axes.
            :param plot_params: (dict) contains metadata for each trace in the
                                plot located at plot_row, plot_col. This may
                                include multiple traces on the primary y-axis
                                and/or multiple traces on the secondary y-axis.
                                Each uses the same x-axis data.
        """
        # get x axis title, presume time if not provided. Remove data_source if using time (for linking)
        x = plot_params.get('x', 'time')  # default to time
        x = 'time' if x.endswith('time') else x
        
        # Check wether x axis should be linked to other plots. Defaults true.
        link_x = plot_params.get('link_x', 1)  # default to linking x-axes (will zoom and pan together)
        # specify x axis parameters
        x_axis = {'title_text': x, 'row': plot_row, 'col': plot_col}
        
        # add linkage
        if link_x:
            x_axis['matches'] = self.link_x_axis.get(x, None)
        if x not in self.link_x_axis:
            self.link_x_axis[x] = f"x{plot_count}"
        
        # prepend additional parameters with x_
        for p in axes_params['x']:
            if 'x_' + p in plot_params:
                x_axis[p] = plot_params['x_' + p]
        
        self.x_axes_specs.append(x_axis)
    
    def _y_axes(self, plot_row: int, plot_col: int, plot_params: dict):
        """
            Define primary and secondary y axis metadata (not y data, but other important metadata info).
            y-axis linkage not implemented.
        
            :param plot_row: (int) row of the plot
            :param plot_col: (int) column of the plot
            :param plot_params: (dict) contains metadata for each trace in the
                                plot located at plot_row, plot_col. This may
                                include multiple traces on the primary y-axis
                                and/or multiple traces on the secondary y-axis.
                                Each uses the same x-axis data.
        """
        
        # build the metadata dictionarys for both y1 and y2
        y_axis_list = []
        for y in ['y1', 'y2']:
            y_metadata = self._y_axis_metadata(y, plot_row, plot_col, plot_params)
            if y_metadata:
                y_axis_list.append(y_metadata)
        
        # Plotly needs to be told metadata is for the secondary y-axis
        if len(y_axis_list) > 1:
            y_axis_list[1]['secondary_y'] = True
        
        self.y_axes_specs.append(y_axis_list)
    
    def _y_axis_metadata(self, param_name: str, plot_row: int, plot_col: int, plot_params: dict):
        """
            Builds the y-axis metadata (see _y_axes, above).
            
            :param param_name: name of the y-axis (y1 or y2 for primary and secondary y-axis, respectively)
            :param plot_row: (int) row of the plot
            :param plot_col: (int) column of the plot
            :param plot_params: (dict) contains metadata for each trace in the
                                plot located at plot_row, plot_col. If there are
                                multiple traces on the y-axis, only the first
                                will be used to name the axis.
            
            :output: (dict)
        """
        
        y = plot_params.get(param_name, None)
        
        if not y:  # handle if particular y-axis doesn't exist (specifically for secondary y (y2))
            return None
        
        y_axis_first_entry = y[0]
        if type(y_axis_first_entry) == dict:
            y_axis_first_entry_name = next(iter(y_axis_first_entry))
        elif type(y_axis_first_entry) == str:
            y_axis_first_entry_name = y_axis_first_entry
        y_axis_name = y_axis_first_entry_name.split()[-1]  # faster than list(y1[0].keys())[0]
        y_axis = {'title_text': y_axis_name, 'row': plot_row, 'col': plot_col}
        for p in axes_params[param_name]:
            if param_name + '_' + p in plot_params:
                y_axis[p] = plot_params[param_name + '_' + p]
        
        return y_axis
    
    def _sub_param_keywords_with_data(self,  x: str, y: str, param_dict: dict):
        """
            Substitutes parameter keywords with associated data. Data is accessed
            through the provided data object. Expected format for keywords is
            'source_name data_name', which will point to the name of a data column
            (ex. time, sst, sss, etc.) within a particular source (ex. merge, apon,
            climatology, etc.).
            
            :param x: (str) x-axis keyword.
                      Defaults to time data from the y source_name.
            :param y: (str) y-axis keyword.
            :param param_dict: (dict) additional metadata, such as color,
                               which must be converted to actual data.
        """
        
        output = {}
        output['y'] = self.data.get_data(y.lower())
        
        # determine what x should be
        y_source = y.lower().split()[0]
        if len(x) > 0:
            if not x.lower().endswith('time'):
                output['x'] = self.data.get_data(x.lower())
            else:
                # some data (ex. validation) does not necessarily line up with the MapCO2/ASVCO2 cannonical times, so try to get their timestamps first.
                x_val = y_source + ' time' if y_source in self.data.available_data_sources() else x
                output['x'] = output['x'] = self.data.get_data(x_val)
        else:
            # default x as time, first as time from y's source data or merge time
            x = y_source + ' time' if y_source in self.data.available_data_sources() else 'merge time'
            output['x'] = self.data.get_data(x)
        
        # handle marker kw (specifies marker properties like color) which needs special handling because of qc parameters.
        marker = param_dict.pop('marker', None)
        y_split = y.lower().split()
        y_source, y_data = y_split[0], y_split[-1]
        if marker is not None:
            output['marker'] = self._handle_marker_color(y_source, y_data, marker)
        else: # if a color isn't provided, default to the predefined color of the data.
            c_source = self.colors.get(y_source, self.colors['merge'])
            c_data = c_source.get(y_data, c_source['default'])
            output['marker'] = {'color': c_data}
        
        # handle other supplementary parameters provided in param_dict
        for spec_type, param in param_dict.items():
            output[spec_type] = self.data.get_data(param.lower())
        return output
    
    def _handle_marker_color(self, y_source: str, y_data: str, marker_dict: dict):
        """
            The color parameter of marker can be set as a variable. Substitute color (when specified) with data.
            Handles qc parameters (names that end with '_qc') by converting different qc flags to particular color codes.
            
            :param y_source: (str) the name of the source (ex. merge) containing the y_data column.
                             Used when the provided color parameter is a qc parameter.
            :param y_data: (str) name of the data column in the y_source.
                           Used when the provided color parameter is a qc parameter.
            :param marker_dict: (dict) contains the marker information (among other metadata).
                                The value of the marker key will be replaced with an array containing
                                either actual data or color codes (for qc data).
            
            :output: (dict) modified marker_dict with value of 'marker' key substituted with appropriate data.
        """
        
        color = marker_dict.get('color', None)
        isQC = True if color and color.endswith('_qc') else False
        if color is not None:
            color = self.data.get_data(color.lower())
            if len(color) == 1:
                color = color[0] if type(color[0]) == str else None  # presume users have specified the color correctly.
            elif isQC:
                c_source = self.colors.get(y_source, self.colors['merge'])
                c_data = c_source.get(y_data, c_source['default'])
                marker_dict['symbol'] = np.array(['circle' if i == 1 else 'x' for i in color])
                marker_dict['line'] = {'width': 1, 'color': np.array([c_data if i == 1 else '#ffae42' for i in color])}
                color = np.array([c_data if i == 1 else '#1c4003' for i in color])
            # TODO: handle if string color input not in acceptable list, default to value
        marker_dict['color'] = color
        
        return marker_dict
    
    def initialization(self):
        return self.inits
    
    def plots(self):
        return self.plot_specs
    
    def x_axes(self):
        return self.x_axes_specs
    
    def y_axes(self):
        return self.y_axes_specs
