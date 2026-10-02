# standard library imports
import binascii
import datetime as dt
import struct

# 3rd party libraries
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

# local imports
from xco2qc import core


def process_sami_strings(sami_strings, salinity=None):
    """
    Process the sami hex strings into data

    Parameters
    ----------
    sami_strings : array-like
        timeseries of raw sami hex strings
    salinity : array-like or None
        timeseries of salinity

    Returns
    -------
    pandas dataframe of measurements
    """
    if salinity is None:
        # the default position of the original code was to assume a salinity
        # value of 35
        salinity = pd.Series([35] * len(sami_strings))

    # because the sami hex strings can be of differing lengths, we cannot
    # easily vectorize, have to go thru them one at a time
    measurements = []
    for sami_string, salinity_value in zip(sami_strings, salinity):

        try:
            measurement = process_sami_string(sami_string, salinity_value)
        except (ValueError, IndexError):
            # most likely a corrupt sami string
            measurement = {}

        measurements.append(measurement)

    df = pd.DataFrame(measurements)

    return df


def process_sami_string(samistr, salinity=35):
    """
    Process a sami hex string into temperature, pH, slope, and r**2

    Parameters
    ----------
    samistr : str
        a single SAMI string, may be 455 or 465 chars in length
    salinity : numeric, optional
        the algorithms default to 35, but recommend using seabird CTD if
        available

    Returns
    -------
    Dictionary of individual calculated values, namely temperature, ph,
    slope, r2
    """
    _EA434 = 18103
    _EB434 = 2296
    _EA578 = 97.75
    _EB578 = 40427

    # This seems to weight the temperature calculation towards the final
    # thermistor reading.
    numph = 5

    measurements = {
        'temperature': core.DEFAULT_FILLVALUE,
        'slope': core.DEFAULT_FILLVALUE,
        'r2': core.DEFAULT_FILLVALUE,
        'ph': core.DEFAULT_FILLVALUE,
        'ph_qc': core.quality.GOOD,
        'battery': core.DEFAULT_FILLVALUE,
        'sami_time': pd.NaT
    }

    # if the hex string was all zeros, then its all unitialized.  we'll say
    # that it is missing
    if samistr == '0' * len(samistr):
        measurements['ph_qc'] = core.quality.MISSING_DATA
        return measurements

    # record_length = int(samistr[3:5], 16)

    # 0A = 10 is a pH record
    # record_type = int(samistr[5:7], 16)

    # time
    seconds = int(samistr[7:15], 16)
    datetime = (
        dt.datetime(1904, 1, 1, tzinfo=dt.timezone.utc)
        + dt.timedelta(seconds=seconds)
    )
    measurements['sami_time'] = datetime

    # starting thermistor and ending thermistor
    # temperatures at beginning and end of measurements
    temp1 = int(samistr[15:19], 16)
    temp2 = int(samistr[459:463], 16)

    # chksum = int(samistr[-2:], 16)

    # battery voltage
    measurements['battery'] = 0.00366 * int(samistr[455:459], 16)

    # thermistor calculations
    rt1 = (temp1 / (4096 - temp1)) * 17400

    invT1 = 0.0010183 + 0.000241 * np.log(rt1) + 1.5E-07 * np.log(rt1) ** 3

    tempK1 = 1 / invT1
    tempC1 = tempK1 - 273.15

    rt2 = (temp2 / (4096 - temp2)) * 17400
    invT2 = 0.0010183 + 0.000241 * np.log(rt2) + 1.5E-07 * np.log(rt2) ** 3
    tempK2 = 1 / invT2
    tempC2 = tempK2 - 273.15
    tAvgC = (tempC1 + (numph - 1) * tempC2) / numph

    measurements['temperature'] = tAvgC

    if np.isnan(salinity) or salinity == 0:
        measurements['ph_qc'] = core.quality.BAD_SSTC
        return measurements

    # original pKa was from Clayton/Byrne 1993
    # This equation from Oz code, 2020!
    pKa = (
        -241.462
        + 0.6375
        + 7085.72 / tempK2
        + 43.8332 * np.log(tempK2)
        - 0.0806406 * tempK2
        - 0.3238 * salinity ** 0.5
        + 0.0807 * salinity
        - 0.01157 * salinity ** 1.5
        + 0.000694 * salinity ** 2
    )

    # Molar absorptivities
    ea434 = _EA434 + 20.1620 * (25 - tAvgC)
    ea578 = _EA578
    eb434 = _EB434 - 6.3863 * (25 - tAvgC)
    eb578 = _EB578 + 66.8080 * (25 - tAvgC)
    e1 = ea578 / ea434
    e2 = eb578 / ea434
    e3 = eb434 / ea434

    # raw blank measurements
    ref434a = int(samistr[19:23], 16)
    sig434a = int(samistr[23:27], 16)
    ref578a = int(samistr[27:31], 16)
    sig578a = int(samistr[31:35], 16)

    ref434b = int(samistr[35:39], 16)
    sig434b = int(samistr[39:43], 16)
    ref578b = int(samistr[43:47], 16)
    sig578b = int(samistr[47:51], 16)

    ref434c = int(samistr[51:55], 16)
    sig434c = int(samistr[55:59], 16)
    ref578c = int(samistr[59:63], 16)
    sig578c = int(samistr[63:67], 16)

    ref434d = int(samistr[67:71], 16)
    sig434d = int(samistr[71:75], 16)
    ref578d = int(samistr[75:79], 16)
    sig578d = int(samistr[79:83], 16)

    if (
        ref434a == 0 or ref434b == 0
        or ref434c == 0 or ref434d == 0
        or ref578a == 0 or ref578b == 0
        or ref578c == 0 or ref578d == 0
    ):
        measurements['ph_qc'] = core.quality.INVALID_434_578_MEASUREMENT
        return measurements

    # blank absorbances
    blank434A = sig434a / ref434a
    blank578A = sig578a / ref578a
    blank434B = sig434b / ref434b
    blank578B = sig578b / ref578b
    blank434C = sig434c / ref434c
    blank578C = sig578c / ref578c
    blank434D = sig434d / ref434d
    blank578D = sig578d / ref578d

    # average blank absorbance
    blank434 = (blank434A + blank434B + blank434C + blank434D) / 4
    blank578 = (blank578A + blank578B + blank578C + blank578D) / 4

    with np.errstate(divide='ignore', invalid='ignore'):
        # suppress division by zero messages
        a434blank = -np.log10(blank434)
        a578blank = -np.log10(blank578)

    if np.isinf(a434blank) or np.isinf(a578blank):
        measurements['ph_qc'] = core.quality.INVALID_434_578_MEASUREMENT
        return measurements

    nrows = 22
    packed_data = binascii.unhexlify(samistr[83:435])
    data = struct.unpack('>' + 'H' * nrows * 4, packed_data)
    data = np.array(data, dtype=np.uint16).reshape((nrows, 4))

    raw_df = pd.DataFrame(
        data, columns=['ref434', 'i434', 'ref578', 'i578']
    )

    with np.errstate(divide='ignore', invalid='ignore'):
        a434 = -np.log10(raw_df['i434'] / raw_df['ref434'])
        a578 = -np.log10(raw_df['i578'] / raw_df['ref578'])

    abs434 = a434 - a434blank
    abs578 = a578 - a578blank

    R = abs578 / abs434
    v1 = R - e1
    v2 = e2 - R * e3

    HI = (
        ((abs434 * eb578) - (abs578 * eb434))
        / ((ea434 * eb578) - (eb434 * ea578))
    )
    i = (
        ((abs578 * ea434) - (abs434 * ea578))
        / ((ea434 * eb578) - (eb434 * ea578))
    )

    indConc = HI + i

    with np.errstate(divide='ignore', invalid='ignore'):
        pointpH = pKa + np.log10(v1 / v2)

    df = pd.DataFrame({'indconc': indConc, 'pointpH': pointpH})

    # restrict the observations we actually use
    maxobs = df[df.indconc == df.indconc.max()]
    if maxobs.index[0] < 12:
        first_pt = maxobs.index[0] + 1
    else:
        first_pt = 6

    df = df.iloc[first_pt:, :]

    # filter out points outside the accepted region
    df = df.query(
        'indconc >= 0.00001 and indconc <= 0.00008 and not pointpH.isnull()',
        engine='python'
    )

    if len(df) < 2:
        # must have at least two measurements to do the regression
        measurements['ph_qc'] = core.quality.TOO_FEW_MEASUREMENTS
        return measurements

    model = smf.ols('pointpH ~ indconc', data=df).fit()

    xbar = df.mean()['indconc']
    ybar = df.mean()['pointpH']
    slope = model.params['indconc']
    ph = ybar - (slope * xbar)

    measurements['slope'] = slope
    measurements['ph'] = ph
    measurements['r2'] = model.rsquared

    return measurements
