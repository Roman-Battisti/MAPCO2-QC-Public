# standard libraries
from copy import deepcopy
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


class MultiYearPlotter:
    """
        Plots multi-year data using day-of-year (adjusted for time) rather than datetime.
        
        :param standard_plots: (list[str]) list of parameter names to be plotted.
        :param data_acces_object: (netCDFaccess) data storage object.
    """
    
    def __init__(self, standard_plots: list, data_access_object, use_colorblind=False):
        self.data = data_access_object
        self._check_for_standard_plot_data(standard_plots)
        self._get_year_range()
        self.use_colorblind = use_colorblind
    
    def _check_for_standard_plot_data(self, standard_plots: list):
        """
            Check that all standard plot variables have data. If not,
            remove variable from standard_plots list.
        """
        
        self.standard_plots = []
        for pl in standard_plots:
            if pl.lower() in self.data.available_merge_columns():
                self.standard_plots.append(pl)
    
    def _get_year_range(self):
        """
            Find minimum year and maximum year in dataset (including historic data, if available).
            Used to standardize the color of a year across multiple plots.
        """
        
        dt = pd.to_datetime(self.data.get_full_timeseries(['merge time'])[0])
        
        self.min_year = min(dt).year
        self.max_year = max(dt).year
    
    def _get_data(self, param: str):
        """
            Return formatted dataframe including day-of-year adjusted
            for time of day.
            
            :param param: (str) name of parameter column.
        """
        
        all_data = self.data.get_full_timeseries(['merge time', 'merge ' + param.lower()])
        if type(all_data[0]) == str:
            return param
        
        dt = pd.DatetimeIndex(all_data[0])
        formatted_dt = dt.strftime("%d %b %y, %H:%M")
        dt_year = dt.year
        dt_day_of_year = np.array([int(i.strftime('%j')) + round(i.hour / 24 + i.minute / (24 * 60), 2) for i in dt])
        
        return pd.DataFrame({'datetime': formatted_dt, 'day_of_year': dt_day_of_year, 'year': dt_year, 'data': all_data[1]})
    
    def _data_generator(self, data):
        """
            Used to group data by year for iteration.
            Each year will be a separate trace in the Plotly figure
            
            :param data: (pd DataFrame) contains a year column (to groupby), day-of-year, and parameter data.
        """
        year_group = data.groupby('year')
        for yr, yr_data in year_group:
            yield yr, yr_data
    
    def plot(self, colorscale='rainbow'):
        """
            Plot data using Plotly offline, creating an html file. Plots are based on provided standard plots
            and available data.
            
            :param colorscale: specify the colorscale to use in the Plotly figure.
        """
        
        if self.use_colorblind:
            colorscale = 'bluered'
        
        initialize = {'cols': 1, 'rows': len(self.standard_plots),
                      'vertical_spacing': 0.03,
                      'subplot_titles': self.standard_plots}
        fig = make_subplots(**initialize)
        
        # Create each plot in the figure
        row = 0
        for p in self.standard_plots:
            p_data = self._get_data(p)
            if type(p_data) == str:
                # in case data doesn't exist, skip over this plot.
                continue
            # create each trace in the plot.
            for yr, yr_data in self._data_generator(p_data):
                if yr_data['data'].isnull().all():
                    # so as not to have extra legend entries for years with zero data
                    continue
                # additional methods for below: https://plotly.com/python-api-reference/generated/plotly.colors.html
                yr_color = plotly.colors.sample_colorscale(colorscale, [(yr - self.min_year) / max((self.max_year - self.min_year), 1)])[0]
                params = {'x': yr_data['day_of_year'], 'y': yr_data['data'], 'name': ' '.join([str(yr), p]), 'text': yr_data['datetime'], 'mode': 'markers', 'marker': {'color': yr_color}}
                params['hovertemplate'] = "%{text}<br>" + f"<b>{p}</b>: " + "%{y:.2f}<extra></extra>" 
                fig.add_trace(go.Scatter(**params), **{'row': row + 1, 'col': 1})
            
            # specify additional metadata for plot.
            x_axis_specs = {'title_text': 'Day of Year', 'row': row + 1, 'col': 1}
            if row > 0:
                x_axis_specs['matches'] = 'x1'
            y_axis_specs = {'title_text': p, 'row': row + 1, 'col': 1}
            fig.update_yaxes(**y_axis_specs)
            fig.update_xaxes(**x_axis_specs)
            
            row += 1
                
        fig.update_layout(hovermode='x', height=700 * len(self.standard_plots))

        return fig
