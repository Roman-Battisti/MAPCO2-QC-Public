# standard library imports
import datetime as dt
import importlib.resources as ir
import logging
import pathlib
import sys

# 3rd party library imports
import dateutil.parser
import netCDF4
import numpy as np
import xarray as xr
import yaml

# local imports
from xco2qc import core
from xco2qc.science_algorithms import calc_pco2, calc_fugacity
from . import data


class InvalidMapCO2ConfigFile(RuntimeError):
    """
    Raise this exception if the configuration file is somehow invalid.
    """
    pass


class MissingParametersError(RuntimeError):
    """
    Raise this exception if we are missing parameters needed for further
    computation.
    """
    pass


class MapCO2core(object):
    """
    This is the base class for everything because we implement logging and
    configuration file handling.

    Attributes
    ----------
    config : dict
        runtime configuration
    logger : logging.Logger
        logs processing events
    output_directory_tree_root : path
        This is the root directory for all output.
    require_config_in_output_directory_tree : bool
        If true, the configuration file must already be present in the output
        directory tree.  This should be false when doing the raw data
        conversion.
    src_dir : path (optional)
        location of output data files
    dst_dir : path (optional)
        location of output
    verbosity : str
        corresponds to a logging level
    """

    def __init__(
        self, verbosity=None, logger_name=None,
        src_dir=None, dst_dir=None,
        require_config_in_output_directory_tree=True
    ):
        self.require_config_in_output_directory_tree = require_config_in_output_directory_tree  # noqa : E501
        
        self._is_notebook = self._check_if_jupyter()
        
        if src_dir is None:
            self.src_dir = None
        else:
            self.src_dir = pathlib.Path(src_dir)

            # Not all sub classes make use of this because not all have the
            # concept of a 'src_dir'.
            self.cycle_header_ncfile = self.src_dir / core.CYCLE_HEADER_NCFILE
            self.epoff_ncfile = self.src_dir / core.licor.EPOFF_NCFILE
            self.apoff_ncfile = self.src_dir / core.licor.APOFF_NCFILE
            self.spoff_ncfile = self.src_dir / core.licor.SPOFF_NCFILE

            self.durafet_ncfile = self.src_dir / core.DURAFET_NCFILE
            self.external_met_ncfile = self.src_dir / core.EXTERNAL_MET_NCFILE
            self.external_sami_ncfile = self.src_dir / core.EXTERNAL_SAMI_NCFILE  # noqa : E501
            self.external_sbe63_ncfile = self.src_dir / core.EXTERNAL_SBE63_NCFILE  # noqa : E501
            self.external_seafet_ncfile = self.src_dir / core.EXTERNAL_SEAFET_NCFILE  # noqa : E501
            self.historical_ncfile = self.src_dir / core.HISTORICAL_NCFILE
            self.met_ncfile = self.src_dir / core.MET_NCFILE
            self.prawler_ncfile = self.src_dir / core.PRAWLER_CTD_NCFILE
            self.sami_ncfile = self.src_dir / core.SAMI_NCFILE
            self.sbe16_ncfile = self.src_dir / core.SBE16_NCFILE
            self.seafet_ncfile = self.src_dir / core.SEAFET_NCFILE

        if dst_dir is None:
            if src_dir is not None:
                # if no destination directory is given, then we assume we are
                # writing back to the same location.
                self.dst_dir = self.src_dir
                self.output_directory_tree_root = self.src_dir.parents[0]
            else:
                self.output_directory_tree_root = None
                self.dst_dir = None
        else:
            self.output_directory_tree_root = pathlib.Path(dst_dir).parents[0]
            self.dst_dir = pathlib.Path(dst_dir)

        if (
            self.src_dir is not None
            and self.dst_dir is not None
            and self.output_directory_tree_root is not None
        ):
            # the src_dir and dst_dir have to be at the same directory level
            dst_dir2 = self.src_dir.parents[0] / self.dst_dir.name
            if self.dst_dir != dst_dir2:
                msg = (
                    f"The source directory \"{self.src_dir}\" and the "
                    f"destination directory \"{self.dst_dir}\" must be at the "
                    "same level."
                )
                raise RuntimeError(msg)

        self.read_config_file()

        if verbosity is None or verbosity == 'NOTSET':
            self.verbosity = self.config['logging']['verbosity'].upper()
        else:
            # If specified by argument, that takes precedence over the
            # configuration file.
            self.verbosity = verbosity.upper()

        self.setup_logging(logger_name)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        pass

    def _check_if_jupyter(self):
        try:
            from IPython import get_ipython
            shell = get_ipython().__class__.__name__
            
            if shell == "ZMQInteractiveShell":
                return True  # running in a Jupyter Notebook or JupyterLab
            elif shell == "TerminalInteractiveShell":
                return False  # Terminal based IPython
            else:
                return False  # other IPython
        
        except (NameError, ImportError):
            return False  # Standard python interpreter
    
    def determine_src_sstc_ncfile(self):
        """
        SSS and SST could be found in any of a MET, external MET, or prawler
        netCDF file.

        Returns
        -------
        netCDF file containing the src SSS/SST, along with the variable name in
        the file.
        """
        sss_varname, sst_varname, ncfile = None, None, None

        # look at the ncfiles in order of lowest priority to highest.  The
        # highest priority one that exists, wins.
        if self.prawler_ncfile.exists():
            ncfile = self.prawler_ncfile
            sss_varname = 'salinity'
            sst_varname = 'temperature'

        if self.met_ncfile.exists():
            ncfile = self.met_ncfile
            sss_varname = 'SSS'
            sst_varname = 'SST'

        if self.external_met_ncfile.exists():
            ncfile = self.external_met_ncfile
            sss_varname = 'SSS'
            sst_varname = 'SST'

        return sss_varname, sst_varname, ncfile

    def determine_src_ph_ncfile(self):
        """
        ph could be found in any of a SAMI, SEAFET, external SAMI, or external
        SEAFET netCDF file.

        Returns
        -------
        netCDF file containing the src ph, along with the variable name in the
        file.
        """
        varname, candidate = None, None

        # look at the ncfiles in order of lowest priority to highest.  The
        # highest priority one that exists, wins.
        if self.seafet_ncfile.exists():
            candidate = self.seafet_ncfile
            varname = 'ph'

        if self.durafet_ncfile.exists():
            candidate = self.durafet_ncfile
            varname = 'ph_int'

        if self.sami_ncfile.exists():
            candidate = self.sami_ncfile
            varname = 'ph'

        if self.external_seafet_ncfile.exists():
            candidate = self.external_seafet_ncfile
            varname = 'ph'

        if self.external_sami_ncfile.exists():
            candidate = self.external_sami_ncfile
            varname = 'ph'

        return varname, candidate

    def get_good_ts(self, ncfile=None, ds=None, varname=None, name=None):
        """
        Parameters
        ----------
        ncfile : path or str or None
            Path to netCDF file
        ds : xarray.DataSet
            netCDF file data
        varname : string
            name of netCDF variable
        name : str or None
            If not None, assign this name to the pd.Series.  Otherwise assign
            varname.

        Returns
        -------
        Retrieve a time series for a variable.  All QC values that are not
        GOOD get replaced with NaN.
        """
        if ncfile is not None:
            with xr.open_dataset(ncfile) as ds:
                ds = ds.load()

        ts = ds[varname].to_pandas()
        ts.name = varname

        if name is None:
            ts.name = varname
        else:
            ts.name = name

        # is there a valid range?  technically this might be overkill, because
        # if there is an associated quality variable, then the valid range
        # is taken into account there.  but this handles the case where there
        # is a valid range but no associated quality variable.
        try:
            valid_min, valid_max = ds[varname].valid_range
        except AttributeError:
            pass
        else:
            ts[(ts < valid_min) | (ts > valid_max)] = np.nan

        # is there a QC variable?
        try:
            qc_vars = ds[varname].ancillary_variables.split(' ')
        except AttributeError:
            # nothing else to do, we are done
            return ts

        try:
            # use a socat qc variable if it is there
            qc_var = [
                var for var in qc_vars
                if ds[var].standard_name == 'status_flag'
                and hasattr(self.merge_ds[var], 'flag_values')
            ][0]
        except (AttributeError, IndexError):
            pass
        else:
            qc = ds[qc_var].to_pandas()
            ts[qc != core.quality.SOCAT_GOOD] = np.nan
            return ts

        try:
            # use a regular qc variable if it is there
            qc_var = [
                var for var in qc_vars
                if ds[var].standard_name == 'status_flag'
                and hasattr(ds[var], 'flag_masks')
            ][0]
        except (AttributeError, IndexError):
            pass
        else:
            qc = ds[qc_var].to_pandas()
            ts[qc != core.quality.GOOD] = np.nan
            return ts

        # Ok, no qc variable.  Just return as-is.
        return ts

    def setup_logging(self, logger_name, logfile=None):
        """
        Parameters
        ----------
        verbosity : str
            Logging level
        logger_name : str
            Identifier for the logger so it can be located elsewhere.
        """
        level = getattr(logging, self.verbosity)

        self.logger = logging.getLogger(f"xco2qc.{logger_name}")
        self.logger.setLevel(level)

        # it's possible that this could be run a 2nd time within the same
        # python session, e.g. a jupyter notebook.  So don't add any new
        # handlers, otherwise we can get duplicated (triplicated, etc.) logging
        # output.
        if any(
            isinstance(x, logging.StreamHandler) for x in self.logger.handlers
        ):
            return

        format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        formatter = logging.Formatter(format)

        h = logging.StreamHandler(sys.stdout)
        h.setLevel(level)
        h.setFormatter(formatter)

        self.logger.addHandler(h)

    def clear_flag(self, qc, flag):
        """
        Clear a QC flag.
        """
        bit = int(np.log2(flag))
        mask = (~(1 << bit)) & 0xFFFFFFFF
        return qc & mask

    def clear_qc(self, ncfile, varname, flag):
        """
        Parameters
        ----------
        ncfile : str or path or netCDF4.Dataset
            The netCDF file.
        varname : str
            The netCDF variable
        flag : int
            Mnemonic

        Clear a QC flag from a netCDF variable.  This is necessary in case we
        need to change thresholds and run a QC check a 2nd time.  We would want
        the results of the first run to be cleared out so that they don't
        contaminate the 2nd run.
        """
        def _clear_qc(nc, varname, flag):
            qc = nc[varname][:]
            qc = self.clear_flag(qc, flag)
            nc[varname][:] = qc

        if isinstance(ncfile, str) or isinstance(ncfile, pathlib.Path):
            with netCDF4.Dataset(ncfile, mode='r+') as nc:
                _clear_qc(nc, varname, flag)
        else:
            _clear_qc(ncfile, varname, flag)

    def read_config_file(self):
        """
        Read the configuration file for MAPCO2 QC.  It's ok if one does not
        exist, in that case, defaults are supplied.
        """
        # Look for a config file in the output directory (and possibly its
        # parent) first.
        if (
            self.require_config_in_output_directory_tree
            and self.output_directory_tree_root is not None
        ):
            path = self.output_directory_tree_root / 'config.yml'
            if path.exists():
                with path.open() as f:
                    self.config = yaml.safe_load(f)
                    self._validate_configuration()
                    return

        # Next look for a config file in the current directory.
        path = pathlib.Path.cwd() / 'mapco2.yml'
        if path.exists():
            with path.open() as f:
                self.config = yaml.safe_load(f)
                self._validate_configuration()
                self._save_config()
                return

        # Read the default configuration.
        with ir.as_file(ir.files(data).joinpath('default_qc_config.yml')) as path:
            with path.open() as f:
                self.config = yaml.safe_load(f)
                self._validate_configuration()
                self._save_config()
                return

        msg = (
            "The specified output directory path does not contain the "
            "configuration file in the parent directory.  You must "
            "choose an output directory tree and be consistent with "
            "your choice."
        )
        raise RuntimeError(msg)

    def _save_config(self):

        if self.output_directory_tree_root is not None:
            output_path = self.output_directory_tree_root / 'config.yml'
            with output_path.open(mode='wt') as f:
                yaml.dump(self.config, f)

    def _validate_configuration(self):

        # Check for required keys
        required_keys = [
            'air_diff_range_higher', 'air_diff_range_lower',
            'equil_diff_range_higher', 'equil_diff_range_lower',
            'max_air_xco2_std', 'max_equil_xco2_std', 'max_rh_std',
            'max_rh_temp_std', 'xco2_trend_std', 'num_points_eachside',
            'ppm_above_span_cal', 'ppm_above_zero', 'ppm_below_span_cal',
            'ppm_below_zero', 'initial_span_cal', 'start', 'stop',
        ]
        for key in required_keys:
            if key not in self.config['QC'].keys():
                msg = f"{key} key not found in configuration"
                raise InvalidMapCO2ConfigFile(msg)

        # Transform the datetime keys
        if not isinstance(self.config['QC']['start'], dt.datetime):
            self.config['QC']['start'] = dateutil.parser.parse(self.config['QC']['start'])  # noqa : E501
        if not isinstance(self.config['QC']['stop'], dt.datetime):
            self.config['QC']['stop'] = dateutil.parser.parse(self.config['QC']['stop'])  # noqa : E501

        self.check_time_split()

    def check_time_split(self):
        """
        Verify the correctness of the instrument_time_split, if it exists
        """
        if 'instrument_time_split' in self.config['QC']:

            if self.config['QC']['instrument_time_split'] is None:
                # if the time split is not defined, just remove it for now
                self.config['QC'].pop('instrument_time_split')
                return

            if not isinstance(
                self.config['QC']['instrument_time_split'], dt.datetime
            ):
                msg = (
                    'Bad instrument split time value, '
                    f'{self.config["QC"]["instrument_time_split"]} '
                )
                raise RuntimeError(msg)

    def _plot_mode(self, ncfile, ax=None):

        with xr.open_dataset(ncfile) as ds:
            mode = ds['mode'].to_series()
            categories = ds['mode'].categories
            codes = ds['mode'].codes

        if np.isscalar(codes):
            # just a single code means that we have to make it iterable
            codes = [codes]

        # Plot the whole thing.  This gets us around a strange issue with the
        # time axis not updating properly.
        mode.plot.line(marker='*', linestyle='none', ax=ax)

        for category, code in zip(categories.split(), codes):
            ts = mode[mode == code]
            ts.plot.line(
                marker='*', linestyle='none', label=category, ax=ax
            )

        # drop the mode
        handles, labels = ax.get_legend_handles_labels()
        handles, lables = list(
            zip(*[(h, l) for h, l in zip(handles, labels) if l != 'mode'])
        )
        ax.legend(handles, labels)

        ax.set_ylabel('mode')

    def get_units(self, configfile, variable):
        """
        Retrieve variable units from our configuration files.
        """
        path = ir.files('xco2qc.core.vardefs.config').joinpath(configfile)
        with path.open() as f:
            d = yaml.safe_load(f)
            units = d[variable]['attributes']['units']

        return units

    def get_pco2_inputs(self):
        """
        Gather all the inputs needed to compute pCO2
        """

        with xr.open_dataset(self.merge_ncfile) as ds:
            
            if 'SSS' not in ds or 'SST' not in ds:
                # If we don't have this, we can't calculate pco2
                message = (
                    "No SSS or SST, can't calculate saturated vapor pressure, "
                    "can't calculate pco2."
                )
                raise MissingParametersError(message)

            df = ds.to_dataframe()[['SSS', 'SST', 'xCO2_sw', 'xCO2_air']]

            # convert to kelvin
            df['SST'] += 273.15

        # epoff pressure (sw)
        # if user has made a licor pressure adjustment, ds['pressure'] is not adjusted, use atm_pressure variable (if it exists)
        with xr.open_dataset(self.merge_ncfile) as ds:
            if 'atm_pressure' in ds:
                df['press_sw'] = ds['atm_pressure'].to_pandas() / 10
                
                return df
        
        with xr.open_dataset(self.epoff_ncfile) as ds:
            df['press_sw'] = ds['pressure'].to_pandas()

        return df

    def recalculate_pco2(self):

        df = self.get_pco2_inputs()

        df['pco2_sw'] = calc_pco2(
            df['press_sw'], df['SSS'], df['SST'], df['xCO2_sw']
        )
        df['pco2_air'] = calc_pco2(
            df['press_sw'], df['SSS'], df['SST'], df['xCO2_air']
        )
        df['pco2_qc'] = np.full(df['pco2_sw'].shape, core.quality.GOOD)

        return df

    def gather_fco2_inputs(self):

        with xr.open_dataset(self.merge_ncfile) as ds:
            df = ds.to_dataframe()

        if 'SSS' not in df or 'SST' not in df:
            msg = "No SSS/SST data available, not calculating fugacity."
            raise MissingParametersError(msg)

        keepers = [
            'SSS', 'SSS_qc', 'SST', 'SST_qc',
            'xCO2_air', 'xCO2_air_qc',
            'xCO2_sw', 'xCO2_sw_qc',
        ]

        if "atm_pressure" in df:
            df["pressure"] = df["atm_pressure"]
            df["pressure_qc"] = df["atm_pressure_qc"]
            df = df[keepers + ["pressure", "pressure_qc"]]
        else:
            df = df[keepers]
            epoff_ncfile = self.src_dir / core.licor.EPOFF_NCFILE
            with xr.open_dataset(epoff_ncfile) as ds:
                # convert from kPa to hPa
                df['pressure'] = ds['pressure'].values * 10
                df['pressure_qc'] = ds['pressure_qc']

        # xarray want to return all columns as float, but the QC columns should
        # unsigned 32 bit integers
        for x in df.columns:
            if x.endswith('_qc'):
                df[x] = df[x].astype(np.uint32)

        return df

    def recalculate_fco2(self):

        df = self.gather_fco2_inputs()

        valid_range = core.vardefs.data_dict['merge']['fCO2_air']['attributes']['valid_range']  # noqa : E501

        df['fco2_air'] = calc_fugacity(
            df['pressure'], df['SST'], df['SSS'], df['xCO2_air']
        )
        df['fco2_air_qc'] = self.calc_fugacity_qc(
            df['fco2_air'], valid_range,
            df['pressure_qc'],
            df['SST_qc'], df['SSS_qc'], df['xCO2_air_qc']
        )

        df['fco2_sw'] = calc_fugacity(
            df['pressure'], df['SST'], df['SSS'], df['xCO2_sw']
        )
        df['fco2_sw_qc'] = self.calc_fugacity_qc(
            df['fco2_sw'], valid_range,
            df['pressure_qc'], df['SST_qc'], df['SSS_qc'], df['xCO2_sw_qc']
        )

        return df

    def calc_fugacity_qc(
        self, data, valid_range, P_hPa_qc, T_qc, S_qc, X1_qc
    ):
        """
        Fugacity becomes defined here, so we have to do a special case to
        calculate quality flags.
        """

        # valid range check
        valid_min, valid_max = valid_range
        qc = np.where(
            np.logical_or(data < valid_min, data > valid_max),
            core.quality.OUT_OF_RANGE,
            core.quality.GOOD
        )

        # Missing data check on the other variables
        qc = np.where(
            np.bitwise_and(P_hPa_qc, core.quality.MISSING_DATA) > 1,
            core.quality.MISSING_DATA,
            qc
        )
        qc = np.where(
            np.bitwise_and(T_qc, core.quality.MISSING_DATA) > 1,
            core.quality.MISSING_DATA,
            qc
        )
        qc = np.where(
            np.bitwise_and(S_qc, core.quality.MISSING_DATA) > 1,
            core.quality.MISSING_DATA,
            qc
        )
        qc = np.where(
            np.bitwise_and(X1_qc, core.quality.MISSING_DATA) > 1,
            core.quality.MISSING_DATA,
            qc
        )

        # Out of range or spike detection on SSTC results in BAD_SSTC
        qc = np.where(
            np.bitwise_and(T_qc, core.quality.OUT_OF_RANGE) > 1,
            core.quality.BAD_SSTC,
            qc
        )
        qc = np.where(
            np.bitwise_and(S_qc, core.quality.OUT_OF_RANGE) > 1,
            core.quality.BAD_SSTC,
            qc
        )

        qc = np.where(
            np.bitwise_and(T_qc, core.quality.SPIKE_DETECTED) > 1,
            core.quality.BAD_SSTC,
            qc
        )
        qc = np.where(
            np.bitwise_and(S_qc, core.quality.SPIKE_DETECTED) > 1,
            core.quality.BAD_SSTC,
            qc
        )

        return qc


def file2label(ncfile):
    """
    Produce a short label given a netCDF file with a pump_mode attribute.

    Parameters
    ----------
    ncfile : path or str
        The netCDF file, presumably has a 'pump_mode' attribute.

    Returns
    -------
    str
    """
    label_dict = {
        'air pump on': 'APON',
        'air pump off': 'APOFF',
        'equil pump on': 'EPON',
        'equil pump off': 'EPOFF',
        'span pump on': 'SPON',
        'span pump off': 'SPOFF',
        'span post cal': 'SPOSTCAL',
        'zero pump on': 'ZPON',
        'zero pump off': 'ZPOFF',
        'zero post cal': 'ZPOSTCAL',
    }
    with netCDF4.Dataset(ncfile) as nc:
        label = label_dict[nc.pump_mode]

    return label
