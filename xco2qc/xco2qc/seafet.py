# standard library imports
import datetime as dt
import io
import re
import warnings

# 3rd party library imports
import pandas as pd

# local imports
from xco2qc.core import seafet


def process_cycle(text):
    """
    Process a Seafet section of a mapco2 file.

    Parameters
    ----------
    text : str
        Text from mapco2 file, looks something like what lies between the ---
        delimeters.

        ---
         Seafet D sSATPHA0217,2017283,21.1041069,7.86388,...
        SATPHA0217,2017283,21.1043853,7.86295,7.50876,...
         .
         .
        SATPHA0217,2017283,21.1054954,7.86334,7.50859,...
        End Seafet Data
        ---

    Returns
    -------
    pandas.Dataframe or None

    References
    ----------
    User's Manual, SeaFET pH Sensor
    """

    # locate the extents of the 'regular' seafet data, restrict the seafet
    # section to the extents, and create a file-like object from the text (
    # suitable for pandas to easily read)
    #
    # There are a few different cases to handle here.
    #
    #   1.  "Seafet D"
    #   2.  "Seafet D s"
    #   3.  "Seafet D/rs"
    #
    # Number 2 seems to be the case for good data.
    pattern = r'Seafet\sD((\ss)|\/rs)?'
    m1 = re.search(pattern, text)
    if m1 is None:
        return None
    start = m1.span()[1]

    # Sometimes there is an s just in front of End, sometimes not.
    m2 = re.search('s?End Seafet Data', text)
    if m2 is None:
        return None
    stop = m2.span()[0]

    if start == stop:
        # the data string is empty
        return None

    s = io.StringIO(text[start:stop])

    # try to determine from the first line if we have good data or not
    # if it's all zeros and is space-delimited, then it's uninitialized
    first_line = s.readline()
    try:
        datums = [float(x) for x in first_line.split()]
        if len(datums) == 11 and all(x == 0 for x in datums):
            # don't return in the try clause
            pass
    except ValueError:
        # it is NOT uninitialized, this is what we want.  reset the file
        # object and continue on
        #
        # It looks something like
        #
        # SATPHA0345,2018318,9.5865612,8.03040,8.08025,16.3681,nan,nan,nan,nan,
        # 0.97830623,-0.93059301,0.96968263,12.231,30,255.0,4.922,12.152,6.158,
        # 5.816,611,110,0.00000000,0x0080,102
        s.seek(0)
    else:
        # it IS uninitialized, the data is unusable
        # It probably looks something like
        #
        # 0.00000 0.00000 00.0000 0.00000000  0.00000000 0.00000000 00.000
        # 00.000 00.0 0.000 0.000\r
        return None

    df = read_seafet(s)
    if df is None:
        return None

    # convert the date and time into a single column, and then we can drop
    # the date and time columns
    df['seafet_time'] = df['date'] + df['time']

    df = df.drop(['date', 'time'], axis='columns')

    # 'unknown' is from the VBA variant.  Since we don't know what it is, we
    # will drop it as well.
    if 'unknown' in df.columns:
        df = df.drop(['unknown'], axis='columns')

    # rename ph_ext to just ph
    df = df.rename(columns={'ph_ext': 'ph'})

    return df


def read_seafet(s):
    """
    Read in the dataframe from the file-like object.  There are 3 possible
    data formats.
    """

    long_frame = False
    short_frame = False
    vba_frame = False

    # read the data
    converters = {
        'date': yyyyddd,
        'time': lambda x: dt.timedelta(hours=float(x)),
        'status': lambda x: int(x, 16)
    }

    s.seek(0)
    try:
        df = pd.read_csv(
            s, names=seafet.LONG_FRAME_COLUMNS, converters=converters
        )
    except ValueError:
        pass
    else:
        long_frame = True

    if not long_frame:
        s.seek(0)
        try:
            df = pd.read_csv(
                s, names=seafet.SHORT_FRAME_COLUMNS, converters=converters
            )
        except ValueError:
            pass
        else:
            short_frame = True

    if not long_frame and not short_frame:
        s.seek(0)
        try:
            df = pd.read_csv(
                s, names=seafet.VBA_FRAME_COLUMNS, converters=converters
            )
            pass
        except ValueError:
            pass
        else:
            vba_frame = True

    if not long_frame and not short_frame and not vba_frame:
        msg = (
            'Unable to process seafet section, format is neither long '
            'frame nor short frame nor the undocumented VBA frame.'
        )
        warnings.warn(msg)
        return None

    return df


def yyyyddd(x):
    """
    Custom converter for creating a date object out of a string like 1983281
    """
    year = int(x[:4])
    day_of_year = int(x[4:])
    date = dt.datetime(year, 1, 1)
    date = date + dt.timedelta(days=day_of_year - 1)
    return date
