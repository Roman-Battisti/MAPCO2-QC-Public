# standard libraries
import os
import pathlib
import re

# 3rd party libraries
import numpy as np
import pandas as pd
import xarray as xr
import yaml

# Local imports
from .remote_climatology import OpenDAPO2Climatology, ChlCache
from .chl_climatology import CHLClimatology
from .o2_climatology import O2Climatology


curr_path = os.path.dirname(os.path.abspath(__file__))
mapping_path = os.path.join(curr_path, 'core', 'param_mapping.yml')
with open(mapping_path) as f:
    param_mapping = yaml.load(f, yaml.SafeLoader)
nc_file_mapping = param_mapping.pop('NC_file_mapping', {})

primary_params = ['xCO2_air', 'xCO2_sw', 'temperature', 'SSS', 'pH_sw', 'dissolved_oxygen', 'chl_nighttime', 'ntu']
historic_param_mapping = {
                          'dissolved_oxygen': 'doxy'
                         }



class netCDFaccess:
    """
        Container for general access to the various data access objects.
        Handles inputs of the general form 'source_name data_column_name',
        where the source_name references the appropriate data access object
        and the data_column_name referencing a column within that source object.
        If source_name and/or data_column_name are incorrect, the input string
        will be returned.
        
        netCDFaccess is set up for the Quality Control (QC) jupyter notebook
        developed for the Moored Carbon Group at the Pacific Marine Environmental
        Laboratory (PMEL).
        
        :param merge_path: (Path or str) file path to the merge netCDF of the current QC process.
        :param trim_path: (Path or str) path to folder containing trimmed netCDF files.
        :param site_id: (str) cannonical name of site/station whose data is currently being QC'ed.
        :param nc_file_mapping: (dict) mapping of simplified source names to thier file names in the trimmed directory.
    """
    def __init__(self, merge_path, trim_path, site_id, config, nc_file_mapping=nc_file_mapping):
        self.merge_path = merge_path
        self.trim_path = trim_path
        self.site_id = site_id.lower()
        self.config = config
        self._setup_data()
        
    def _setup_data(self):
        """Builds the data dictionary containing the various data access objects."""
        self.data = load_nc_from_folder(self.trim_path)
        self.data['merge'] = MergeColumnSelector(self.merge_path)
        self._add_climatologies()
    
    def _add_climatologies(self):
        """Adds climatology objects to data dictionary"""
        merge_time = pd.to_datetime(self.load_columns('merge', ['time']))
        latlong_df = pd.DataFrame(self.load_columns('merge', ['latitude', 'longitude']), columns=['latitude', 'longitude'])
        latlong_df.index = merge_time
        latlong_df = latlong_df.replace(-999, float('nan'))
        latlong_df = latlong_df.loc[(latlong_df['longitude'] >= -180) & (latlong_df['latitude'] >= -90), :]
        latlong_df = latlong_df.astype(np.float32)
        
        self.data.update(add_climatologies(latlong_df, self.config, self.available_merge_columns(), merge_time, self.site_id))
        pass
    
    def get_data(self, param_name: str):
        """
            Standard interface for getting data.
            
            :param param_name: (str) general format of 'source_name data_column_name'.
                               See class description for details. If only data_column_name
                               provided, the source_name will be automatically set to 'merge'.
                               Processing requires source_name and data_column_name to not have
                               spaces in their names.
            
            :output: (1D np array or str) numpy array returned if source and data column exist,
                     param_name returned otherwise.
        """
        
        param = param_name.lower().split()
        if len(param) == 2 and param[0] in self.data:
            return self.data[param[0]].load_columns(param[1:])
        elif len(param) == 1:  # if source_name not provided, assume 'merge'
            return self.data['merge'].load_columns(param)
        
        # QC process requires some basic derived variables that require addition/subtraction
        # the following elif statements are to handle those basic requests.
        elif '-' in param:
            index = param.index('-')
            try:
                return self.get_data(' '.join(param[:index])) - self.get_data(' '.join(param[index+1:]))
            except np.core._exceptions.UFuncTypeError:
                return param_name
            except TypeError:
                return param_name
        elif '+' in param:
            index = param.index('+')
            try:
                return self.get_data(' '.join(param[:index])) + self.get_data(' '.join(param[index+1:]))
            except np.core._exceptions.UFuncTypeError:
                return param_name
            except TypeError:
                return param_name
        else:
            return param_name
    
    def get_full_timeseries(self, param_list: list):
        """
            Many of the quality control parameters have historic data
            which can be used to help inform on the quality of the
            current data. This method outputs the concatenated historic
            and current data rather than have the logic in other places.
            Can take a list of parameter names. 
            
            return logic:
            1) If any parameter does not exist in the current QC parameter data pool,
               param_list will be returned. 
            2) If no historic data exists, current data will be returned so long as
               (1) is met.
            3) When historic data does exist, if any of the parameters in the list do not
               have historic data, param_list will be return.
            Otherwise a list of np.array with concatenated [historic, current] data will be returned.
            
            :param_list: (list) param names.
            
            :output: (list of np arrays or list) array entries of list are concatenated
                     [historic, current] data pairs. If any parameters don't exist in
                     either historic or current data access objects, param_list is returned.
        """
        
        param_data = []
        for param_name in param_list:
            p_d = self.get_data(param_name)
            if len(p_d) <= 1:
                return param_list
            param_data.append(p_d)
        
        if 'historical' in self.data:
            sep_params = [param_name.lower().split() for param_name in param_list]
            hist_params = [param.lower() for param in self.available_data_in_source('historical')]
            hist_data = []
            for source, p in sep_params:
                p_historic = historic_param_mapping.get(p, p)
                if p_historic not in hist_params:
                    return param_data
                hist_data.append(self.get_data(' '.join(['historical', p_historic])))
            param_data = [np.append(p_h, p_d) for p_h, p_d in zip(hist_data, param_data)]
        return param_data
    
    def load_columns(self, nc_file: str, param_list: list):
        """
            Load numerous columns from a single source.
            
            :param nc_file: (str) source data object.
            :param param_list: (list) param names. Will return param_list
                               if any param name not in data object columns.
        """
        return self.data[nc_file].load_columns(param_list)
    
    def available_merge_columns(self):
        return self.data['merge'].available_columns()
    
    def available_data_sources(self):
        return list(self.data.keys())
        
    def available_data_in_source(self, source: str):
        source = source.lower()
        if type(source) != str or source not in self.data:
            return [None]
        else:
            return self.data[source].available_columns()
        
    def available_netcdfs(self):
        available_ncs = list(self.data.keys())
        available_ncs.remove('merge')
        return available_ncs
    
    def available_netcdf_data(self, nc_file: str):
        return self.trim_data.available_columns(nc_file)


# netCDFaccess helper functions
nc_name_to_connonical_mapping = {'cycle_header': 'header',
                                 'licor.air-pump-off': 'apoff',
                                 'licor.air-pump-on': 'apon',
                                 'licor.equil-pump-off': 'epoff',
                                 'licor.equil-pump-on': 'epon',
                                 'licor.span-post-cal': 'spcal',
                                 'licor.span-pump-off': 'spoff',
                                 'licor.span-pump-on': 'spon',
                                 'licor.zero-post-cal': 'zpcal',
                                 'licor.zero-pump-off': 'zpoff',
                                 'licor.zero-pump-on': 'zpon',
                                 'MetSSTC': 'met'}


def load_nc_from_folder(folder_path):
    """
        Loads each netCDF in folder_path to the appropriate ColumnSelector object.
        
        :param folder_path: (Path or str) path to folder holding netCDFs.
        
        :output: (dict) Keys are file name if the name doesn't exist in the
                 nc_name_to_connonical_mapping. Values are ColumnSelector
                 objects
    """
    
    available_netcdfs = [f.lower() for f in os.listdir(folder_path)
                         if os.path.isfile(os.path.join(folder_path, f))
                         and f.endswith('.nc')]
    nc_dict = {}
    for nc in available_netcdfs:
        nc_name = os.path.basename(nc).split('.nc')[0]
        nc_connonical = nc_name_to_connonical_mapping.get(nc_name, nc_name)
        if nc_connonical != 'historical':
            nc_dict[nc_connonical] = StandardColumnSelector(os.path.join(folder_path, nc))
        else:
            nc_dict[nc_connonical] = HistoricalColumnSelector(os.path.join(folder_path, nc))
    
    return nc_dict


def add_climatologies(latlong_df, config, merge_cols, merge_time, site_id):
    """
    Import oxygen and chlorophyll climatologies either remotely or localy (try remote first). Local climatology is
    built in-house (PMEL) and is a fail safe if climatologies are not available.
    
    :param latlong_df: :param latlong_df: (pandas dataframe) dataframe containing latitude and longitude data
    :param config: (str or path) path to config file containing remote chl climatology access information.
    :param merge_cols: (list) available parameters. Checks whether oxygen and chlorophyll exist in the data set.
                       If not, no need to get associated climatology.
    :param merge_time: times to match if using local climatology.
    :param site_id: site to search for in local climatology.
    
    :output: (dict) contains EstimatedColumnSelector of climatology data.
    """
    
    output = {}
    
    clima_time = pd.to_datetime(merge_time)
    
    if 'dissolved_oxygen' in merge_cols:
        o2_name = 'o2_climatology'
        output[o2_name] = get_o2_climatology(latlong_df, clima_time, site_id, o2_name)
    if 'chl' in merge_cols:
        chl_name = 'chl_climatology'
        output[chl_name] = get_chl_climatology(latlong_df, config, clima_time, site_id, chl_name)
    
    return output


def get_o2_climatology(latlong_df, clima_time, site_id, param_name):
    """
    Extracts remote climatology, if available. If not, will try local data, finally reporting no data (nans)
    
    :param latlong_df: (pandas dataframe) dataframe containing latitude and longitude data
    :param merge_time: times to match if using local climatology.
    :param site_id: site to search for in local climatology.
    :param name: parameter name to use when building the EstimatedColumnSelector
    
    :output: EstimatedColumnSelector containing relevant climatological information.
    """
    
    # try remote climatology first, then local, then default nan
    try:
        with OpenDAPO2Climatology(
            latlong_df
        ) as o:
            o2_output = o.run()
            # new merge time is o2_output index
            merge_time = o2_output.index.to_series()
            o2_series = o2_output
    except Exception as e:
        merge_time = clima_time
        o2_series = get_local_climatologies(O2Climatology, clima_time, site_id, 'O2')
        
    return EstimatedColumnSelector(merge_time, o2_series, param_name)


def get_chl_climatology(latlong_df, config, clima_time, site_id, param_name):
    """
    Extracts remote climatology, if available. If not, will try local data, finally reporting no data (nans)
    
    :param latlong_df: (pandas dataframe) dataframe containing latitude and longitude data
    :param config: (str or path) path to config file containing remote chl climatology access information.
    :param merge_time: times to match if using local climatology.
    :param site_id: site to search for in local climatology.
    :param name: parameter name to use when building the EstimatedColumnSelector
    
    :output: EstimatedColumnSelector containing relevant climatological information.
    """
    
    # try remote climatology first, then local, then default nan
    try:
        if config is None:
            raise NoConfigFile
        with ChlCache(
            latlong_df, config
        ) as o:
            o.run()
            chl_output = o.ts
            # new merge time is chl_output index
            merge_time = chl_output.index.to_series()
            chl_series = chl_output
    except Exception as e:
        merge_time = clima_time
        chl_series = get_local_climatologies(CHLClimatology, clima_time, site_id, 'Chl')

    return EstimatedColumnSelector(merge_time, chl_series, param_name)


def get_local_climatologies(climatology, merge_time, site_id, param_name):
    """
        Creates a climatological series from local data. If none exist for specified site, returns NaN
        
        :param climatology: (function) function used to get climatology data.
        :param merge_time: (np array) datetimes used to align climatological times to QC data times.
        :param site_id: (str) cannonical name of site. Current climatologies are based on site names.
        :param param_name: (str) name of climatological data to extract from climatology function output.
        
        :output: (pd.Series) climatology data or NaNs if no data present. 
    """
    
    try:
        with climatology(site_id) as clima:
            clima_df = clima.interpolate(merge_time)
            clima_series = clima_df[param_name]
    except KeyError:
        # no climatology data available
        clima_series = pd.Series(np.full(merge_time.shape), np.nan)
    
    return clima_series


# data access classes
class ColumnSelector:
    """
        Base class for the data access classes. Data is stored
        in pandas DataFrames.
        
        :param nc_path: (Path or str) file path to netCDF file.
    """
    
    def __init__(self, nc_path):
        self.nc_path = nc_path
        self.df = self._load_data()
    
    def _load_data(self):
        """method to load data. Depends on the type of netCDF file being loaded."""
        pass
    
    def load_columns(self, param_list: list):
        """
            Standard method to load data.
            
            :param param_list: (list) column names to be loaded.
            
            :output: (np array or list) if all column names exist
                     in the DataFrame, data is returned. Otherwise
                     param_list is returned.
        """
        try:
            df = self.df[param_list]
        except KeyError:
            return param_list
        np_df = df.to_numpy()
        if len(param_list) == 1:
            return np_df.reshape([-1,])
        return np_df
    
    def available_columns(self):
        """list of column names available in the DataFrame."""
        return list(self.df.columns)
    

class HistoricalColumnSelector(ColumnSelector):
    """Handles historical netCDF. 'time' is not the index for this netCDF."""
    def __init__(self, nc_path):
        super().__init__(nc_path)
        
    def _load_data(self):
        df = load_nc_to_dataframe(self.nc_path)
        if 'time' in df.columns:
            df['time'] = df['time'].dt.strftime('%Y-%m-%d %H:%M')
        else:
            df['time'] = df.index.strftime('%Y-%m-%d %H:%M')
        return df
    

class StandardColumnSelector(ColumnSelector):
    """Handles most netCDF. 'time' is the index for this netCDF."""
    def __init__(self, nc_path):
        super().__init__(nc_path)
        
    def _load_data(self):
        df = load_nc_to_dataframe(self.nc_path)
        df['time'] = df.index.strftime('%Y-%m-%d %H:%M')
        return df


class EstimatedColumnSelector(ColumnSelector):
    """
        For estimated values like climatologies. Requires extra information for processing.
    
        :param merge_time: (np array) Climatologies are pulled from existing, external data.
                           merge_time is used to align the climatological datetimes to the QC data datetimes.
        :param climatology_data: (pd DataFrame) contains datetime and parameter information from
                                 external climatologies.
        :param param_name: (str) name of the climatological data to be used as the column name of the data.
    """
    def __init__(self, merge_time, climatology_data, param_name):
        self.merge_time = merge_time
        self.climatology_data = climatology_data
        self.param_name = param_name
        super().__init__(nc_path=None)
        
    def _load_data(self):
        """loading data requires the climatological times to be aligned with the QC data time."""
        df = self.climatology_data
        df = df.to_frame(self.param_name)
        aligned_time_index = df.index.get_indexer(self.merge_time, method='nearest')  # [df.index.get_loc(i, method='nearest') for i in self.merge_time]
        df = df.iloc[aligned_time_index, :]
        df['time'] = self.merge_time
        df['climatology_time'] = df.index.strftime('%Y-%m-%d %H:%M')
        df.reset_index(drop=True, inplace=True)
        df.columns = df.columns.str.lower()
        self.climatology_data = None
        self.merge_time = None
        return df

class MergeColumnSelector(ColumnSelector):
    """
        Specifically handles merge netCDF. There are special bit flag masks
        which are associated with the automatic quality control flags.
        These bit flags need to be converted to columns in the dataframe.
        The conversion methods are inherited from ________ in the ________ module.
    """
    def __init__(self, nc_path):
        super().__init__(nc_path)
        
    def _load_data(self):
        """loading data requires bit flag masks to be converted to columns."""
        df, ds = load_nc_to_dataframe(self.nc_path, return_ds=True)
        df = df.reset_index()
        if 'time' in df.columns:
            df['time'] = df['time'].dt.strftime('%Y-%m-%d %H:%M')
        self._add_quality_flags_and_meanings(df, ds)
        ds.close()
        for met in ['sst', 'sss']:
            if met not in df.columns:
                df[met] = float('nan')
                df[met + '_qc'] = 6
                df[met + '_qc_reason'] = 'missing'
        return df
    
    def _add_quality_flags_and_meanings(self, df, ds):
        """
        Add quality flags and reason for quality flags of the primary variables
        to the dataframe
        """
        for p in primary_params:
            if p not in ds:
                continue
            ancillary_attr = ds[p].ancillary_variables
            try:
                bitmask_qc_var, socat_qc_var = ancillary_attr.split()
            except ValueError:
                # ValueError: not enough values to unpack (expected 2, got 1)
                bitmask_qc_var = ancillary_attr
                socat_qc_var = None
            flag_masks = ds[bitmask_qc_var].flag_masks
            flag_meanings = ds[bitmask_qc_var].flag_meanings.split()
            
            if socat_qc_var is not None:
                df[socat_qc_var.lower()] = df[socat_qc_var.lower()].astype(np.uint8)
            df[bitmask_qc_var.lower()] = df[bitmask_qc_var.lower()].astype(np.uint32)
            
            self._create_qc_reasons(df, bitmask_qc_var, flag_masks, flag_meanings)
    
    def _create_qc_reasons(self, df, bitmask_qc_var, flag_masks, flag_meanings):
        """
        change the bitflag qc variable to a comma-delimited text of reasons
        for the bit flags
        """
        col_name = bitmask_qc_var.lower() + '_reason'
        d = {val: meaning for val, meaning in zip(flag_masks, flag_meanings)}
        
        df[col_name] = ''
        for mask_value, reason in d.items():
            x = np.bitwise_and(df[bitmask_qc_var.lower()], mask_value)
            reasons = np.where(x, ',' + reason, '')
            df[col_name] = df[col_name].str.cat(reasons)
        # get rid of the leading comma
        df[col_name] = df[col_name].str.strip(',')


# data class helper functions
def load_nc_to_dataframe(nc_file_path, return_ds=False):
    """
        Loads a netCDF into a pandas DataFrame using xarray.
        
        :param nc_file_path: (Path or str) file path to netCDF file.
        :param return_ds: (bool) whether to also return the xarray object
                          (for additional processing).
        
        :output: (pd DataFrame, maybe xarray data object) DataFrame always returned.
                 xarray data object returned upon request.
    """
    
    try:
        assert os.path.exists(nc_file_path) and os.path.splitext(nc_file_path)[-1] == ".nc"
    except AssertionError:
        breakpoint()
        pass
    
    with xr.open_dataset(nc_file_path) as ds:
        ds = ds.load()
    df = ds.to_dataframe()
    df.columns = df.columns.str.lower()
    
    if not return_ds:
        ds.close()
        return df
    else:
        return df, ds


class NoConfigFile(Exception):
    pass