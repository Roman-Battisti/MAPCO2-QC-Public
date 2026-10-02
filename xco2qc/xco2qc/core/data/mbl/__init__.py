# standard library imports
import calendar
import datetime as dt
import functools
import gzip
import importlib.resources as ir
import io

# 3rd party library imports
import dateutil.parser
import numpy as np
import pandas as pd
import requests

# local imports
from . import data


_timestamp = None


def get_timestamp():
    """
    Returns
    -------
    datetime.datetime
        Timestamp of file creation.
    """
    return _timestamp


def read_mbl(retrieve_remote):
    """
    Parameters
    ----------
    retrieve_remote : bool
        If true, attempt to retrieve the newest version of the MBL data from
        the ESRL website.  Otherwise use the stored version.

    Returns
    ------
    pandas.DataFrame of the NOAA Greenhouse Gas Marine Boundary Layer
    Reference
    """
    if retrieve_remote:
        df = retrieve_remote_mbl_data()
    else:
        df = retrieve_internal_data()

    # the date column is currently a fractional year, it needs to be turned
    # into a full-fledged pandas DatetimeIndex
    df.index = assemble_date(df[0])

    return df


def retrieve_internal_data():
    """
    Read the data from the internal copy.
    """

    with ir.as_file(ir.files(data).joinpath('Latest_MBL.txt.gz')) as p:
        mbl_textfile = str(p)

    with gzip.open(mbl_textfile, mode='rt') as f:
        read_header(f)
        df = pd.read_csv(f, header=None, sep=r'\s+')

    return df


def retrieve_remote_mbl_data():
    """
    Retrieve the most recent data from ESRL.
    """

    url = 'https://esrl.noaa.gov/gmd/ccgg/mbl/ghg.php'

    params = {
        'hidden': True,
        'param': 'CO2',
        'reference_type': 'surface',
        'reference': [-90, 90],
        'startyear': 1979,
        'startmonth': 1,
        'endyear': dt.datetime.now().year,  # use the current year
        'endmonth': 12,
        'output': 'text'
    }
    r = requests.get(url, params=params)
    r.raise_for_status()

    sio = io.StringIO(r.text)
    read_header(sio)
    df = pd.read_csv(sio, header=None, sep=r'\s+')
    with ir.as_file(ir.files(data).joinpath('Latest_MBL.txt.gz')) as p:
        mbl_textfile = str(p)

    with gzip.open(mbl_textfile, mode='wt') as f:
        f.write(r.text)

    return df


def read_header(f):
    """
    Read through the header to position ourselves at the start of the actual
    data.  The File Creation date needs to be saved, though.
    """

    # read the header
    header_lines = []
    while True:
        line_start = f.tell()
        line = f.readline()

        if line.startswith('# File Creation'):
            global _timestamp
            _timestamp = dateutil.parser.parse(line.split()[3])

        if line.startswith('#'):
            header_lines.append(line)
        else:
            # We'v read the entire header.  Seek back to the start of
            # the current line so that pandas can process the rest in a
            # single step.
            f.seek(line_start)
            break

    header = '\n'.join(header_lines)

    return header


def assemble_date(ts):
    """
    Transform a fractional year date format into something that we can
    work with.

    Parameters
    ----------
    ts : pandas.Series
        each value is a year fraction,
        i.e. 1979.020833 = 1979-01-08 14:29:49

    Returns
    -------
    pandas.DatetimeIndex of the fully-formed dates
    """
    # break the decimal year down into constituent parts
    year = np.floor(ts)
    year_fraction = ts - year

    # must handle leap years in order to convert into day-of-year
    leap_year = year.apply(calendar.isleap)
    days_in_year = pd.Series(np.full((len(year),), 365))
    days_in_year[leap_year] = 366

    df = pd.DataFrame({
        'year': year,
        'dayofyear': days_in_year * year_fraction
    })

    # these are dummy columns, just need them to construct the first
    # day of the year
    df['month'] = 1
    df['day'] = 1

    df['startofyear'] = pd.to_datetime(df[['year', 'month', 'day']])

    # add the year day to the start of the year to get the complete date
    fcn = functools.partial(pd.Timedelta, unit='days')
    df['time'] = df['startofyear'] + df['dayofyear'].apply(fcn)

    return df.set_index('time').index
