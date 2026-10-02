"""
Generate SOCAT CSV and XML output from the netCDF file
"""
# standard library imports
import copy
import datetime as dt
import importlib.resources as ir
import pathlib
import pickle
import warnings

# 3rd party library
import lxml.etree as ET
import netCDF4
import numpy as np
import pandas as pd
import xarray as xr
import yaml

# local imports
from xco2qc import core
from xco2qc.core.socat import FUGACITY_AIR, FUGACITY_SW, DFCO2


class SocatWriter(core.MapCO2core):
    """
    Attributes
    ----------
    merge_ncfile : path or str
        the netCDF file merged together out of disparate sources, will be the
        final authoritative product
    xmlfile : path
        path to output XML file for submission to SOCAT
    csvfile : path
        path to output CSV file for submission to SOCAT
    site_ids : dictionary
        associates mooring sites with additional metadata
    princ_inv : list
        Details of the PIs.
    models_file : path or None
        path to binary file where regression and cluster model information is
        stored, but only if the models_file is not None
    vessel_id : str
        Name of the cruise vessel
    qflog : str or path
        QF log CSV file
    """
    def __init__(
        self, *,
        ncfile=None, xmlfile=None, csvfile=None, verbosity=None,
        initial_span_cal=None, licor_pressure_correction=None,
        models_file=None,
        pi_list=None,
        qcer=None,
        vessel_id=None,
        qflog=None,
        **kwargs
    ):
        self.merge_ncfile = pathlib.Path(ncfile)
        super().__init__(
            src_dir=self.merge_ncfile.parents[0],
            verbosity=verbosity, logger_name='socat'
        )

        if pi_list is not None:
            self.princ_inv = pi_list
        else:
            # Load the default from our configuration file.
            self.princ_inv = self.config['metadata']['pi_list']

        self.xmlfile = pathlib.Path(xmlfile)
        self.csvfile = pathlib.Path(csvfile)
        self.savefilename = 'socat'  # default
        self.models_file = models_file
        self.qcer = qcer
        self.vessel_id = vessel_id

        with ir.as_file(ir.files(core.data).joinpath('sites.yml')) as path:
            with path.open() as f:
                self.site_ids = yaml.safe_load(f)

        if initial_span_cal is None:
            self.initial_span_cal = self.config['QC']['initial_span_cal']
        else:
            self.initial_span_cal = initial_span_cal

        if licor_pressure_correction is None:
            self.licor_pressure_correction = self.config['adjustments']['licor_pressure_correction']  # noqa : E501
        else:
            self.licor_pressure_correction = licor_pressure_correction

        if qflog is not None:
            self.qflog = pathlib.Path(qflog)
        else:
            self.qflog = None

    def run(self):

        self.logger.info('Generating SOCAT products...')

        # Now that the netCDF writing is done, reopen the merge netCDF file
        # in read-only mode.
        with xr.open_dataset(self.merge_ncfile) as self.ds:
            self._get_mooring_metadata()
            self.write_socat_csv()
            self.write_socat_xml()

        self.write_qf_log()

        self.logger.info('Finished generating SOCAT products...')

        # Display the final product files and their sizes.
        for file in sorted(
            [self.merge_ncfile, self.xmlfile, self.csvfile],
            key=lambda path: path.name
        ):
            kb_size = file.stat().st_size / 1024
            self.logger.info(f"{file.name:25}  {kb_size:8.2f} KB")

    def write_qf_log(self):
        """
        Create a CSV file with the reasons behind any 3 or 4 (questionable or
        bad).
        """
        df_bitmask = self._construct_bitmask_qf_log()
        qflog_filename = '_'.join([self.savefilename, 'QFlog']) + '.csv'
        qflog_savepath = self.csvfile / qflog_filename
        
        try:

            # merge with the existing QF log?
            df_reason = pd.read_csv(
                self.qflog, parse_dates=['Date/Time'], index_col=None
            )

            # reset the indexes so we can do a join
            df_bitmask = df_bitmask.set_index(['Date/Time', 'Parameter'])
            df_reason = df_reason.set_index(['Date/Time', 'Parameter'])

            df = df_bitmask.join(df_reason, how='left')
            df = df.reset_index()

            # replace NaNs with '' to make it easier to merge the Reason column
            # into the QC note
            df.loc[df['Reason'].isnull(), 'Reason'] = ''
            df['QC Note'] = df[['QC Note', 'Reason']].agg('; '.join, axis=1)

            # clean up any trailing commas
            df['QC Note'] = df['QC Note'].str.rstrip('; ')

            df = df.drop('Reason', axis='columns')

        except (FileNotFoundError, ValueError):

            # there was no existing QF log (it's None), so just write out
            # what we constructed from the bitmask
            df = df_bitmask

        finally:
            if df is not None:  # this can happen if there are no data with flags 3 or 4
                df_no_flag_2s = df.loc[(df['QF'] != 2) & (df['QC Note'] != 'out of range,daytime'), :]
                df_no_flag_2s.to_csv(qflog_savepath, sep=',', index=False)

    def _construct_bitmask_qf_log(self):

        data_vars = []

        with xr.open_dataset(self.merge_ncfile) as ds:
            df = ds.to_dataframe()

            # we need to have a mapping from the socat qc variable to the
            # associated bitmask qc var
            d = {}
            d2 = {}
            for var in ds:
                if (
                    hasattr(ds[var], 'ancillary_variables')
                    and var != 'chl'
                ):
                    anc_vars = getattr(ds[var], 'ancillary_variables').split()

                    # a bitmask quality variable has a 'flag_masks' attribute
                    # a socat quality variable has a 'flag_values' attribute
                    bitmask_qc_var = None
                    socat_qc_var = None

                    for anc_var in anc_vars:
                        if hasattr(ds[anc_var], 'flag_masks'):
                            bitmask_qc_var = anc_var
                        elif hasattr(ds[anc_var], 'flag_values'):
                            socat_qc_var = anc_var
                        # it's possible there might be something else in there
                        # so ignore it

                    if bitmask_qc_var and socat_qc_var:
                        d[socat_qc_var] = bitmask_qc_var
                        data_vars.append(var)
                        d2[socat_qc_var] = {}
                        d2[socat_qc_var]['dataname'] = var
                        d2[socat_qc_var]['bitmask'] = bitmask_qc_var

            # restrict the dataframe to just the socat qc variables
            df_socat = df[d.keys()].astype(np.uint32)
            df_bitmask = df[d.values()].astype(np.uint32)
            df_data = df[data_vars]

            # restrict the dataframe to just those measurements where socat
            # quality was 3 or 4.
            idx = ((df_socat >= 3) & (df_socat <= 4)).any(axis='columns')
            if idx.sum() == 0:
                qflog_filename = '_'.join([self.savefilename, 'QFlog']) + '.csv'
                qflog_savepath = self.csvfile / qflog_filename
                # Write an empty QF log and be done with it.
                with qflog_savepath.open(mode='wt') as f:
                    f.write('Date/Time,Parameter,Value,QF,QC Note')
                return None

            df_data = df_data.loc[idx, :]
            df_bitmask = df_bitmask.loc[idx, :]
            df_socat = df_socat.loc[idx, :]

            # convert the bitmask columns into text values
            data = {
                k: ['' for _ in df_bitmask.index] for k in df_bitmask.keys()
            }
            df_reason = pd.DataFrame(index=df_bitmask.index, data=data)

            # construct text reasons for the QC values
            for varname in df_bitmask.columns:
                idxmap = {
                    k: v for k, v in zip(
                        ds[varname].flag_masks,
                        ds[varname].flag_meanings.split()
                    )
                }
                for flag, flag_meaning in idxmap.items():
                    idx = df_bitmask[varname] & flag > 0
                    df_reason.loc[idx, varname] += f',{flag_meaning}'

                # remove the leading ','
                df_reason.loc[:, varname] = df_reason.loc[:, varname].str.strip(',')  # noqa : E501
                df_reason.loc[:, varname] = df_reason.loc[:, varname].str.replace('_', ' ')  # noqa : E501

        # ok create the output records
        rounding_dict = {
            'dissolved_oxygen_socat_qc': 2,
            'SSS_socat_qc': 3,
            'SST_socat_qc': 3,
            'xCO2_air_socat_qc': 1,
            'xCO2_sw_socat_qc': 1,
            'chl_nighttime_socat_qc': 3,
            'ntu_socat_qc': 3,
            'pH_sw_socat_qc': 4,
        }
        records = []
        for timestamp, row in df_socat.iterrows():
            for socat_var, socat_qc_value in row.items():
                if socat_qc_value not in (2, 3, 4):
                    continue
                record = {
                    'Date/Time': timestamp,
                    'Parameter': d2[socat_var]['dataname'],
                    'Value': np.round(df_data.loc[timestamp, d2[socat_var]['dataname']], rounding_dict.get(socat_var, 2)),
                    'QF': socat_qc_value,
                    'QC Note': df_reason.loc[timestamp, d2[socat_var]['bitmask']],  # noqa : E501
                }

                records.append(record)

        qflog_df = pd.DataFrame.from_records(records)
        return qflog_df

    def write_socat_xml(self):

        self.logger.info('Generating SOCAT XML file...')

        with ir.as_file(ir.files(core.data).joinpath('socat.xml')) as document_path:
            self.doc = ET.parse(str(document_path))

        self.update_principal_investigator_details()
        self.update_qc_operator_details()
        self.update_initial_submit_date()
        self.update_cruise_id()
        self.update_experiment_and_vessel_info()
        self.update_vessel_id()
        self.update_geospatial_bounds()
        self.update_temporal_bounds()
        self.update_co2_sensor_calibration()
        self.update_additional_information_element()
        self.update_citation()
        self.update_link_note()
        self.strip_out_spurious_variables()
        
        xmlfilename = self.savefilename + '.xml'
        self.doc.write(str(self.xmlfile / xmlfilename), pretty_print=True)

    def strip_out_spurious_variables(self):
        """
        The template XML file contains all variables that are possible, but not
        all variables will actually be present in the data.  Remove any that
        are not actually present.
        """
        with xr.open_dataset(self.merge_ncfile)as ds:
            # did we have dissolved oxygen?
            if 'dissolved_oxygen' not in ds:

                self.remove_variable_from_doc('DOXY')
                self.remove_variable_from_doc('DOXY QF')

                self.remove_sensor_from_doc('Max-250')
                self.remove_sensor_from_doc('SBE63')

            if 'chl' not in ds and 'ntu' not in ds:
                self.remove_variable_from_doc('CHL')
                self.remove_variable_from_doc('CHL QF')
                self.remove_variable_from_doc('NTU')
                self.remove_variable_from_doc('NTU QF')

            if 'pH_sw' not in ds:
                self.remove_variable_from_doc('pH SW')
                self.remove_variable_from_doc('pH QF')
                self.remove_sensor_from_doc('SAMI2 pH')
            else:
                if ds['pH_sw'].source == 'DURAFET':
                    self.remove_sensor_from_doc('SAMI2 pH')

    def remove_sensor_from_doc(self, model):
        """
        Remove a Sensor element from the XML document because the data
        for it must not be present.
        """

        path = (
            f"Method_Description/Other_Sensors/Sensor"
            f"/Model[text() = '{model}']"
        )
        elt = self.doc.getroot().xpath(path)[0]

        # we want to remove the parent element
        parent = elt.getparent()
        grandparent = parent.getparent()
        grandparent.remove(parent)

    def remove_variable_from_doc(self, varname):
        """
        Remove a Variable element from the XML document because the data
        for it must not be present.
        """

        path = f"Variables_Info/Variable/Variable_Name[text() = '{varname}']"
        elt = self.doc.getroot().xpath(path)[0]

        # we want to remove the parent element
        parent = elt.getparent()
        grandparent = parent.getparent()
        grandparent.remove(parent)

    def update_initial_submit_date(self):
        """
        Update the details about when we are making the initial submission
        (hint: it's always today).
        """
        path = 'Dataset_Info/Submission_Dates/Initial_Submission'
        elt = self.doc.xpath(path)[0]
        elt.text = dt.date.today().strftime('%m/%d/%Y')

    def update_vessel_id(self):
        """
        Update the details about the name of the cruise vessel.
        """
        if self.vessel_id is not None:
            path = 'Cruise_Info/Vessel/Vessel_ID'
            elt = self.doc.xpath(path)[0]
            elt.text = self.vessel_id

    def update_principal_investigator_details(self):
        """
        Update the details about the PIs.
        """
        orig_elt = self.doc.xpath('Investigator')[0]
        orig_elt.getparent().remove(orig_elt)

        for idx, pi in enumerate(self.princ_inv):
            pi_elt = copy.deepcopy(orig_elt)

            elt = pi_elt.xpath('Name')[0]
            if pi['title'] == '':
                elt.text = f"{pi['first_name']} {pi['last_name']}"
            else:
                elt.text = f"{pi['title']} {pi['first_name']} {pi['last_name']}"  # noqa : E501

            elt = pi_elt.xpath('Organization')[0]
            elt.text = pi['organization']

            elt = pi_elt.xpath('Address')[0]
            elt.text = pi['address']

            elt = pi_elt.xpath('Phone')[0]
            elt.text = pi['phone']

            elt = pi_elt.xpath('Email')[0]
            elt.text = pi['email']

            self.doc.getroot().insert(idx, pi_elt)

    def update_qc_operator_details(self):
        """
        Update the details about the person running the QC process
        """
        if self.qcer is None:
            return

        elt = self.doc.xpath('User/Name')[0]
        if self.qcer['title'] == '':
            elt.text = f"{self.qcer['last_name']}, {self.qcer['first_name']}"
        else:
            elt.text = (
                f"{self.qcer['title']} "
                f"{self.qcer['last_name']}, {self.qcer['first_name']}"
            )

        elt = self.doc.xpath('User/Organization')[0]
        elt.text = self.qcer['organization']

        elt = self.doc.xpath('User/Address')[0]
        elt.text = self.qcer['address']

        elt = self.doc.xpath('User/Phone')[0]
        elt.text = self.qcer['phone']

        elt = self.doc.xpath('User/Email')[0]
        elt.text = self.qcer['email']

    def write_socat_csv(self):
        """
        Write a CSV file that can be delivered to SOCAT.
        """

        self.logger.info('Generating SOCAT CSV file...')

        # First convert the xarray dataset to a dataframe
        df = self.ds.to_dataframe().reset_index()

        df[core.socat.MOORING] = self.mooring_name

        # Date and time
        df[core.socat.DATE] = df['time'].dt.strftime('%m/%d/%Y')
        df[core.socat.TIME] = df['time'].dt.strftime('%H:%M')

        # TODO:  explain
        df['o2_ratio'] = df['o2_ratio'] * 100

        # dpCO2 is just the difference between two columns
        if 'pCO2_sw' in df.columns and 'pCO2_air' in df.columns:
            df[core.socat.DPCO2] = df['pCO2_sw'] - df['pCO2_air']
        else:
            df[core.socat.DPCO2] = -999

        df = df.round({
            'atm_pressure': 1,
            'dissolved_oxygen': 2,
            'latitude': 3,
            'longitude': 3,
            'temperature': 1,
            'o2_ratio': 2,
            'pCO2_air': 2,
            'pCO2_sw': 2,
            'dpCO2': 2,
            'dfCO2': 2,
            'fCO2_air': 2,
            'fCO2_sw': 2,
            'SSS': 3,
            'SST': 3,
            'xCO2_air': 1,
            'xco2_air_wet': 1,
            'xco2_sw_wet': 1,
            'xCO2_sw': 1,
        })

        # Rename to SOCAT names.
        mapper = {
            'atm_pressure': core.socat.LICOR_PRESSURE,
            'chl_nighttime': core.socat.CHL,
            'chl_nighttime_socat_qc': core.socat.CHL_QC,
            'dissolved_oxygen': core.socat.DISSOLVED_OXYGEN,
            'dissolved_oxygen_socat_qc': core.socat.DISSOLVED_OXYGEN_QC,
            'fCO2_sw': core.socat.FUGACITY_SW,
            'fCO2_air': core.socat.FUGACITY_AIR,
            'longitude': core.socat.LONGITUDE,
            'latitude': core.socat.LATITUDE,
            'ntu': core.socat.NTU,
            'ntu_socat_qc': core.socat.NTU_QC,
            'xco2_air_wet': core.socat.XCO2_AIR_WET,
            'xco2_air_socat_qc': core.socat.XCO2_AIR_QC,
            'temperature': core.socat.LICOR_TEMPERATURE,
            'o2_ratio': core.socat.O2_PERCENT,
            'pCO2_air': core.socat.PCO2_AIR,
            'pCO2_sw': core.socat.PCO2_SW,
            'vapor_pressure_air': core.socat.VAPOR_PRESSURE_AIR,
            'vapor_pressure_sw': core.socat.VAPOR_PRESSURE_SW,
            'xco2_sw_wet': core.socat.XCO2_SW_WET,
            'xco2_sw_socat_qc': core.socat.XCO2_SW_QC,
            'xCO2_sw': core.socat.XCO2_SW_DRY,
            'xCO2_air': core.socat.XCO2_AIR_DRY,
        }
        df = df.rename(mapper=mapper, axis='columns')

        if core.socat.PCO2_AIR not in df.columns:
            df[core.socat.PCO2_AIR] = -999
        if core.socat.PCO2_SW not in df.columns:
            df[core.socat.PCO2_SW] = -999

        df = self.incorporate_ssst(df)
        df = self.incorporate_ph(df)
        df = self.incorporate_fugacity(df)
        df = self.account_for_missing_vapor_pressure(df)
        df = self.update_gps(df)
        df = self.update_co2_for_bad_qc(df)
        df = self.update_for_sstc(df)
        df = self.update_aux_for_bad_qc(df)

        df = self._restrict_to_subset_of_columns(df)

        # and last thing before writing the CSV file, collect needed
        # information that will go into the file header

        # This is the same as the Cruise_ID in the XML?
        isMobile = self._get_mobility()
        if isMobile:
            platform_type = "32DB"
        else:
            platform_type = "3164"
        expocode = f"{platform_type}{self.start_date.strftime('%Y%m%d')}"

        # TODO: need explanation for this
        vessel_name = self.mooring_name
        
        # missing data default to -9999, replace with -999
        df.replace(-9999, -999, inplace=True)
        df.dropna(inplace=True)
        
        self.savefilename = '_'.join([self.mooring_name, self.start_date.strftime('%b%Y'), self.end_date.strftime('%b%Y')])
        csvfilename = self.savefilename + '.csv'
        
        with open(self.csvfile / csvfilename, 'wt') as f:
            self.write_csv_file_header(expocode, vessel_name, f)
            df.to_csv(f, index=False, lineterminator='\n')
    
    def _get_mooring_metadata(self):
        """
        Set up mooring name and start and end dates for various data and metadata entries.
        """
        
        # Insert the mooring name.
        try:
            # try to use the "official" name
            self.mooring_name = self.config['metadata'].get('ncei_station_name', None)
            if self.mooring_name is None:
                self.mooring_name = self.site_ids[self.ds.site_code.lower()]['socat_id']
        except KeyError:
            # make a best guestimate
            self.mooring_name = self.ds.site_code.upper()

            msg = (
                f"Unmatched site code \"{self.ds.site_code}\", "
                "using it anyway."
            )
            warnings.warn(msg)
        except AttributeError:
            # no site code?
            warnings.warn("No site code was found.  Using 'Unknown'.")
            self.mooring_name = 'Unknown'
        
        ts = self.ds['time'].to_series()
        self.start_date = ts.iloc[0]
        self.end_date = ts.iloc[-1]

    def update_co2_for_bad_qc(self, df):

        df = self.update_xco2_for_bad_xco2_qc(df)
        df = self.update_pCO2_for_bad_qc(df)
        df = self.update_fugacity_for_bad_qc(df)
        return df

    def update_for_sstc(self, df):

        df = self.update_pCO2_for_sstc(df)
        df = self.update_fugacity_for_sstc(df)
        return df

    def write_csv_file_header(self, expocode, vessel_name, f):
        """
        The first four lines are a header.  The pandas package would need
        to be told to skip them.
        """
        f.write(f'expocode: {expocode}\n')
        f.write(f'vessel name: {vessel_name}\n')

        # have to construct the PI line, unfortunately
        name_list = []
        for pi in self.princ_inv:
            name = f"{pi['last_name']}_{pi['first_name'][0]}."
            name_list.append(name)
        pi_string = '; '.join([name for name in name_list])
        f.write(f"PIs: {pi_string}\n")

        f.write("vessel type: Mooring\n")

    def account_for_missing_vapor_pressure(self, df):
        """
        In the case that post xco2 was not calculated, just make
        it missing data.
        """
        if (
            core.socat.VAPOR_PRESSURE_AIR not in df.columns
            and core.socat.VAPOR_PRESSURE_SW not in df.columns
        ):
            df[core.socat.VAPOR_PRESSURE_AIR] = -999
            df[core.socat.VAPOR_PRESSURE_SW] = -999

        return df

    def update_fugacity_for_bad_qc(self, df):
        """
        If the fugacity qc variables indicate that xco2 was flagged, then set
        the fugacity data to -999.
        """
        
        if 'SST_qc' in df.columns:
            sst_qc = df['SST_qc'].astype(np.uint32)
            df[core.socat.FUGACITY_AIR] = np.where(
                sst_qc != 1,
                -999,
                df[core.socat.FUGACITY_AIR]
            )
            df[core.socat.FUGACITY_SW] = np.where(
                sst_qc != 1,
                -999,
                df[core.socat.FUGACITY_SW]
            )
        
        if 'SSS_qc' in df.columns:
            sss_qc = df['SSS_qc'].astype(np.uint32)
            df[core.socat.FUGACITY_AIR] = np.where(
                sss_qc != 1,
                -999,
                df[core.socat.FUGACITY_AIR]
            )
            df[core.socat.FUGACITY_SW] = np.where(
                sss_qc != 1,
                -999,
                df[core.socat.FUGACITY_SW]
            )
        
        qc = df['CO2 Air QF'].astype(np.uint32)
        df[core.socat.FUGACITY_AIR] = np.where(
            qc == core.quality.SOCAT_BAD,
            -999,
            df[core.socat.FUGACITY_AIR]
        )

        qc = df['CO2 SW QF'].astype(np.uint32)
        df[core.socat.FUGACITY_SW] = np.where(
            qc == core.quality.SOCAT_BAD,
            -999,
            df[core.socat.FUGACITY_SW]
        )

        # DFCO2 doesn't exist in the netCDF file, so just make it's -999
        # locations consistent with FUGACITY_SW and FUGACITY_AIR
        df[core.socat.DFCO2] = np.where(
            (df[core.socat.FUGACITY_SW] == -999) | (df[core.socat.FUGACITY_AIR] == -999),
            -999, df[core.socat.DFCO2]
        )


        return df

    def update_fugacity_for_sstc(self, df):
        """
        If the fugacity qc variables indicate that there was BAD_SSTC, then set
        the fugacity data to -999.  But just for fCO2 sw.
        """
        if 'fCO2_sw_qc' not in df.columns:
            # nothing to do
            return df

        fugacity_sw_qc = df['fCO2_sw_qc'].astype(np.uint32)

        df[core.socat.FUGACITY_SW] = np.where(
            np.bitwise_and(
                fugacity_sw_qc, core.quality.BAD_SSTC
            ) > 0,
            -999,
            df[core.socat.FUGACITY_SW]
        )

        # DFCO2 doesn't exist in the netCDF file, so just make it's -999
        # locations consistent with FUGACITY_SW
        df[core.socat.DFCO2] = np.where(
            df[core.socat.FUGACITY_SW] == -999, -999, df[core.socat.DFCO2]
        )

        return df

    def update_pCO2_for_sstc(self, df):
        """
        If the pCO2 qc variables indicate that there was BAD_SSTC, then set
        the pCO2 data to -999.  But just for pCO2 sw and dpCO2
        """
        if 'pCO2_sw_qc' not in df.columns:
            # nothing to do
            return df

        pCO2_sw_qc = df['pCO2_sw_qc'].astype(np.uint32)

        df[core.socat.PCO2_SW] = np.where(
            np.bitwise_and(
                pCO2_sw_qc, core.quality.BAD_SSTC
            ) > 0,
            -999,
            df[core.socat.PCO2_SW]
        )

        # DPCO2 doesn't exist in the netCDF file, so just make it's -999
        # locations consistent with PCO2_SW and PCO2_AIR
        df[core.socat.DPCO2] = np.where(
            (df[core.socat.PCO2_SW] == -999) | (df[core.socat.PCO2_AIR] == -999),
            -999, df[core.socat.DPCO2]
        )

        return df

    def update_xco2_for_bad_xco2_qc(self, df):
        """
        If the xco2 qc variables indicate that xco2 was flagged, then set the
        xCO2 data to -999.
        """
        qc = df[core.socat.XCO2_AIR_QC].astype(np.uint32)

        df[core.socat.XCO2_AIR_DRY] = np.where(
            qc == core.quality.SOCAT_BAD,
            -999,
            df[core.socat.XCO2_AIR_DRY]
        )
        df[core.socat.XCO2_AIR_WET] = np.where(
            qc == core.quality.SOCAT_BAD,
            -999,
            df[core.socat.XCO2_AIR_WET]
        )

        qc = df[core.socat.XCO2_SW_QC].astype(np.uint32)

        df[core.socat.XCO2_SW_DRY] = np.where(
            qc == core.quality.SOCAT_BAD,
            -999,
            df[core.socat.XCO2_SW_DRY]
        )
        df[core.socat.XCO2_SW_WET] = np.where(
            qc == core.quality.SOCAT_BAD,
            -999,
            df[core.socat.XCO2_SW_WET]
        )

        return df

    def update_pCO2_for_bad_qc(self, df):
        """
        If the pCO2 qc variables indicate that xco2 was flagged, then set the
        pCO2 data to -999.
        """
        if core.socat.SST not in df.columns and core.socat.SALINITY not in df.columns:  # noqa : E501
            # could not have produced pco2 in this case
            return df
        
        if 'SST_qc' in df.columns:
            sst_qc = df['SST_qc'].astype(np.uint32)
            df[core.socat.PCO2_AIR] = np.where(
                sst_qc != 1,
                -999,
                df[core.socat.PCO2_AIR]
            )
            df[core.socat.PCO2_SW] = np.where(
                sst_qc != 1,
                -999,
                df[core.socat.PCO2_SW]
            )
        
        if 'SSS_qc' in df.columns:
            sss_qc = df['SSS_qc'].astype(np.uint32)
            df[core.socat.PCO2_AIR] = np.where(
                sss_qc != 1,
                -999,
                df[core.socat.PCO2_AIR]
            )
            df[core.socat.PCO2_SW] = np.where(
                sss_qc != 1,
                -999,
                df[core.socat.PCO2_SW]
            )
        
        xco2_air_socat_qc = df['CO2 Air QF'].astype(np.uint32)
        df[core.socat.PCO2_AIR] = np.where(
            xco2_air_socat_qc == core.quality.SOCAT_BAD,
            -999,
            df[core.socat.PCO2_AIR]
        )

        xco2_sw_socat_qc = df['CO2 SW QF'].astype(np.uint32)
        df[core.socat.PCO2_SW] = np.where(
            xco2_sw_socat_qc == core.quality.SOCAT_BAD,
            -999,
            df[core.socat.PCO2_SW]
        )

        # DPCO2 doesn't exist in the netCDF file, so just make it's -999
        # locations consistent with PCO2_SW
        df[core.socat.DPCO2] = np.where(
            df[core.socat.PCO2_SW] == -999, -999, df[core.socat.DPCO2]
        )

        return df

    def update_gps(self, df):
        """
        Depending whether this is a stationary or mobile platform:
            Stationary: compute mean GPS, ignoring missing data.
            Mobile: If there is flagged GPS interpolate missing if a mobile platform otherwise.
        """
        
        isMobile = self._get_mobility()
        
        latitude = np.where(
            df['latitude_qc'] != core.quality.GOOD,
            np.nan,
            df['Latitude']
        )
        longitude = np.where(
            df['longitude_qc'] != core.quality.GOOD,
            np.nan,
            df['Longitude']
        )
        
        if isMobile:
            latitude = pd.Series(latitude, index=df['time'])
            latitude = latitude.interpolate(method='time')
            df['Latitude'] = np.round(latitude.to_numpy(), 3)
            
            longitude = pd.Series(longitude, index=df['time'])
            longitude = longitude.interpolate(method='time')
            df['Longitude'] = np.round(longitude.to_numpy(), 3)
        else:
            lat_mean = np.nanmean(latitude)
            df['Latitude'] = np.round(lat_mean, 3)
            
            long_mean = np.nanmean(longitude)
            df['Longitude'] = np.round(long_mean, 3)
        
        return df
    
    def _get_mobility(self):
        with netCDF4.Dataset(self.merge_ncfile) as nc:
            return True if nc.stationary_mobile == 'mobile' else False
    
    def _restrict_to_subset_of_columns(self, df):

        # Only keep a subset of columns.  We need to order them properly,
        # anyway.
        keepers = [
            core.socat.MOORING, core.socat.LATITUDE, core.socat.LONGITUDE,
            core.socat.DATE, core.socat.TIME, core.socat.XCO2_SW_WET,
            core.socat.XCO2_SW_QC, core.socat.VAPOR_PRESSURE_SW,
            core.socat.XCO2_AIR_WET, core.socat.XCO2_AIR_QC,
            core.socat.VAPOR_PRESSURE_AIR,
            core.socat.LICOR_PRESSURE, core.socat.LICOR_TEMPERATURE,
            core.socat.O2_PERCENT,
            core.socat.SST, core.socat.SALINITY,
            core.socat.XCO2_SW_DRY, core.socat.XCO2_AIR_DRY,
            core.socat.FUGACITY_SW, core.socat.FUGACITY_AIR, core.socat.DFCO2,
            core.socat.PCO2_SW, core.socat.PCO2_AIR, core.socat.DPCO2,
            core.socat.PH, core.socat.PH_QC,
        ]

        chl_ntu_cols = [
            core.socat.CHL, core.socat.CHL_QC,
            core.socat.NTU, core.socat.NTU_QC
        ]
        if all(x in df.columns for x in chl_ntu_cols):
            keepers = keepers + chl_ntu_cols

        doxy_cols = [
            core.socat.DISSOLVED_OXYGEN, core.socat.DISSOLVED_OXYGEN_QC
        ]
        if all(x in df.columns for x in doxy_cols):
            keepers = keepers + doxy_cols

        return df[keepers]

    def incorporate_fugacity(self, df):
        """
        Fold the fugacity air, sw, and dfCO2 into the dataframe.
        """

        if 'fCO2_air_qc' in df.columns:

            # dfCO2 is just the difference between two columns
            df[DFCO2] = df[FUGACITY_SW] - df[FUGACITY_AIR]

        else:
            # It does not have them.  So we need to supply these columns into
            # the dataframe and give them "missing" data.
            msg = (
                'No fugacity was located.  Missing data (-999) will be used.'
            )
            self.logger.warning(msg)

            df[FUGACITY_AIR] = -999
            df[FUGACITY_SW] = -999
            df[DFCO2] = -999

        return df

    def incorporate_ssst(self, df):
        """
        Fold the salinity and SST (if they exist) into the dataframe.
        """
        # It's possible that the netCDF file doesn't have salinity or sst.
        if 'SSS' in df.columns and 'SST' in df.columns:

            # It does have them.  So the variables have to be renamed and
            # processed for QC since we don't carry over the QC variable.

            sss, qc = df['SSS'], df['SSS_qc']
            sss = sss.where(
                qc == core.quality.GOOD, core.DEFAULT_SOCAT_FILLVALUE
            )
            df['SSS'] = sss

            sst, qc = df['SST'], df['SST_qc']
            sst = sst.where(
                qc == core.quality.GOOD, core.DEFAULT_SOCAT_FILLVALUE
            )
            df['SST'] = sst

            # and finally rename them to socat
            mapper = {
                'SSS': core.socat.SALINITY,
                'SST': core.socat.SST,
            }
            df = df.rename(mapper=mapper, axis='columns')

        else:
            # It does not have them.  So we need to supply these columns into
            # the dataframe and give them "missing" data.
            msg = (
                'No SSS or SST was located.  Missing data (-999) will be used.'
            )
            self.logger.warning(msg)

            df[core.socat.SALINITY] = -999
            df[core.socat.SST] = -999

        return df

    def incorporate_ph(self, df):
        """
        It's possible that the netCDF file doesn't have PH
        """
        if 'pH_sw' in df.columns:
            # It does have pH columns.  So the variables have to be renamed
            # to SOCAT names
            
            ph_qc = df['pH_sw_socat_qc'].astype(np.uint32)
            df['pH_sw'] = np.where(
                (ph_qc == core.quality.SOCAT_BAD) | (ph_qc == core.quality.SOCAT_MISSING),
                -999,
                df['pH_sw']
            )
            mapper = {
                'pH_sw': core.socat.PH,
                'pH_sw_socat_qc': core.socat.PH_QC
            }

            df = df.rename(mapper=mapper, axis='columns')
        else:
            # It does not have them.  So we need to supply these columns into
            # the dataframe and give them "missing" data.
            msg = (
                'No SAMI PH was located.  Missing data (-999) will be used.'
            )
            self.logger.warning(msg)

            df[core.socat.PH] = -999
            df[core.socat.PH_QC] = core.quality.SOCAT_MISSING

        return df
    
    def update_aux_for_bad_qc(self, df):
        if core.socat.CHL_QC in df.columns:
            chl_qc = df[core.socat.CHL_QC].astype(np.uint32)
            df[core.socat.CHL] = np.where(
                (chl_qc == core.quality.SOCAT_BAD) | (chl_qc == core.quality.SOCAT_MISSING),
                -999,
                df[core.socat.CHL]
            )
        if core.socat.NTU_QC in df.columns:
            ntu_qc = df[core.socat.NTU_QC].astype(np.uint32)
            df[core.socat.NTU] = np.where(
                (ntu_qc == core.quality.SOCAT_BAD) | (ntu_qc == core.quality.SOCAT_MISSING),
                -999,
                df[core.socat.NTU]
            )
        if core.socat.DISSOLVED_OXYGEN_QC in df.columns:
            o2_qc = df[core.socat.DISSOLVED_OXYGEN_QC].astype(np.uint32)
            df[core.socat.DISSOLVED_OXYGEN] = np.where(
                (o2_qc == core.quality.SOCAT_BAD) | (o2_qc == core.quality.SOCAT_MISSING),
                -999,
                df[core.socat.DISSOLVED_OXYGEN]
            )
        
        return df
    
    def update_additional_information_element(self):
        """
        The Additional_Information element has a few items that need to be
        interpolated.

        1. the licor pressure adjustment needs to be inserted into the metadata
        2. loss of span
        """
        kwargs = {}

        path = 'Additional_Information'
        elt = self.doc.xpath(path)[0]

        # Get the licor pressure correction. Six characters for the item,
        # zero-padded, a +/- sign, and three digits of precision.
        correction = self.licor_pressure_correction
        kwargs['licor_pressure_bias'] = f"{correction:0<+6.3}"

        kwargs['loss_of_span_stmt'] = self.setup_loss_of_span_statement()

        item = self.setup_licor_coefficent_equations()
        kwargs['licor_coefficient_regression_equation'] = item

        item = self.setup_mbl_correction()
        kwargs['mbl_correction'] = item
        
        item = self.setup_chl_correction()
        kwargs['chl_correction'] = item
        
        kwargs['missing_data'] = 'o No data = -999'

        elt.text = elt.text.format(**kwargs)
    
    def update_citation(self):
        with netCDF4.Dataset(self.merge_ncfile) as nc:
            try:
                contributors = nc.contributors_citation
            except AttributeError:
                statement = ''
            else:
                contributors = contributors.split(', ')
                contributors_text = ', '.join(contributors[:-1]) + f', and {contributors[-1]}'
                platform = 'uncrewed surface vehicle' if nc.stationary_mobile == 'mobile' else 'mooring'
                statement = f"{contributors_text}. {self.start_date.strftime('%Y')}. High-resolution ocean and atmosphere pCO2 time-series measurements from {platform} {self.mooring_name}."
        path = 'Citation'
        elt = self.doc.xpath(path)[0]
        elt.text = statement
    
    def update_link_note(self):
        with netCDF4.Dataset(self.merge_ncfile) as nc:
            try:
                link_citation = nc.link_citation
            except AttributeError:
                statement = ''
            else:
                statement = f"Refer to {link_citation} for links to actual data."
        path = 'Data_Set_Link/Link_Note'
        elt = self.doc.xpath(path)[0]
        elt.text = statement
        

    def setup_licor_coefficent_equations(self):
        """
        Record the details of the MBL correction.
        """
        if self.models_file is None:
            msg = (
                'No models file was provided, licor coefficient regression '
                'information will not be saved to the SOCAT file.'
            )
            self.logger.warning(msg)
            return

        with open(self.models_file, mode='rb') as f:
            [regr_models, kmeans_model] = pickle.load(f)

        statements = []
        for cluster_id in range(kmeans_model.n_clusters):

            slope = regr_models[cluster_id].params['temperature']
            intercept = regr_models[cluster_id].params['Intercept']
            rsquared = regr_models[cluster_id].rsquared

            statement = (
                f"o Post calculation and correlation between Licor "
                f"temperature and span coefficient "
                f"at cluster center {cluster_id} is: "
                f"Licor coef = {slope:.6f} * Temp + {intercept:.4f}, "
                f"r^2 = {rsquared:.4f}"
            )

            statements.append(statement)

        statement = '\n\n'.join(statements)
        return statement

    def setup_mbl_correction(self):
        """
        Create a blurb concerning the MBL correction.  We need to record both
        the size of the correction and when the MBL data was published.
        """

        with netCDF4.Dataset(self.merge_ncfile) as nc:
            try:
                mbl_correction = nc.mbl_correction
                timestamp = nc.mbl_timestamp
            except AttributeError:
                statement = ''
            else:
                adjustment_phrase = f"an adjustment of {mbl_correction} umol mol-1" if mbl_correction != 0 else "no adjustment"
                statement = (
                    f'''o As part of the QC process, xCO2 air measurements are compared to the following data sets when available: previous MAPCO2 deployment at same site if overlap on recovery/deployment, following MAPCO2 deployment at same site if overlap on recovery/deployment, and Marine Boundary Layer (MBL) xCO2 air data from GlobalView-CO2.  This MAPCO2 deployment is offset from the available comparison data sets, and {adjustment_phrase} was applied to the data set.
   Dlugokencky, E.J., K.W. Thoning, P.M. Lang, and P.P. Tans (2019),
   NOAA Greenhouse Gas Reference from Atmospheric Carbon Dioxide
   Dry Air Mole Fractions from the NOAA ESRL Carbon Cycle Cooperative
   Global Air Sampling Network.
   Data Path: ftp://aftp.cmdl.noaa.gov/data/trace_gases/co2/flask/surface/.

o MBL Data were last downloaded from ESRL on {timestamp.split()[0]}.'''
                )

        return statement

    def setup_loss_of_span_statement(self):

        try:
            start = self.ds.loss_of_span_start
            stop = self.ds.loss_of_span_stop
        except AttributeError:
            # Assume no loss of span, make the blurb empty
            statement = ''
        else:
            statement = (
                f"o The standard reference gas ran out between {start} and "
                f"{stop}.  Missing reference gas coefficients were computed "
                f"using the correlation between Licor temperature and the "
                f"coefficients in the time range of good span values.  xCO2 "
                f"air and sw (wet) from {start} to {stop} were then "
                f"recalculated using these computed coefficients."
            )

        return statement

    def update_co2_sensor_calibration(self):
        """
        The initial span calibration value needs to be inserted into the
        metadata.
        """
        path = '/'.join([
            'Method_Description',
            'CO2_Sensors',
            'CO2_Sensor',
            'CO2_Sensor_Calibration',
        ])
        elt = self.doc.xpath(path)[0]

        elt.text = elt.text.format(spanconc=self.initial_span_cal)

    def update_cruise_id(self):
        """
        Update the Cruise ID element.  This seems to be a particular constant,
        "3164" is the code for a stationary/mooring platform plus the YYMMDD of the initial starting time.  
        "32DB" is the code for a mobile/ship platform
        """
        path = 'Cruise_Info/Experiment/Cruise/Cruise_ID'
        elt = self.doc.xpath(path)[0]

        ts = self.ds['time'].to_series()
        isMobile = self._get_mobility()
        if isMobile:
            platform_type = "32DB"
        else:
            platform_type = "3164"
        cruise_id = f"{platform_type}{ts.iloc[0].strftime('%Y%m%d')}"
        elt.text = cruise_id
    
    def update_experiment_and_vessel_info(self):
        """Update experiment type and vessel info based on site name and platform type"""
        platform_type_paths = [
                               'Cruise_Info/Experiment/Experiment_Type',
                               'Cruise_Info/Vessel/Vessel_Type'
                              ]
        vessel_name_path = 'Cruise_Info/Vessel/Vessel_Name'
        
        if self._get_mobility():
            platform_type = 'Uncrewed Surface Vehicle'
        else:
            platform_type = 'Moored Buoy'
        
        for path in platform_type_paths:
            elt = self.doc.xpath(path)[0]
            elt.text = platform_type
        
        elt = self.doc.xpath(vessel_name_path)[0]
        elt.text = self.mooring_name
        
    def update_temporal_bounds(self):
        """
        Update the temporal coverage elements.
        """
        ts = self.ds['time'].to_series()

        path = 'Cruise_Info/Experiment/Cruise/Temporal_Coverage/Start_Date'
        elt = self.doc.xpath(path)[0]
        elt.text = ts.iloc[0].strftime('%Y%m%d')

        path = 'Cruise_Info/Experiment/Cruise/Temporal_Coverage/End_Date'
        elt = self.doc.xpath(path)[0]
        elt.text = ts.iloc[-1].strftime('%Y%m%d')

    def update_geospatial_bounds(self):
        """
        Construct the bounding box in SOCAT XML.
        """
        path = 'Cruise_Info/Experiment/Cruise/Geographical_Coverage/Bounds'

        with netCDF4.Dataset(self.merge_ncfile) as nc:
            elt = self.doc.xpath(path + '/Westernmost_Longitude')[0]
            elt.text = f"{nc.geospatial_lon_min:.3f}"

            elt = self.doc.xpath(path + '/Easternmost_Longitude')[0]
            elt.text = f"{nc.geospatial_lon_max:.3f}"

            elt = self.doc.xpath(path + '/Northernmost_Latitude')[0]
            elt.text = f"{nc.geospatial_lat_max:.3f}"

            elt = self.doc.xpath(path + '/Southernmost_Latitude')[0]
            elt.text = f"{nc.geospatial_lat_min:.3f}"

    def setup_chl_correction(self):
        if self.config['QC']['chl_global_conversion'] == 1:
            statement = (
            '''o During the QC process, the community-established calibration bias of 2 for the WET Labs ECO-series fluorometer was applied to these in situ fluorometric chlorophyll values. See: 
   Roesler, C. , and others. 2017.
   Recommendations for obtaining unbiased chlorophyll estimates from in situ chlorophyll fluorometers: 
   A global analysis of WET Labs ECO sensors.
   Limnol. Oceanogr.: Methods 15: 572-585. doi:10.1002/lom3.10185.
o Only nighttime measurements of chlorophyll (defined as 21:00 to 03:00 local time) are published, given the lack of validation data for correcting daytime quenching.  All daytime measurements are flagged as missing (QF = 5).
o Chlorophyll, turbidity, and Oxygen measurement outliers are determied as 5 standard deviations away from the median of a two week interval.
o Gross ranges flags for chlorophyll, turbidity, and oxygen were measurements outside of 0 and 25 ug/l for chorophyll, 0 and 25 for NTU, and 0 and 400 umol/kg for oxygen.
            '''
            )
        else:
            statement = ('')
        
        return statement