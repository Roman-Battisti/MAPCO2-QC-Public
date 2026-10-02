import os
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import yaml

import numpy as np
import pandas as pd

import docx
import ipywidgets as widgets
import matplotlib as mpl
import matplotlib.pyplot as plt
import netCDF4
import pickle
import xarray as xr

# internal code
from . import align_arrays
from .netcdf_to_pandas import HistoricalColumnSelector
from xco2qc.core import MERGE_NCFILE, MODELS_FILE, HISTORICAL_NCFILE
from xco2qc.core.licor import APOFF_NCFILE
from xco2qc.browse import qt_browse
from xco2qc.mbl import MBL
from xco2qc.remote_climatology import ChlCache, OpenDAPO2Climatology

plt.rcParams.update({'font.size': 22})

column_mapping_standard = {
                           'sst (c)': 'SST',
                           'salinity':  'SSS',
                           'xco2 sw (dry) (umol/mol)': 'xCO2_sw',
                           'xco2 air (dry) (umol/mol)': 'xCO2_air',
                           'pco2 sw (sat) uatm': 'pCO2_sw',
                           'pco2 air (sat) uatm': 'pCO2_air',
                           'dpco2': 'dpCO2'
                          }
column_mapping_aux = {
                      'ph (total scale)': 'pH_sw',
                      'chl': 'CHL (night time)',
                      'chl (ug/l)': 'CHL (night time)',
                      'ntu': 'NTU',
                      'ntu (ntu)': 'NTU',
                      'doxy': 'DOXY',
                      'doxy (umol/kg)': 'DOXY'
                     }
mergenc_mapping = {
                   'SST': 'SST',
                   'SSS': 'SSS',
                   'xCO2_sw': 'xCO2_sw',
                   'xCO2_air': 'xCO2_air',
                   'pH_sw': 'pH_sw',
                   'CHL (night time)': 'chl_nighttime',
                   'NTU': 'ntu',
                   'DOXY': 'dissolved_oxygen'
                  }
column_mapping_historic = {
                           'time': 'datetime',
                           'latitude': 'latitude',  # for mbl comparison
                           'longitude': 'longitude',
                           'sst': 'SST',
                           'sss': 'SSS',
                           'pco2_sw': 'pCO2_sw',
                           'pco2_air': 'pCO2_air',
                           'xco2_air': 'xCO2_air',
                           'ph_sw': 'pH_sw',
                           'doxy': 'DOXY',
                           'dissolved_oxygen': 'DOXY',
                           'chl': 'CHL (night time)',
                           'chl_nighttime': 'CHL (night time)',
                           'ntu': 'NTU',
                          }

qf_columns = {
              'xCO2_sw': 'co2 sw qf',
              'xCO2_air': 'co2 air qf',
              'pH_sw': 'ph qf',
              'CHL (night time)': 'chl qf',
              'NTU': 'ntu qf',
              'DOXY': 'doxy qf'
             }
qflog_mapping = {
                 'CHL (night time)': 'chl_nighttime',
                 'NTU': 'ntu',
                 'DOXY': 'dissolved_oxygen',
                }
parameter_unit_mapping = {
                          'SST': r'[$^\circ$C]',
                          'SSS': '[PSU]',
                          'xCO2_air': r'[$\mu$atm]',
                          'xCO2_sw': r'[$\mu$atm]',
                          'pCO2_air': r'[$\mu$atm]',
                          'pCO2_sw': r'[$\mu$atm]',
                          'fCO2_air': r'[$\mu$atm]',
                          'fCO2_sw': r'[$\mu$atm]',
                          'dpCO2': r'[$\mu$atm]',
                          'pH_sw': '',
                          'CHL (night time)': r'[$\mu$g/l]',
                          'NTU': r'',
                          'DOXY': r'[$\mu$mol/kg]'
                         }

standard_colors = {'good': 'b',
                   'questionable': 'orange',
                   'bad': 'red',
                   'climatology': 'g',
                  }
colorblind_colors = {
                     'good': '#0072B2',
                     'questionable': '#E69F00',
                     'bad': '#D55E00',
                     'climatology': '#009E73',
                    }

file_name_pattern = r"^(?P<system_name>[\w\d]+)_((?P<long>\d+\w)_(?P<lat>\d+\w)_)*(?P<start_date>\w{3}\d{4})_(?P<end_date>\w{3}\d{4})"
csv_file_name = re.compile(file_name_pattern, flags=re.IGNORECASE)
qflog_file_name = re.compile(file_name_pattern + '_QFlog', flags=re.IGNORECASE)


class ReportWriterWidget:
    def __init__(self, src_dir='', station_name='', deployment_number=1, use_colorblind=False):
        self.build_subwidgets(src_dir, station_name, deployment_number)
        self.use_colorblind = use_colorblind
        
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass
    
    def run(self):
        src_row = widgets.HBox([self.src_dir_input, self.load_project_button])
        layout = widgets.VBox([src_row, self.station_name_input, self.deployment_number_input, self.write_summary_document_button])
        
        return layout
    
    def build_subwidgets(self, src_dir, station_name, deployment_number):
        self.load_project_button = widgets.Button(description='Select QC Directory')
        self.load_project_button.on_click(self._open_file_dialog)
        
        self.src_dir_input = widgets.Text(value=str(src_dir), description='Source Directory', disabled=True)
        self.station_name_input = widgets.Text(value=station_name, description='Station Name', continuous_update=False)
        
        self.deployment_number_input = widgets.IntText(value=deployment_number, description='Deployment Number')
        
        self.write_summary_document_button = widgets.Button(description='Write Summary')
        self.write_summary_document_button.on_click(self._write_document)
    
    def _open_file_dialog(self, b):
        temp_src_dir = qt_browse(Path.home(), text='Select a directory', is_dir=True)
        if temp_src_dir.is_dir():
            self.src_dir_input.value = str(temp_src_dir)
            self.src_dir_input.style.background = None
    
    def _write_document(self, b):
        if not self._check_fields():
            return

        self.write_summary_document_button.description = "Writing Summary..."
        self.write_summary_document_button.disabled = True
        station_metadata = {
                            'station name': self.station_name_input.value,
                            'deployment number': self.deployment_number_input.value
                           }
        try:
            with ReportWriter(self.src_dir_input.value, station_metadata, use_colorblind=self.use_colorblind) as writer:
                writer.write_summary_document()
        except Exception as e:
            raise e
        finally:
            self.write_summary_document_button.description = "Write Summary"
            self.write_summary_document_button.disabled = False
    
    def _check_fields(self):
        """
        Check fidelity of inputs before attempting to write summary report. Highlight in red incorrect fields for user.
        De-highlight if fields are correct.
        """
        
        can_process = True
        
        if self.src_dir_input.value is None or not Path(self.src_dir_input.value).is_dir():
            self.src_dir_input.style.background = 'red'
            can_process = False
        else:
            self.src_dir_input.style.background = None
        
        if self.station_name_input.value is None or len(self.station_name_input.value) == 0:
            self.station_name_input.style.background = 'red'
            can_process = False
        else:
            self.station_name_input.style.background = None
        
        if self.deployment_number_input.value is None:
            self.deployment_number_input.style.background = 'red'
            can_process = False
        else:
            self.deployment_number_input.style.background = None
        
        return can_process
        

class ReportWriter:
    # https://python-docx.readthedocs.io/en/latest/user/quickstart.html
    def __init__(self, src_dir, station_metadata: dict, use_colorblind=False):
        self.src_dir = Path(src_dir)
        if (self.src_dir / 'merge').is_dir():
            self.dst_dir = self.src_dir / 'merge'
        else:
            self.dst_dir = self.src_dir
        
        self.station_metadata = station_metadata
        
        self.use_colorblind = use_colorblind
        self.color_palette = standard_colors if not use_colorblind else colorblind_colors
        
        self.deployment_data = None
        self.deployment_qflog = None
        self.historic_data = None
        self.deployment_metadata = None
        
        self.standard_plotters = {}
        self.aux_plotters = {}
        self.derived_plotters = {}
        self.climatology_plotters = {}
        self.mbl_plotter = None
        
        self.doc = docx.Document()
        self.setup_doc_style()
        self._load_data()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass
    
    def setup_doc_style(self):
        # https://stackoverflow.com/a/29421050
        obj_styles = self.doc.styles
        obj_charstyle = obj_styles.add_style('SubHeaderStyle', docx.enum.style.WD_STYLE_TYPE.CHARACTER)
        obj_font = obj_charstyle.font
        obj_font.size = docx.shared.Pt(14)
        
        obj_charstyle2 = obj_styles.add_style('StandardStyle', docx.enum.style.WD_STYLE_TYPE.CHARACTER)
        obj_font2 = obj_charstyle2.font
        obj_font2.size = docx.shared.Pt(12)

    def write_summary_document(self):
        self._add_intro()
        self._add_summary()
        self._add_statistics()
        self._add_standard_plots()
        self._add_mbl_comparison()
        self._add_aux_plots()
        self._add_multiparameter_plots()
        self.doc.add_page_break()
        self._add_time_series()
        
        save_name = f"{self.station_metadata.get('station name', 'STATION')} Deployment {self.station_metadata.get('deployment number', 1)} Summary.docx"
        try:
            self.doc.save(self.dst_dir / save_name)
        except PermissionError:
            print(f"PermissionError: Document named '{save_name}' currently open, could not save!")
    
    def _load_data(self):
        # load SOCAT csv and SOCAT qf_log
        files = [f for f in self.dst_dir.glob('**/*') if f.is_file()]
        for f in files:
            if (f.suffix == '.csv') and (m:=qflog_file_name.match(f.stem)):
                self.deployment_qflog = pd.read_csv(f)
            elif (f.suffix == '.csv') and (m:=csv_file_name.match(f.stem)):
                self.deployment_data = pd.read_csv(f, skiprows=4)
            elif (f.suffix == '.xml') and (m:=csv_file_name.match(f.stem)):
                self.station_metadata['user_name'] = get_qcer_name(f)

        # check that the deployment data actually exists otherwise we can't write the summary report.
        if self.deployment_data is None or self.deployment_qflog is None:
            raise(DirectoryStructureException(message='Final SOCAT csv and/or qflog files cound not be found'))
        
        self.historic_data = get_historic_data(self.src_dir / 'trimmed' / HISTORICAL_NCFILE)
        
        try:
            with xr.open_dataset(self.dst_dir / MERGE_NCFILE) as ds:
                ds = ds.load()
                self.merge_ds = ds
        except (ValueError, FileNotFoundError):
            raise(DirectoryStructureException(message=f'{MERGE_NCFILE} could not be found'))
        
        config_path = self.src_dir / 'config.yml'
        if config_path.exists():
            with config_path.open() as f:
                self.config = yaml.safe_load(f)
        else:
            self.config = None
        
        self._process_dataframes()
        self._build_plotters()
        self._get_climatologies()

    def _process_dataframes(self):
        self.deployment_data['datetime'] = pd.to_datetime(self.deployment_data['Date'] + ' ' + self.deployment_data['Time'])
        self.deployment_data.index = self.deployment_data['datetime']
        self.deployment_data.columns = [col.lower() for col in self.deployment_data.columns]

        self.deployment_qflog.rename(columns={'Date/Time': 'datetime'}, inplace=True)
        self.deployment_qflog['datetime'] = pd.to_datetime(self.deployment_qflog['datetime'])
        self.deployment_qflog.index = self.deployment_qflog['datetime']
    
    def _build_plotters(self):
        for k, v in column_mapping_standard.items():
            self.standard_plotters[v] = ParameterPlotter(v, parameter_unit_mapping[v], *self._get_data(k, v))
        
        for k, v in column_mapping_aux.items():
            if mergenc_mapping[v] in self.merge_ds and k in self.deployment_data.columns:
                self.aux_plotters[v] = ParameterPlotter(v, parameter_unit_mapping[v], *self._get_data(k, v))
    
    def _get_data(self, col_name, param_name):
        if col_name not in self.deployment_data.columns:
            return None, None, None, None
            
        if qf_columns.get(param_name, False):
            good_data = self.deployment_data.loc[self.deployment_data[qf_columns[param_name]] == 2, col_name]
        else:  # handle parameters with no QC column (ex. SST, SSS, etc)
            good_data = self.deployment_data.loc[self.deployment_data[col_name] > -900, col_name]
        if good_data.shape[0] == 0:
            good_data = None
        
        qf_groups = self.deployment_qflog.groupby('Parameter')
        if qflog_mapping.get(param_name, param_name) in qf_groups.groups.keys():
            qf_flags = qf_groups.get_group(qflog_mapping.get(param_name, param_name)).groupby('QF')
            questionable_data = qf_flags.get_group(3)['Value'] if 3 in qf_flags.groups.keys() else None
            bad_data = qf_flags.get_group(4)['Value'] if 4 in qf_flags.groups.keys() else None
        else:
            questionable_data = None
            bad_data = None
        historic_data = self.historic_data[param_name] if self.historic_data is not None and param_name in self.historic_data.columns else None
        
        return good_data, questionable_data, bad_data, historic_data, self.use_colorblind
    
    def _get_climatologies(self):
        deployment_longlat_df = self.deployment_data[['longitude', 'latitude']].copy()
        deployment_longlat_df.replace(-999, float('nan'), inplace=True)
        deployment_longlat_df = deployment_longlat_df.loc[(deployment_longlat_df['longitude'] >= -180) & (deployment_longlat_df['latitude'] >= -90), :]
        deployment_longlat_df = deployment_longlat_df.astype(np.float32)
        deployment_climatologies = get_climatologies(deployment_longlat_df, self.config)
        
        if self.historic_data is not None:
            if 'longitude' not in self.historic_data or 'latitude' not in self.historic_data:
                # since currently underway data doesn't have historic data, we will use the current deployment's lat/long
                self.historic_data['longitude'] = deployment_longlat_df.loc[~deployment_longlat_df['longitude'].isnull(), 'longitude'].iloc[0]
                self.historic_data['latitude'] = deployment_longlat_df.loc[~deployment_longlat_df['latitude'].isnull(), 'latitude'].iloc[0]
            historic_climatologies = get_climatologies(self.historic_data[['longitude', 'latitude']], self.config)
        else:
            historic_climatologies = {k: None for k in deployment_climatologies.keys()}
        
        for param in ['CHL (night time)', 'DOXY']:
            climatology_data = [deployment_climatologies[param], None, None, historic_climatologies[param], self.use_colorblind]
            self.climatology_plotters[param] = ParameterPlotter(param, parameter_unit_mapping[param], *climatology_data)
            
    def _add_intro(self):
        title = f"{self.station_metadata['station name']} Deployment {self.station_metadata['deployment number']}"
        self.doc.add_heading(title, 0)
        timespan = f"{min(self.deployment_data['datetime']).strftime('%d %b %Y')} - {max(self.deployment_data['datetime']).strftime('%d %b %Y')}"
        p = self.doc.add_paragraph()
        p.add_run(f"Final deployment timespan: {timespan}", style='SubHeaderStyle')
        if m:=self.station_metadata.get('user_name', False):
            p2 = self.doc.add_paragraph()
            p2.add_run(f"Data QC analyst: {m}", style='SubHeaderStyle')

    def _add_summary(self):
        self.doc.add_heading('Summary', 1)
        
        # check if data post processed by user
        trimmed_apoff_path = self.src_dir / 'trimmed' / APOFF_NCFILE
        with xr.open_dataset(trimmed_apoff_path) as ds:
            if 'post_xco2_dry' in ds:
                text = "This deployment was post-processed. "
            else:
                text = "This deployment was not post-processed. "
        model_path = self.src_dir / 'reduced' / MODELS_FILE
        if model_path.is_file():
            lr_statements = get_temp_coeff_corr(model_path)
            num_regions = len(lr_statements)
            text += f"There {'was' if num_regions == 1 else 'were'} {'no' if num_regions == 0 else num_regions} Linear Regression region{'s' if num_regions != 1 else ''} between Licor Temperature and Span Coefficient found{'.' if num_regions == 0 else ':'}"
            l = self.doc.add_paragraph(text, style='List Bullet')
            
            for s in lr_statements:
                self.doc.add_paragraph(s, style='List Bullet 2')
        self.doc.add_paragraph('', style='List Bullet')
        
        self.doc.add_paragraph()
    
    def _add_statistics(self):
        self.doc.add_heading('Quality Flag Statistics', 1)
        
        stats_df = self.deployment_data[[col for k, col in qf_columns.items() if mergenc_mapping[k] in self.merge_ds and col in self.deployment_data.columns]].copy()
        stats_df.rename(columns={v: k for k, v in qf_columns.items()}, inplace=True)
        stats = flag_statistics(stats_df)
        table_col_names = ['Parameter', 'Flag 2', 'Flag 3', 'Flag 4', 'Flag 5']

        table = self.doc.add_table(rows=1, cols=len(table_col_names))
        table.style = 'Colorful List'
        title_row = table.rows[0].cells
        for i in range(len(table_col_names)):
            title_row[i].text = table_col_names[i]  # to add text to (row, column), values must be str
        for param in stats:
            data_row = table.add_row().cells
            for i in range(len(param)):
                data_row[i].text = param[i]
        self.doc.add_paragraph()
    
    def _add_standard_plots(self):
        self.doc.add_heading('SST and SSS', level=1)
        self._write_plots([p.parameter_plot() for p in self._get_plotters(self.standard_plotters, ['SST', 'SSS'])])
        self.doc.add_heading('xCO2 Air and xCO2 SW', level=1)
        self._write_plots([p.parameter_plot() for p in self._get_plotters(self.standard_plotters, ['xCO2_air', 'xCO2_sw'])])
        
    def _add_mbl_comparison(self):
        mbl_corr = mbl_correction(self.src_dir / 'merge' / 'merge.nc')
        mbl = MBL()
        
        xco2_historic, historic_mbl_values, historic_comparison, historic_avg, historic_std = None, None, None, None, None
        if self.historic_data is not None:
            xco2_historic = self.historic_data['xCO2_air']
            lat_historic = self.historic_data['latitude']
            historic_mbl_values, historic_comparison = compare_xco2_with_mbl(xco2_historic, lat_historic, mbl)
            historic_avg = round(np.nanmean(historic_comparison.values), 1)
            historic_std = round(np.nanstd(historic_comparison.values), 1)
        
        # if QC'er applied an MBL correction, we need to remove that correction to produce the MBL comparison plot
        xco2 = self.deployment_data['xco2 air (dry) (umol/mol)'].copy()
        xco2[xco2 < 0] = float('nan')
        if mbl_corr is not None:
            xco2 -= mbl_corr  # uncorrected xCO2 air
        lat = self.deployment_data['latitude']
        dp_mbl_values, dp_comparison = compare_xco2_with_mbl(xco2, lat, mbl)
        dp_avg = round(np.nanmean(dp_comparison), 1)
        try:  # may only have 1 comparison
            dp_std = round(np.nanstd(dp_comparison), 1)
        except ZeroDivisionError:
            dp_std = 0
            
        current_historic_mbl_diff = dp_avg - historic_avg if historic_avg is not None else None
        self.mbl_plotter = ParameterPlotter('MBL', parameter_unit_mapping['xCO2_air'], parameter_data_good=dp_mbl_values, historic_data=historic_mbl_values, use_colorblind=self.use_colorblind)
        
        self.doc.add_heading('MBL Comparison', level=1)
        p = self.doc.add_paragraph()
        text = ''
        text += f"The average offset between historic xCO2 Air and MBL is {historic_avg} ± {historic_std} μatm. " if historic_avg is not None else ""
        text += f"The average offset between deployment {self.station_metadata['deployment number']}'s xCO2 Air and MBL is {dp_avg} ± {dp_std} μatm"
        text += f", suggesting an offset between this deployment and historic data of {round(current_historic_mbl_diff, 1)} μatm. " if current_historic_mbl_diff is not None else ". "
        text += f"The current, applied offset is {mbl_corr} μatm." if mbl_corr is not None else "No MBL correction has been applied at this time."
        
        p.add_run(text, style='StandardStyle')
        self.doc.add_paragraph()
        self._write_plots([self._plot_mbl(xco2, dp_mbl_values, dp_comparison, xco2_historic, historic_mbl_values, historic_comparison)])
        
    def _plot_mbl(self, dp_xco2, dp_mbl, dp_diff, historic_xco2=None, historic_mbl=None, historic_diff=None):
        fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(20, 15))
        marker_size = 100
        if historic_xco2 is not None:
            ax1.scatter(historic_xco2.index, historic_xco2.to_numpy(), s=marker_size, c=self.color_palette['good'], label='historic xCO2 Air')
        ax1.scatter(dp_xco2.index, dp_xco2.to_numpy(), s=marker_size, c=self.color_palette['bad'], label=f"Deployment {self.station_metadata['deployment number']} xCO2 Air")
        if self.mbl_plotter is not None:
            self.mbl_plotter.add_historic_line(ax1, color_code=self.color_palette['climatology'], label='MBL')
            self.mbl_plotter.add_deployment_line(ax1, color_code=self.color_palette['climatology'], label=None)
        ax1.set_ylabel(f"xCO2 Air {parameter_unit_mapping['xCO2_air']}")
        ax1.legend()
        ax1.grid(True)
        
        if historic_diff is not None:
            ax2.scatter(historic_diff.index, historic_diff.to_numpy(), s=marker_size, c=self.color_palette['good'])
        ax2.scatter(dp_diff.index, dp_diff.to_numpy(), s=marker_size, c=self.color_palette['bad'])
        ax2.set_ylabel(f"xCO2 Air-MBL Difference {parameter_unit_mapping['xCO2_air']}")
        ax2.grid(True)
        
        fig.tight_layout()
        return fig
    
    def _add_aux_plots(self):
        if 'pH_sw' in self.aux_plotters:
            self.doc.add_heading('pH', level=1)
            self._write_plots([self.aux_plotters['pH_sw'].parameter_plot()])
        
        aux_plots = []
        for param in ['CHL (night time)', 'NTU', 'DOXY']:
            if param not in self.aux_plotters:
                continue
            fig, ax = self.aux_plotters[param].parameter_plot(return_ax=True)
            if param in self.climatology_plotters:
                self.climatology_plotters[param].add_deployment_line(ax, color_code=self.color_palette['climatology'], label='Climatology')
            ax.legend()
            aux_plots.append(fig)
            
        if len(aux_plots) > 0:
            self.doc.add_heading('Auxiliary Sensors', level=1)
            self._write_plots(aux_plots)
    
    def _add_multiparameter_plots(self):
        self.doc.add_heading('Multi-parameter plots', level=1)
        xco2_sw_plotter = self.standard_plotters['xCO2_sw']
        plots = []
        for param in [self.standard_plotters.get('SST', False), self.aux_plotters.get('pH_sw', False), self.aux_plotters.get('DOXY', False)]:
            if param:
                fig, ax = xco2_sw_plotter.build_plot()
                xco2_sw_plotter.add_deployment_timeseries(ax, color_code=self.color_palette['good'], label=xco2_sw_plotter.parameter_name)
                ax2 = ax.twinx()
                param.add_deployment_timeseries(ax2, color_code=self.color_palette['bad'], label=param.parameter_name)
                ax2.set_ylabel(f'{param.parameter_name} {param.parameter_units}')
                if param.parameter_name == 'pH_sw':
                    ax2.yaxis.set_inverted(True)
                lines, labels = ax.get_legend_handles_labels()
                lines2, labels2 = ax2.get_legend_handles_labels()
                ax2.legend(lines + lines2, labels + labels2, loc=0)
                plots.append(fig)
        for param in ['air', 'sw']:
            xco2_plotter = self.standard_plotters[f'xCO2_{param}']
            pco2_plotter = self.standard_plotters[f'pCO2_{param}']
            
            # build associated fCO2 plotter
            param_name = f'fCO2_{param}'
            param_csv_name = f'fco2 {param} (sat) uatm'
            fco2_plotter = ParameterPlotter(param_name, parameter_unit_mapping[param_name], *self._get_data(param_csv_name, param_name))
            
            fig, ax = xco2_plotter.build_plot()
            xco2_plotter.add_deployment_timeseries(ax, color_code=self.color_palette['good'], label=xco2_plotter.parameter_name)
            pco2_plotter.add_deployment_timeseries(ax, color_code=self.color_palette['questionable'], label=pco2_plotter.parameter_name)
            fco2_plotter.add_deployment_timeseries(ax, color_code=self.color_palette['bad'], label=fco2_plotter.parameter_name)
            ax.legend()
            plots.append(fig)
        
        self._write_plots(plots)
    
    def _add_time_series(self):
        self.doc.add_heading('Time Series and Day of Year Plots', level=1)
        for plotter_dict in [self.standard_plotters, self.derived_plotters, self.aux_plotters]:
            for param, plotter in plotter_dict.items():
                if param == 'xCO2_sw':
                    continue
                self.doc.add_heading(param, level=2)
                fig, ax = plotter.timeseries_plot(return_ax=True)
                if param in self.climatology_plotters:
                    self.climatology_plotters[param].add_historic_line(ax, color_code=self.color_palette['climatology'], label='Climatology')
                    self.climatology_plotters[param].add_deployment_line(ax, color_code=self.color_palette['climatology'], label=None)
                elif param == 'xCO2_air' and self.mbl_plotter is not None:
                    self.mbl_plotter.add_historic_line(ax, color_code=self.color_palette['climatology'], label='MBL')
                    self.mbl_plotter.add_deployment_line(ax, color_code=self.color_palette['climatology'], label=None)
                ax.legend()
                self._write_plots([fig, plotter.yearday_plot()])
    
    def _get_plotters(self, plotter_dict: dict, params: list):
        plots = []
        for p in params:
            if plotter:=plotter_dict.get(p, False):
                plots.append(plotter)
        if len(plots) == 0:
            return []
        return plots
    
    def _write_plots(self, plots: list):
        fig_save_path = os.path.join(self.dst_dir, 'temp.png')
        
        for p in plots:
            p.savefig(fig_save_path, bbox_inches='tight')
            plt.close(p)
            self.doc.add_picture(fig_save_path, docx.shared.Inches(6))
            os.remove(fig_save_path)
            

class ParameterPlotter:
    def __init__(self, parameter_name, parameter_units, parameter_data_good=None, parameter_data_questionable=None, parameter_data_bad=None, historic_data=None, use_colorblind=False):
        self.parameter_name = parameter_name
        self.parameter_units = parameter_units
        self.data_good = parameter_data_good
        self.data_questionable = parameter_data_questionable
        self.data_bad = parameter_data_bad
        self.historic = historic_data
        self.figsize = (20, 10)
        self.markersize = 100
        self.linewidth = 5
        self.use_colorblind = use_colorblind
        self.color_palette = standard_colors if not use_colorblind else colorblind_colors
        
        # self.remove_nonsensical_data()
    
    def remove_nonsensical_data(self):
        """Temporary measure to handle random aberrant data in historical record."""
        lower_range = None
        upper_range = None
        # if 'doxy' in self.parameter_name.lower():
        #     lower_range = 100
        #     upper_range = 375
        # elif 'co2' in self.parameter_name.lower():
            # note: this also includes dpco2/dfco2/dxco2 data
        #     lower_range = -1000
        #     upper_range = 1000
        
        # if lower_range is not None and upper_range is not None and self.historic is not None:
        #     index = (self.historic.to_numpy() < lower_range) | (self.historic.to_numpy() > upper_range)
        #     self.historic[index] = float('nan')
        
        # if 'sss' in self.parameter_name.lower():
        #     index = self.historic.to_numpy() < 5
        #     self.historic[index] = float("nan")
    
    def build_plot(self):
        fig, ax = plt.subplots(figsize=self.figsize)
        ax.set_ylabel(f'{self.parameter_name} {self.parameter_units}')
        ax.grid(True)
        fig.tight_layout()
        
        return fig, ax
    
    def parameter_plot(self, return_ax=False):
        fig, ax = self.build_plot()
        
        if self.data_good is not None:
            ax.scatter(self.data_good.index, self.data_good.to_numpy(), s=self.markersize, c=self.color_palette['good'], label='Flag 2')
        if self.data_questionable is not None:
            ax.scatter(self.data_questionable.index, self.data_questionable.to_numpy(), s=self.markersize, c=self.color_palette['questionable'], label='Flag 3')
        if self.data_bad is not None:
            ax.scatter(self.data_bad.index, self.data_bad.to_numpy(), s=self.markersize, c=self.color_palette['bad'], label='Flag 4')
        ax.legend()
        
        if return_ax:
            return fig, ax
        else:
            return fig
    
    def yearday_plot(self, return_ax=False):
        fig, ax = self.build_plot()
        
        concat_data = []
        for d in [self.historic, self.data_questionable, self.data_good]:
            if d is not None:
                concat_data.append(d)
        if len(concat_data) == 1:
            full_timeseries = concat_data[0]
        elif len(concat_data) == 0:
            if return_ax:
                return fig, ax
            else:
                return fig
        else:
            full_timeseries = pd.concat(concat_data)
        # if self.historic is not None:
        #     full_timeseries = pd.concat([self.historic, self.data_good, self.data_questionable])
        # elif self.data_questionable is not None:
        #     full_timeseries = pd.concat([self.data_good, self.data_questionable])
        # else:
        #     full_timeseries = self.data_good
        
        day_of_year = np.array([int(dt.strftime('%j')) + round(dt.hour / 24 + dt.minute / (24 * 60), 2) for dt in full_timeseries.index])
        full_timeseries = pd.DataFrame({'param': full_timeseries.to_numpy(), 'day_of_year': day_of_year}, index=full_timeseries.index)
        
        yr_groups = full_timeseries.groupby(full_timeseries.index.year)
        
        min_year = min(full_timeseries.index.year)
        max_year = max(full_timeseries.index.year)
        
        for yr, data in yr_groups:
            yr_increment = (yr - min_year) / max(max_year - min_year, 1)
            if not self.use_colorblind:
                color = plt.cm.rainbow(yr_increment)  # https://matplotlib.org/stable/gallery/color/individual_colors_from_cmap.html
            else:
                color = plt.cm.inferno(yr_increment)
            ax.scatter(data['day_of_year'], data['param'], s=self.markersize, color=color, label=yr)
        ax.set_xlabel('Day of Year')
        ax.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        
        if return_ax:
            return fig, ax
        else:
            return fig
    
    def timeseries_plot(self, return_ax=False):
        fig, ax = self.build_plot()
        self.add_historic_timeseries(ax, color_code=self.color_palette['good'])
        self.add_deployment_timeseries(ax, self.color_palette['bad'])
        ax.legend()
        
        if return_ax:
            return fig, ax
        else:
            return fig
    
    def add_historic_timeseries(self, ax, color_code, label='Historic'):
        if self.historic is not None:
            ax.scatter(self.historic.index, self.historic.to_numpy(), s=self.markersize, marker='.', c=color_code, label=label)
        return ax
    
    def add_deployment_timeseries(self, ax, color_code, label='Current Deployment'):
        if self.data_questionable is not None and self.data_good is not None:
            deployment = pd.concat([self.data_good, self.data_questionable])
        elif self.data_questionable is not None:
            deployment = self.data_questionable
        else:
            deployment = self.data_good
        if deployment is not None:
            ax.scatter(deployment.index, deployment.to_numpy(), s=self.markersize, c=color_code, label=label)
        return ax
    
    def add_historic_line(self, ax, color_code='b', label='Historic'):
        if self.historic is not None:
            ax.plot(self.historic.index, self.historic.to_numpy(), linewidth=self.linewidth, c=color_code, label=label)
        return ax
    
    def add_deployment_line(self, ax, color_code='r', label='Current Deployment'):
        if self.data_questionable is not None and self.data_good is not None:
            deployment = pd.concat([self.data_good, self.data_questionable])
        elif self.data_questionable is not None:
            deployment = self.data_questionable
        else:
            deployment = self.data_good
        if deployment is not None:
            ax.plot(deployment.index, deployment.to_numpy(), linewidth=self.linewidth, c=color_code, label=label)
        return ax


def get_qcer_name(metadata_filepath):
    deployment_metadata = ET.parse(metadata_filepath)
    for child in deployment_metadata.getroot():
        if child.tag == 'User':
            for sub_child in child:
                if sub_child.tag == 'Name':
                    return sub_child.text
    return ''


def get_historic_data(historic_file_path):
    if not historic_file_path.is_file():
        return None
    
    data_selector = HistoricalColumnSelector(historic_file_path)
    historic_df = data_selector.df
    restricted_historic_mapping = {}
    for k, v in column_mapping_historic.items():
        if k in historic_df.columns:
            restricted_historic_mapping[k] = v
    if not restricted_historic_mapping or 'time' not in restricted_historic_mapping:
        return None
    historic_df = historic_df[list(restricted_historic_mapping.keys())].copy()
    historic_df.rename(columns=restricted_historic_mapping, inplace=True)
    historic_df.index = pd.to_datetime(historic_df['datetime'])
    historic_df.replace(-999, float('nan'), inplace=True)

    if 'pCO2_sw' in historic_df.columns and 'pCO2_air' in historic_df.columns:
        historic_df['dpCO2'] = historic_df['pCO2_sw'] - historic_df['pCO2_air']

    return historic_df


def get_climatologies(longlat_df, config):
    output = {}
    # get O2 climatology
    try:
        with OpenDAPO2Climatology(
            longlat_df
        ) as o:
            output['DOXY'] = o.run()
    except Exception as e:
        output['DOXY'] = None
    
    # get CHL climatology
    if config is None:
        output['CHL (night time)'] = None
        return output
    try:
        with ChlCache(
            longlat_df, config
        ) as o:
            o.run()
            output['CHL (night time)'] = o.ts
    except Exception as e:
        print(f"Couldn't load CHL climatology because of {e}.")
        output['CHL (night time)'] = None
    return output


def get_temp_coeff_corr(model_path):
    if not model_path.is_file():
        return []
    
    with open(model_path, mode='rb') as f:
        [regr_models, kmeans_model] = pickle.load(f)

        statements = []
        for cluster_id in range(kmeans_model.n_clusters):

            slope = regr_models[cluster_id].params['temperature']
            intercept = regr_models[cluster_id].params['Intercept']
            rsquared = regr_models[cluster_id].rsquared

            statement = f"{slope:.6f} * Licor_Temp + {intercept:.4f}, R² = {rsquared:.4f}"
            statements.append(statement)
    
    return statements


def mbl_correction(merge_file_path):
    if not merge_file_path.is_file():
        return None
    
    with netCDF4.Dataset(merge_file_path) as nc:
        try:
            mbl_correction = float(nc.mbl_correction)
        except AttributeError:
            return None
    
    return mbl_correction


def compare_xco2_with_mbl(xco2, latitude, mbl):
    good_xco2_indicies = ~pd.isna(xco2)
    xco2 = xco2[good_xco2_indicies]
    latitude = latitude[good_xco2_indicies]
    
    mbl_time = mbl.da.coords['time'].values
    mbl_lats = mbl.da.coords['latitude'].values
    dp_restricted_index = (mbl_time > min(xco2.index) - np.timedelta64(1, 'D')) & (mbl_time < max(xco2.index) + np.timedelta64(1, 'D'))
    dp_restricted_mbl_time = mbl_time[dp_restricted_index]
    
    t_delta = np.timedelta64(4, 'D')
    mbl_dt = []
    mbl_xco2 = []
    difference = []
    for dt in dp_restricted_mbl_time:
        indicies = (xco2.index > dt - t_delta) & (xco2.index < dt + t_delta)
        if sum(indicies) > 0:
            avg_xco2 = np.nanmean(xco2[indicies])
            avg_lat = np.nanmean(latitude[indicies])
            da_mbl_t = mbl.da.loc[dt, :]
            matched_lat = align_arrays.find_closest(mbl_lats, avg_lat) 
            mbl_xco2_t_l = da_mbl_t.loc[matched_lat]
            mbl_dt.append(dt)
            mbl_xco2.append(mbl_xco2_t_l)
            difference.append(avg_xco2 - mbl_xco2_t_l)

    return pd.Series(data=mbl_xco2, index=mbl_dt), pd.Series(data=difference, index=mbl_dt)
        

def round_percent(percent):
    """Depending on the value of percent, return a rounded version."""
    if percent < 1:
        return round(percent, 3)
    elif percent < 10:
        return round(percent, 2)
    else:
        return round(percent, 1)

    
def flag_statistics(df_qf):
    output = []
    num_data = df_qf.shape[0]
    flags = [2, 3, 4, 5]
    for col in df_qf.columns:
        temp = [re.sub(' QF', '', col)]
        param_statistics = []
        if 'chl' not in col.lower():
            for f in flags:
                statistic = sum((df_qf[col] == f))
                statistic_percent = round_percent(statistic / num_data * 100)
                param_statistics.append([statistic, statistic_percent])
        else:  # handle CHL, which has most values as flag 5, because we don't report daytime CHL
            temp_stats = []
            for f in flags[:-1]:
                temp_stats.append(sum((df_qf[col] == f)))
            # so as not to skew the statistics, get the possible number of data without including flag 5's.
            temp_sum = sum(temp_stats)  
            for stat in temp_stats:
                statistic_percent = round_percent(stat / temp_sum * 100) if temp_sum > 0 else 0
                param_statistics.append([stat, statistic_percent])
            param_statistics.append(['N/A', 'N/A'])
                
        if param_statistics[0][0] + param_statistics[1][0] == 0:
            temp += ['Failed'] * len(flags)
        else:
            statistic_text = [str(s) + f' ({s_p}%)' if type(s) == int else s for s, s_p in param_statistics]
            temp += statistic_text
        output.append(temp)
    return output


class DirectoryStructureException(Exception):
    def __init__(self, message):
        super().__init__(message)