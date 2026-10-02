"""
Check span2_coefficient for negative values
"""
# standard library imports
import os

# 3rd party library imports
from IPython.display import display, HTML
import netCDF4
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
import xarray as xr

# local imports
from . import core
from xco2qc.core.vardefs import data_dict as vardefs
from xco2qc.browse import qt_browse


class FixSpan2Coefficient(core.MapCO2core):
    """
    Updates the span2 coefficient variable if so directed.

    Attributes
    ----------
    ncfile : str or path
        Path to cycle header netCDF file
    span2 : floating point scalar or None
        If not None, then update span2_coefficient to this value.
    """
    def __init__(self, ncfile, span2=None, span_correction=False):
        self.ncfile = ncfile
        self.span2 = span2
        self.span_correction = span_correction

    def run(self):

        if self.span2 is not None:
            with netCDF4.Dataset(self.ncfile, mode='r+') as nc:
                nc['span2_coefficient'][:] = self.span2

        if self.span_correction:
            self._span_correction()
        
        return None
    
    def _span_correction(self):
        with SpanRecalculation(self.ncfile) as gui:
            gui.run()


class CheckSpan2Coefficient(core.MapCO2core):
    """
    Checks the span2 coefficient variable, is it all zero?  That may mean that
    it needs to be changed.

    Attributes
    ----------
    ncfile : str or path
        Path to cycle header netCDF file
    zero_detected : bool
        At least one zero value was detected.
    different_values_detected : bool
        Not all the span2 coefficients were the same.
    """
    def __init__(self, ncfile):
        super().__init__()

        self.ncfile = ncfile
        self.zeros_detected = False
        self.different_values_detected = False

    def run(self):
        if not self.ncfile.is_file():
            # either there was an error processing, which should throw its own error before this point, or a netCDF was used, in which case the CYCLE_HEADER_NCFILE does not exist
            # no reason to notify user, this will only cause confusion.
            return
        
        with xr.open_dataset(self.ncfile) as ds:

            span2 = ds['span2_coefficient']

        # Was it even defined?  If all NaN, then it's not zero or different.
        if np.isnan(span2).sum() == len(span2):
            return

        # Are any values zero?
        num_zero_values = (span2.values == 0).sum()
        if num_zero_values > 0:
            self.zeros_detected = True
            msg = (
                '<h1>'
                f'{num_zero_values} zero span2 coefficients detected out of '
                f'{len(span2)} total values.  Consider specifying a '
                'replacement value in the data reduction code block.'
                '</h1>'
            )
            display(HTML(msg))

        # Are any values different?
        num_different = len(np.unique(span2))
        if num_different > 1:
            self.different_values_detected = True
            msg = (
                '<h1>'
                f'There were {num_different} different span2 coefficients out '
                f'of {len(span2)} total values.  Consider specifying a '
                'replacement value in the data reduction code block.'
                '</h1>'
            )
            display(HTML(msg))


class SpanRecalculation(core.MapCO2core):
    """
    Recalculates the span coefficients based on post-hoc test data and SPOFF licor temperature.
    
    Attributes
    ----------
    ncfile : str or path
        Path to reduced cycle header netCDF file
    temperature_column : str
        name of temperature column in post-hoc data.
    span_coeff_column : str
        name of span coefficient column in post-hoc data.
    """
    
    def __init__(self, ncfile, temperature_column="celltemp", span_coeff_column="co2kspan"):
        self.ncfile = ncfile
        self.spoff_ncfile = self.ncfile.parents[0] / core.licor.SPOFF_NCFILE
        self.TEMPERATURE_COLUMN = temperature_column
        self.SPAN_COEFF_COLUMN = span_coeff_column
    
    def run(self):
        post_hoc_path = self._load_post_hoc_data(self.ncfile.parents[0].parents[0])
        self._correct_span_coefficients(post_hoc_path)
    
    def _correct_span_coefficients(self, post_hoc_path):
        """
        Corrects span coefficients in reduced cycle header.
        
        :param file_path: (str or path) where to load post-hoc csv data.
        """
        
        post_hoc_temp, post_hoc_span_coeff = self._load_post_hoc_temp_and_span(post_hoc_path)
        
        with xr.open_dataset(self.spoff_ncfile) as ds:
            spoff_licor_temp = ds['temperature'].to_numpy().reshape(-1, 1)
        
        with xr.open_dataset(self.ncfile) as ds:
            uncorrected_span_coeff = ds['span_coefficient'].to_numpy()
        
        corrected_span_coeff = self._corrected_span_coefficients(post_hoc_temp,
                                                                 post_hoc_span_coeff,
                                                                 spoff_licor_temp)
        
        if corrected_span_coeff is not None:
            with netCDF4.Dataset(self.ncfile, mode='r+') as nc:
                # save original span coeff data
                varname = 'uncorrected_span_coefficient'
                metadata = vardefs['cycle_header']['span_coefficient']
                ncvar = nc.createVariable(
                    varname,
                    metadata['datatype'],
                    dimensions=('time',),
                    fill_value=metadata['fill_value']
                )
                ncvar[:] = uncorrected_span_coeff
                
                # overwrite span_coefficient with corrected span coefficient data.
                nc['span_coefficient'][:] = corrected_span_coeff
        
    def _load_post_hoc_data(self, home_dir):
        """
        Requests filepath of post-hoc oven test data from user.
        
        :param home_dir: (str or path) where to initialize file browser search.
        
        :output: (path) location of post-hoc csv file.
        """
        
        file_path = qt_browse(home_dir, text='Select the post-Hoc csv file to correct the span coefficient.')
        return file_path
        
    def _load_post_hoc_temp_and_span(self, file_path):
        """
        Loads the data from a post-Hoc lab experiment and returns the appropriate variables in numpy array format.
        
        :param file_path: (str or path) where to load post-hoc csv data.
        
        :output: (np.array) temperature array and licor span coefficent array.
        """
        
        if os.path.isfile(file_path) and file_path.name.endswith(".csv"):
            df = pd.read_csv(file_path)
        
            if self.TEMPERATURE_COLUMN in df.columns and self.SPAN_COEFF_COLUMN in df.columns:
                temp = df[self.TEMPERATURE_COLUMN].to_numpy().reshape(-1, 1)
                span = df[self.SPAN_COEFF_COLUMN].to_numpy().reshape(-1, 1)
                return temp, span
        
        return None, None
    
    def _corrected_span_coefficients(self, post_hoc_temp, post_hoc_span_coeff, licor_temperature):
        """
        Computes corrected span coefficients based on post-Hoc lab tests and in-situ licor temperature. This function is run
        when the instrument/system did not have enough span gas flow and did not calibrate properly.
        
        :param post_hoc_temp: (str) temperatures from post-hoc test.
        :param post_hoc_span_coeff: (str) span coefficients from post-hoc test.
        :param licor_temperature: (np.array) in-situ licor temperature during the span pump off cycle.
        
        :output: (np.array) corrected span coefficients
        """
        
        # locate nan values in licor_temperature, replace them for LR, then reset LR output to nan for those values.
        nan_index = np.isnan(licor_temperature)
        licor_temperature[nan_index] = -999.  # unrealistic value
        
        if post_hoc_temp is not None and post_hoc_span_coeff is not None:
            lr_model = LinearRegression()
            lr_model.fit(post_hoc_temp, post_hoc_span_coeff)
            print("Slope: ", lr_model.coef_[0][0], " ", "Intercept: ", lr_model.intercept_[0], "R**2: ", lr_model.score(post_hoc_temp, post_hoc_span_coeff))
            
            output = np.round(lr_model.predict(licor_temperature.reshape(-1, 1)), 6)
            # replace values that had nan temperatures with nans
            output[nan_index] = np.nan
            
            return output
        
        return None