"""
Here lie the entry points for command line scripts.
"""

# Standard library imports
import argparse
import pathlib
import tempfile

# Local imports
from . import core
from xco2qc.adjustments import XCO2Adjustments
from xco2qc.data_reduction import XCO2Reduce
from xco2qc.export_to_csv import ExportToCSV
from xco2qc.mbl import CompareMBL
from xco2qc.merge import XCO2Merge
from xco2qc.metadata_conventions import MetadataWriter
from xco2qc.post_xco2_processing import PostXCO2Calc
from xco2qc.pre_xco2_processing import PreXCO2Calc
from xco2qc.qc import QCChecker
from xco2qc.raw_text_conversion import RawTextToRawNC
from xco2qc.socat import SocatWriter
from xco2qc.socat_qc import SocatQC
from xco2qc.trim_netcdf import TrimXCO2netCDF

_LOGGING_VERBOSITY_CHOICES = ["critical", "error", "warning", "info", "debug"]


def import_mapco2():
    """
    Entry point for converting RAW text file to netCDF.
    """
    parser = argparse.ArgumentParser()

    help = 'Input file, can be either raw text file or a saildrone netCDF file'
    parser.add_argument('input', help=help)

    help = "Output directory"
    default = pathlib.Path(tempfile.gettempdir())
    parser.add_argument('output', help=help, default=default)

    parser.add_argument('--deployment-number', help='Site ID')

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with RawTextToRawNC(
        args.input, args.output,
        deployment_number=args.deployment_number,
        verbosity=args.verbosity.upper()
    ) as p:
        p.run()


def mapco2_reduce():
    """
    Entry point for reduce RAW netCDF
    """
    parser = argparse.ArgumentParser()

    help = 'Source directory of raw netCDF files'
    parser.add_argument('input', help=help)

    help = "Destination directory for reduced netCDF files"
    parser.add_argument('output', help=help)

    parser.add_argument('--chl-channel', type=int, default=0)
    parser.add_argument('--ntu-channel', type=int, default=1)
    parser.add_argument('--o2-channel', type=int, default=2)
    parser.add_argument('--o2-temp-channel', type=int, default=3)
    parser.add_argument('--chl-scale-factor', type=float, default=10.0)
    parser.add_argument('--chl-dark-count', type=float, default=0.06)
    parser.add_argument('--ntu-scale-factor', type=float, default=5.0)
    parser.add_argument('--ntu-dark-count', type=float, default=0.06)
    parser.add_argument('--o2-salinity-setting', type=float, default=1.0)
    parser.add_argument('--chl-global-conversion', type=int, default=1)
    parser.add_argument('--sbe16-mapping', type=int, default=1)

    help = "Data reduction method, default is mean"
    parser.add_argument('--reduce-method', help=help,
                        choices=['mean', 'median'], default='mean')

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    d = {
        'median': core.REDUCE_MEDIAN,
        'mean': core.REDUCE_MEAN
    }
    with XCO2Reduce(
        args.input, args.output,
        reduce=d[args.reduce_method],
        chl_channel=args.chl_channel,
        ntu_channel=args.ntu_channel,
        o2_channel=args.o2_channel,
        o2_temp_channel=args.o2_temp_channel,
        chl_scale_factor=args.chl_scale_factor,
        chl_dark_count=args.chl_dark_count,
        ntu_scale_factor=args.ntu_scale_factor,
        ntu_dark_count=args.ntu_dark_count,
        chl_global_conversion=args.chl_global_conversion,
        o2_salinity_setting=args.o2_salinity_setting,
        sbe16_mapping=args.sbe16_mapping,
        verbosity=args.verbosity,
    ) as p:
        p.run()


def compare_with_mbl():
    """
    Entry point for comparing MBL data with APOFF XCO2
    """
    description = "Compare MBL data with APOFF, determine any offset."
    parser = argparse.ArgumentParser(description=description)

    help = 'Input merge netCDF file'
    parser.add_argument('merge_ncfile', help=help,
                        type=_validate_netcdf_argument)

    help = 'Input historical netCDF file'
    parser.add_argument('historical_ncfile', help=help,
                        type=_validate_netcdf_argument)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with CompareMBL(
        merge_ncfile=args.merge_ncfile,
        historical_ncfile=args.historical_ncfile,
        verbosity=args.verbosity
    ) as p:
        p.run()


def calculate_pre_xco2():
    """
    Entry point for converting reduced netCDF to pre xco2 (dry)
    """
    description = "Utility for calculating pre xCO2 (dry) and pCO2"
    parser = argparse.ArgumentParser(description=description)

    help = (
        'Source directory of reduced netCDF files, we write back to these '
        'files.'
    )
    parser.add_argument('input', help=help)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with PreXCO2Calc(args.input, verbosity=args.verbosity) as p:
        p.run()


def calculate_post_xco2():
    """
    Entry point for converting reduced netCDF to xco2-processed
    """
    description = "Utility for calculating post xCO2"
    parser = argparse.ArgumentParser(description=description)

    help = (
        'Source directory of reduced netCDF files, we write back to these '
        'files.'
    )
    parser.add_argument('input', help=help)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with PostXCO2Calc(args.input, verbosity=args.verbosity) as p:
        p.run()


def calculate_socat_qc():
    """
    Entry point for converting QC bit masks into SOCAT QC.
    """
    description = "Utility for converting QC bit masks into SOCAT QC."
    parser = argparse.ArgumentParser(description=description)

    help = 'Merged netCDF file'
    parser.add_argument('ncfile', help=help)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with SocatQC(ncfile=args.ncfile, verbosity=args.verbosity) as p:
        p.run()


def qc_xco2():

    parser = argparse.ArgumentParser()

    help = 'Source directory of netCDF files'
    parser.add_argument('input', help=help)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    help = (
        "Initial Span Calibration (corresponds to 'initial_span_cal' in the "
        "configuration file"
    )
    parser.add_argument('--initial-span-cal', help=help, type=float,
                        default=-1)

    help = "Range of pressure difference between APON and APOFF"
    parser.add_argument(
        '--air-diff-range', nargs=2, help=help, type=float,
        default=[None, None]
    )

    help = "Range of pressure difference between EPON and EPOFF"
    parser.add_argument(
        '--equil-diff-range', nargs=2, help=help, type=float,
        default=[None, None]
    )

    help = "Range of pressure difference between SPON and SPOFF"
    parser.add_argument(
        '--span-diff-range', nargs=2, help=help, type=float,
        default=[None, None]
    )

    help = "PPM Range of ZPON/ZPOSTCAL xco2 range around zero"
    parser.add_argument(
        '--ppm-zero-range', nargs=2, help=help, type=float,
        default=[None, None]
    )

    help = (
        "PPM Range of SPOFF xco2 range around the span calibration value.  "
        "The first value is how many PPM below the initial span calibration "
        "value, the 2nd is how many PPM above. "
        "These values must both be positive."
    )
    parser.add_argument(
        '--ppm-span-cal-range', nargs=2, help=help, type=float,
        default=[None, None]
    )

    help = "Maximum allowed value for APOFF xCO2 standard deviation"
    parser.add_argument('--max-air-xco2-std', help=help, type=float)

    help = "Maximum allowed value for EPOFF xCO2 standard deviation"
    parser.add_argument('--max-equil-xco2-std', help=help, type=float)

    help = (
        "Maximum allowed value for pressure differences between APOFF, EPOFF, "
        "and SPOFF."
    )
    parser.add_argument('--max-pressoff-diff', help=help, type=float)

    help = "Maximum allowed value for RH standard deviation"
    parser.add_argument('--max-rh-std', help=help, type=float)

    help = "Maximum allowed value for RH TEMP standard deviation"
    parser.add_argument('--max-rh-temp-std', help=help, type=float)

    help = "Maximum trend STD allowed value for APOFF/EPOFF xCO2"
    parser.add_argument('--xco2-trend-std', help=help, type=float)

    help = "1/2 window size for trend STD calculation"
    parser.add_argument('--num-points-eachside', help=help, type=float)

    help = "Run spike detection, default is yes"
    choices = ['yes', 'no']
    parser.add_argument(
        '--spike-detection', choices=choices, default='yes', help=help
    )

    args = parser.parse_args()

    spike_detection = True if args.spike_detection == 'yes' else False

    qc = QCChecker(
        args.input,
        initial_span_cal=args.initial_span_cal,
        air_diff_range_lower=args.air_diff_range[0],
        air_diff_range_higher=args.air_diff_range[1],
        equil_diff_range_lower=args.equil_diff_range[0],
        equil_diff_range_higher=args.equil_diff_range[1],
        span_diff_range_lower=args.span_diff_range[0],
        span_diff_range_higher=args.span_diff_range[1],
        max_air_xco2_std=args.max_air_xco2_std,
        max_equil_xco2_std=args.max_equil_xco2_std,
        max_pressoff_diff=args.max_pressoff_diff,
        max_rh_std=args.max_rh_std,
        max_rh_temp_std=args.max_rh_temp_std,
        num_points_eachside=args.num_points_eachside,
        ppm_below_zero=args.ppm_zero_range[0],
        ppm_above_zero=args.ppm_zero_range[1],
        ppm_below_span_cal=args.ppm_span_cal_range[0],
        ppm_above_span_cal=args.ppm_span_cal_range[1],
        spike_detection=spike_detection,
        xco2_trend_std=args.xco2_trend_std,
        verbosity=args.verbosity
    )
    qc.run()


def apply_metadata_conventions():

    parser = argparse.ArgumentParser()

    help = 'Path to final netCDF file'
    parser.add_argument('input', help=help)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with MetadataWriter(args.input, verbosity=args.verbosity) as m:
        m.run()


def merge():
    """
    Entry point for command line utility for the merge process.
    """
    description = (
        "Command line utility for merging the SPOFF, EPOFF, and APOFF "
        "variables into a single netCDF file."
    )
    parser = argparse.ArgumentParser(description=description)

    help = 'Source directory of reduced netCDF files'
    parser.add_argument('input', help=help)

    help = 'Merge netCDF file'
    parser.add_argument('output', help=help, type=_validate_netcdf_argument)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with XCO2Merge(args.input, args.output, verbosity=args.verbosity) as m:
        m.run()


def adjustments():
    """
    Entry point for command line utility for adjusting the final product for
    any LICOR pressure correction or MBL xCO2 offset.
    """
    description = (
        "Command line utility for adjusting the final netCDF file for any "
        "LICOR pressure correction or MBL xCO2 offset."
    )
    parser = argparse.ArgumentParser(description=description)

    help = 'Source directory of reduced netCDF files'
    parser.add_argument('input', help=help)

    help = 'Merge netCDF file'
    parser.add_argument('output', help=help, type=_validate_netcdf_argument)

    parser.add_argument('--pressure-correction', type=float,
                        help='Licor pressure correction', default=0.0)

    parser.add_argument('--mbl-xco2-correction',
                        help='Marine Boundary Layer correction', type=float,
                        default=0.0)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with XCO2Adjustments(
        args.input, args.output,
        pressure_correction=args.pressure_correction,
        mbl_correction=args.mbl_xco2_correction,
        verbosity=args.verbosity
    ) as m:
        m.run()


def _validate_netcdf_argument(arg):
    """
    Verify that the netCDF file argument ends with ".nc".  Otherwise there
    might be confusion as to whether a file or a directory is being applied.

    Parameters
    ----------
    arg : str
        string path for netCDF file

    Returns
    -------
    arg if passes test
    """
    if not arg.endswith(".nc"):
        msg = "The merge netCDF file argument must end with '.nc'"
        raise RuntimeError(msg)

    return arg


def nc2csv():
    """
    Entry point for the netCDF - to - CSV command line utility.
    """
    description = "Convert an xCO2 netCDF file to CSV."
    parser = argparse.ArgumentParser(description=description)

    help = 'Input netCDF file'
    parser.add_argument(
        'input_ncfile', help=help, type=_validate_netcdf_argument
    )

    help = 'Output CSV file'
    parser.add_argument(
        'output_csv', help=help, type=_validate_csv_file
    )

    args = parser.parse_args()

    with ExportToCSV(args.input_ncfile, args.output_csv) as p:
        p.run()


def trim():
    """
    Entry point for the netCDF trimmer.
    """
    description = (
        "Trim points outside of a designated start and stop.  If start and/or "
        "stop are not given, then the first and/or last points in the time "
        "series are used in their stead."
    )
    parser = argparse.ArgumentParser(description=description)

    help = 'Input netCDF files directory'
    parser.add_argument('input_ncfile', help=help)

    help = 'Output netCDF files directory'
    parser.add_argument('output_ncfile', help=help)

    help = 'Start date'
    parser.add_argument('--start', help=help, type=str)

    help = 'Stop date'
    parser.add_argument('--stop', help=help, type=str)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with TrimXCO2netCDF(
        args.input_ncfile, args.output_ncfile,
        start=args.start, stop=args.stop, verbosity=args.verbosity
    ) as p:
        p.run()


def generate_socat_xml():

    parser = argparse.ArgumentParser()

    help = 'Merge netCDF file'
    parser.add_argument('ncfile', help=help, type=_validate_netcdf_argument)

    help = 'Output SOCAT XML file'
    parser.add_argument('xmlfile', help=help, type=_validate_socat_xml_file)

    help = 'Output SOCAT CVS file'
    parser.add_argument('csvfile', help=help, type=_validate_socat_csv_file)

    parser.add_argument('--verbosity', help='Logging level',
                        choices=_LOGGING_VERBOSITY_CHOICES,
                        default='info')

    args = parser.parse_args()

    with SocatWriter(
        ncfile=args.ncfile,
        xmlfile=args.xmlfile,
        csvfile=args.csvfile,
        verbosity=args.verbosity
    ) as w:
        w.run()


def _validate_socat_xml_file(arg):
    """
    Verify that the XOCAT XML file argument ends with ".xml".

    Parameters
    ----------
    arg : str
        string path for XML file

    Returns
    -------
    arg if passes test
    """
    if not arg.endswith(".xml"):
        msg = "The SOCAT XML file argument must end with '.xml'"
        raise RuntimeError(msg)

    return arg


def _validate_socat_csv_file(arg):
    """
    Verify that the SOCAT CSV file argument ends with ".csv".

    Parameters
    ----------
    arg : str
        string path for CSV file

    Returns
    -------
    arg if passes test
    """
    return _validate_csv_file(arg, file_descriptor='SOCAT')


def _validate_csv_file(arg, file_descriptor=''):
    """
    Verify that the CSV file argument ends with ".csv".

    Parameters
    ----------
    arg : str
        string path for CSV file
    file_descriptor : str
        Might be 'SOCAT', might be the empty string.

    Returns
    -------
    arg if passes test
    """
    if not arg.endswith(".csv"):
        msg = f"The {file_descriptor} CSV file argument must end with '.csv'"
        raise RuntimeError(msg)

    return arg
