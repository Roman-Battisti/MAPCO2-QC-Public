import os

import numpy as np


SSO = 35.16504
"""
from: https://github.com/TEOS-10/python-gsw/blob/master/gsw/gibbs/constants.py
SSO is the Standard Ocean Reference Salinity (35.16504 g/kg.)
SSO is the best estimate of the Absolute Salinity of Standard Seawater
when the seawater sample has a Practical Salinity, SP, of 35
(Millero et al., 2008), and this number is a fundamental part of the
TEOS-10 definition of seawater.
References:
-----------
.. [1] IOC, SCOR and IAPSO, 2010: The international thermodynamic equation of
   seawater - 2010: Calculation and use of thermodynamic properties.
   Intergovernmental Oceanographic Commission, Manuals and Guides No. 56,
   UNESCO (English), 196 pp. See appendices A.3, A.5 and Table D.4.
.. [2] Millero, F. J., R. Feistel, D. G. Wright, and T. J. McDougall, 2008:
   The composition of Standard Seawater and the definition of the
   Reference-Composition Salinity Scale, Deep-Sea Res. I, 55, 50-72.
   See Table 4 and section 5.
"""


class Cache_npz(object):
	# from: https://github.com/TEOS-10/python-gsw/blob/7d6ebe8114c5d8b4a64268d36100a70e226afaf6/gsw/utilities/utilities.py#L161
    def __init__(self):
        self._cache = dict()
        self._default_path = os.path.join(os.path.dirname(__file__), '')  # 'data')

    def __call__(self, fname, datadir=None):
        if datadir is None:
            datadir = self._default_path
        fpath = os.path.join(datadir, fname)
        try:
            return self._cache[fpath]
        except KeyError:
            pass
        d = np.load(fpath)
        self._cache[fpath] = d
        return d

_npz_cache = Cache_npz()


def read_data(fname, datadir=None):
	# from: https://github.com/TEOS-10/python-gsw/blob/7d6ebe8114c5d8b4a64268d36100a70e226afaf6/gsw/utilities/utilities.py#L261
    """
    Read variables from a numpy '.npz' file into a minimal class providing
    attribute access.  A cache is used to avoid re-reading the same file.
    """
    return _npz_cache(fname, datadir=datadir)


class SA_table(object):
	# from: https://github.com/TEOS-10/python-gsw/blob/7d6ebe8114c5d8b4a64268d36100a70e226afaf6/gsw/gibbs/library.py#L205
    """
    TODO: Write docstring.
    """
    # Central America barrier
    x_ca = np.array([260.0, 272.59, 276.5, 278.65, 280.73, 295.217])
    y_ca = np.array([19.55, 13.97, 9.6, 8.1, 9.33, 0.0])

    def __init__(self, fname="gsw_data_v3_0.npz", max_p_fudge=10000,
                 min_frac=0):
        self.fname = fname
        self.max_p_fudge = max_p_fudge
        self.min_frac = min_frac
        data = read_data(fname)
        self.lon = data['longs_ref'].astype(np.float64)
        self.lat = data['lats_ref'].astype(np.float64)
        self.p = data['p_ref']                # Depth levels
        self.dlon = self.lon[1] - self.lon[0]
        self.dlat = self.lat[1] - self.lat[0]
        self.i_ca, self.j_ca = self.xy_to_ij(self.x_ca, self.y_ca)
        # Make the order x, y, z:
        # Start with deltaSA_ref (was delta_SA_ref in V2):
        temp = data['deltaSA_ref'].transpose((2, 1, 0)).copy()
        self.dsa_ref = np.ma.masked_invalid(temp)
        self.dsa_ref.data[self.dsa_ref.mask] = 0
        # Now SAAR_ref, which did not exist in V2:
        temp = data['SAAR_ref'].transpose((2, 1, 0)).copy()
        self.SAAR_ref = np.ma.masked_invalid(temp)
        self.SAAR_ref.data[self.SAAR_ref.mask] = 0

    def xy_to_ij(self, x, y):
        """
        Convert from lat/lon to grid index coordinates,
        without truncation or rounding.
        """
        i = (x - self.lon[0]) / self.dlon
        j = (y - self.lat[0]) / self.dlat
        return i, j

    def _central_america(self, di, dj, ii, jj, gm):
        """
        Use a line running through Central America to zero
        the goodmask for grid points in the Pacific forming
        the grid box around input locations in the Atlantic,
        and vice-versa.
        """
        ix, jy = ii[0] + di, jj[0] + dj  # Reconstruction: minor inefficiency.
        inear = ((ix >= self.i_ca[0]) & (ix <= self.i_ca[-1])
                 & (jy >= self.j_ca[-1]) & (jy <= self.j_ca[0]))
        if not inear.any():
            return gm
        inear_ind = inear.nonzero()[0]
        ix = ix[inear]
        jy = jy[inear]
        ii = ii[:, inear]
        jj = jj[:, inear]
        jy_ca = np.interp(ix, self.i_ca, self.j_ca)
        above = jy - jy_ca  # > 0 if input point is above dividing line
        # Intersections of left and right grid lines with dividing line
        jleft_ca = np.interp(ii[0], self.i_ca, self.j_ca)
        jright_ca = np.interp(ii[1], self.i_ca, self.j_ca)
        jgrid_ca = [jleft_ca, jright_ca, jright_ca, jleft_ca]
        # Zero the goodmask for grid points on opposite side of divider
        for i in range(4):
            opposite = (above * (jj[i] - jgrid_ca[i])) < 0
            gm[i, inear_ind[opposite]] = 0
        return gm

    def xy_interp(self, di, dj, ii, jj, k):
        """
        2-D interpolation, bilinear if all 4 surrounding
        grid points are present, but treating missing points
        as having the average value of the remaining grid
        points. This matches the matlab V2 behavior.
        """
        # Array of weights, CCW around the grid box
        w = np.vstack(((1 - di) * (1 - dj),  # lower left
                      di * (1 - dj),         # lower right
                      di * dj,               # upper right
                      (1 - di) * dj))        # upper left
        gm = ~self.dsa.mask[ii, jj, k]   # gm is "goodmask"
        gm = self._central_america(di, dj, ii, jj, gm)
        # Save a measure of real interpolation quality.
        frac = (w * gm).sum(axis=0)
        # Now loosen the interpolation, allowing a value to
        # be calculated on a grid point that is masked.
        # This matches the matlab gsw version 2 behavior.
        jm_partial = gm.any(axis=0) & (~(gm.all(axis=0)))
        # The weights of the unmasked points will be increased
        # by the sum of the weights of the masked points divided
        # by the number of unmasked points in the grid square.
        # This is equivalent to setting the masked data values
        # to the average of the unmasked values, and then
        # unmasking, which is the matlab v2 implementation.
        if jm_partial.any():
            w_bad = w * (~gm)
            w[:, jm_partial] += (w_bad[:, jm_partial].sum(axis=0) /
                                 gm[:, jm_partial].sum(axis=0))
        w *= gm
        wsum = w.sum(axis=0)
        valid = wsum > 0  # Only need to prevent division by zero here.
        w[:, valid] /= wsum[valid]
        w[:, ~valid] = 0
        vv = self.dsa.data[ii, jj, k]
        vv *= w
        dsa = vv.sum(axis=0)
        return dsa, frac

    def _delta_SA(self, p, lon, lat):
        """
        Table lookup engine--to be called only from SAAR or SA_ref.
        """
        p = np.ma.masked_less(p, 0)
        mask_in = np.ma.mask_or(np.ma.getmask(p), np.ma.getmask(lon))
        mask_in = np.ma.mask_or(mask_in, np.ma.getmask(lat))
        p, lon, lat = [np.ma.filled(a, 0).astype(float) for a in (p, lon, lat)]
        
        p_orig = p.copy()  # Save for comparison to clipped p.
        ix0, iy0 = self.xy_to_ij(lon, lat)
        i0raw = np.floor(ix0).astype(int)
        i0 = np.clip(i0raw, 0, len(self.lon) - 2)
        di = ix0 - i0
        j0raw = np.floor(iy0).astype(int)
        j0 = np.clip(j0raw, 0, len(self.lat) - 2)
        dj = iy0 - j0
        # Start at lower left and go CCW; match order in _xy_interp.
        ii = np.vstack((i0, i0 + 1, i0 + 1, i0))
        jj = np.vstack((j0, j0, j0 + 1, j0 + 1))
        k1 = np.searchsorted(self.p, p, side='right')
        # Clip p and k1 at max p of grid cell.
        kmax = (self.ndepth[ii, jj].max(axis=0) - 1)
        mask_out = kmax.mask
        kmax = kmax.filled(1)
        clip_p = (p >= self.p[kmax])
        p[clip_p] = self.p[kmax[clip_p]]
        k1[clip_p] = kmax[clip_p]
        k0 = k1 - 1
        dsa0, frac0 = self.xy_interp(di, dj, ii, jj, k0)
        dsa1, frac1 = self.xy_interp(di, dj, ii, jj, k1)
        dp = np.diff(self.p)
        pfrac = (p - self.p[k0]) / dp[k0]
        delta_SA = dsa0 * (1 - pfrac) + dsa1 * pfrac

        delta_SA = np.ma.array(delta_SA, copy=False)
        if mask_in is not np.ma.nomask:
            delta_SA = np.ma.array(delta_SA, mask=mask_in, copy=False)
        return delta_SA

    def SAAR(self, p, lon, lat):
        """
        Table lookup of salinity anomaly ratio, given pressure, lon, and lat.
        """
        self.dsa = self.SAAR_ref
        # In V2,
        # ndepth from the file disagrees with the unmasked count from
        # SAAR_ref in a few places; this should be fixed in the
        # file, but for now we will simply calculate ndepth directly from
        # SAAR_ref.
        # TODO: check to see whether this discrepancy is also found in V3.
        # TODO: check: do we even need to calculate ndepth? It doesn't
        #       appear to be used for anything.
        # self.ndepth = np.ma.masked_invalid(data.ndepth_ref.T).astype(np.int8)
        ndepth = self.dsa.count(axis=-1)
        self.ndepth = np.ma.masked_equal(ndepth, 0)
        return self._delta_SA(p, lon, lat)


def SAAR(p, lon, lat):
	# from: https://github.com/TEOS-10/python-gsw/blob/7d6ebe8114c5d8b4a64268d36100a70e226afaf6/gsw/gibbs/library.py#L375
    """
    Absolute Salinity Anomaly Ratio (excluding the Baltic Sea).
    Calculates the Absolute Salinity Anomaly Ratio, SAAR, in the open ocean
    by spatially interpolating the global reference data set of SAAR to the
    location of the seawater sample.
    This function uses version 3.0 of the SAAR look up table.
    Parameters
    ----------
    p : array_like
        pressure [dbar]
    lon : array_like
          decimal degrees east (will be treated modulo 360)
    lat : array_like
          decimal degrees (+ve N, -ve S) [-90..+90]
    Returns
    -------
    SAAR : array
           Absolute Salinity Anomaly Ratio [unitless]
    in_ocean : boolean array
    Notes
    -----
    The Absolute Salinity Anomaly Ratio in the Baltic Sea is evaluated
    separately, since it is a function of Practical Salinity, not of space.
    The present function returns a SAAR of zero for data in the Baltic Sea.
    The correct way of calculating Absolute Salinity in the Baltic Sea is by
    calling SA_from_SP.
    The in_ocean flag is only set when the observation is well and truly on dry
    land; often the warning flag is not set until one is several hundred
    kilometers inland from the coast.
    The algorithm is taken from the matlab implementation of the references,
    but the numpy implementation here differs substantially from the
    matlab implementation.
    References
    ----------
    .. [1] IOC, SCOR and IAPSO, 2010: The international thermodynamic equation
       of seawater - 2010: Calculation and use of thermodynamic properties.
       Intergovernmental Oceanographic Commission, Manuals and Guides No. 56,
       UNESCO (English), 196 pp.
    .. [2] McDougall, T.J., D.R. Jackett and F.J. Millero, 2010: An algorithm
       for estimating Absolute Salinity in the global ocean.  Submitted to
       Ocean Science. A preliminary version is available at Ocean Sci.
       Discuss., 6, 215-242.
       http://www.ocean-sci-discuss.net/6/215/2009/osd-6-215-2009-print.pdf
    """

    saar = SA_table().SAAR(p, lon, lat)
    return saar, ~saar.mask


def in_Baltic(lon, lat):
	# from: https://github.com/TEOS-10/python-gsw/blob/7d6ebe8114c5d8b4a64268d36100a70e226afaf6/gsw/gibbs/library.py#L1485
    """
    Check if positions are in the Baltic Sea
    Parameters
    ----------
    lon, lat : array_like or masked arrays
    Returns
    -------
    in_Baltic : boolean array (at least 1D)
                True for points in the Baltic Sea
                False for points outside, masked or NaN
    """

    lon, lat = np.atleast_1d(lon, lat)
    # Polygon bounding the Baltic, (xb, yb)
    # Effective boundary is the intersection of this polygon
    # with rectangle defined by xmin, xmax, ymin, ymax

    # start with southwestern point and go round cyclonically
    xb = np.array([12.6, 45.0, 26.0,  7.0, 12.6])
    yb = np.array([50.0, 50.0, 69.0, 59.0, 50.0])
    # Enclosing rectangle
    # xmin, xmax = xb.min(), xb.max()
    # ymin, ymax = yb.min(), yb.max()
    xmin, xmax = 7.0, 32.0
    ymin, ymax = 52.0, 67.0
    # First check if outside the rectangle
    in_rectangle = ((xmin < lon) & (lon < xmax) &
                    (ymin < lat) & (lat < ymax))
    # Masked values are also considered outside the rectangle
    if np.ma.is_masked(in_rectangle):
        in_rectangle = in_rectangle.data & ~in_rectangle.mask
    # Closer check for points in the rectangle
    if np.any(in_rectangle):
        lon, lat = np.broadcast_arrays(lon, lat, subok=True)
        in_baltic = np.zeros(lon.shape, dtype='bool')
        lon1 = lon[in_rectangle]
        lat1 = lat[in_rectangle]
        # There are general ways of testing for point in polygon
        # This works for this special configuration of points
        xx_right = np.interp(lat1, yb[1:3], xb[1:3])
        xx_left = np.interp(lat1, yb[-1:1:-1], xb[-1:1:-1])
        in_baltic[in_rectangle] = (xx_left <= lon1) & (lon1 <= xx_right)
        return in_baltic
    else:  # Nothing inside the rectangle, return the False array.
        return in_rectangle



def SA_from_SP_Baltic(SP, lon, lat):
	# from: https://github.com/TEOS-10/python-gsw/blob/7d6ebe8114c5d8b4a64268d36100a70e226afaf6/gsw/gibbs/library.py#L375
    """
    Computes absolute salinity from practical in the Baltic Sea.
    Parameters
    ----------
    SP : array_like or masked array
        Practical salinity (PSS-78)
    lon, lat : array_like or masked arrays
               geographical position
    Returns
    -------
    SA : masked array, at least 1D
         Absolute salinity   [g/kg]
         masked where inputs are masked or position outside the Baltic
    """

    # Handle masked array input
    input_mask = False
    if np.ma.is_masked(SP):
        input_mask = input_mask | SP.mask
    if np.ma.is_masked(lon):
        input_mask = input_mask | lon.mask
    if np.ma.is_masked(lat):
        input_mask = input_mask | lat.mask
    SP, lon, lat = list(map(np.atleast_1d, (SP, lon, lat)))
    SP, lon, lat = np.broadcast_arrays(SP, lon, lat)
    inds_baltic = in_Baltic(lon, lat)
    # SA_baltic = np.ma.masked_all(SP.shape, dtype=np.float)
    all_nans = np.nan + np.zeros_like(SP)
    SA_baltic = np.ma.MaskedArray(all_nans, mask=~inds_baltic)
    if np.any(inds_baltic):
        SA_baltic[inds_baltic] = (((SSO - 0.087) / 35) *
                                  SP[inds_baltic] + 0.087)
    SA_baltic.mask = SA_baltic.mask | input_mask | np.isnan(SP)
    return SA_baltic



# @match_args_return
def SA_from_SP(SP, p, lon, lat):
	# from: https://github.com/TEOS-10/python-gsw/blob/master/gsw/gibbs/conversions.py
    """Calculates Absolute Salinity from Practical Salinity.
    Parameters
    ----------
    SP : array_like
         salinity (PSS-78) [unitless]
    p : array_like
        pressure [dbar]
    lon : array_like
          decimal degrees east [0..+360] or [-180..+180]
    lat : array_like
          decimal degrees (+ve N, -ve S) [-90..+90]
    Returns
    -------
    SA : masked array
         Absolute salinity [g kg :sup:`-1`]
    Notes
    -----
    The mask is only set when the observation is well and truly on dry
    land; often the warning flag is not set until one is several hundred
    kilometers inland from the coast.
    Since SP is non-negative by definition, this function changes any negative
    input values of SP to be zero.
    Examples
    --------
    >>> import gsw
    >>> SP = [34.5487, 34.7275, 34.8605, 34.6810, 34.5680, 34.5600]
    >>> p = [10, 50, 125, 250, 600, 1000]
    >>> lon = 188
    >>> lat = 4
    >>> gsw.SA_from_SP(SP, p, lon, lat)
    array([ 34.71177834,  34.89152262,  35.02554486,  34.84722903,
            34.73662847,  34.73236307])
    References
    ----------
    .. [1] IOC, SCOR and IAPSO, 2010: The international thermodynamic equation
       of seawater - 2010: Calculation and use of thermodynamic properties.
       Intergovernmental Oceanographic Commission, Manuals and Guides No. 56,
       UNESCO (English), 196 pp. See section 2.5 and appendices A.4 and A.5.
    .. [2] McDougall, T.J., D.R. Jackett and F.J. Millero, 2010: An algorithm
       for estimating Absolute Salinity in the global ocean. Submitted to Ocean
       Science. A preliminary version is available at Ocean Sci. Discuss.,
       6, 215-242.
       http://www.ocean-sci-discuss.net/6/215/2009/osd-6-215-2009-print.pdf
    """
    
    lon, lat, p, SP = np.broadcast_arrays(lon, lat, p, SP)
    SP = np.maximum(SP, 0)
    cond1 = ((p < 100) & (SP > 120))
    cond2 = ((p >= 100) & (SP > 42))
    SP[cond1] = float('nan')
    SP[cond2] = float('nan')
    lon = lon % 360

    SA = (SSO / 35) * SP * (1 + SAAR(p, lon, lat)[0])
    SA_baltic = SA_from_SP_Baltic(SP, lon, lat)

    # The following function (SAAR) finds SAAR in the non-Baltic parts of
    # the world ocean.  (Actually, this SAAR look-up table returns values
    # of zero in the Baltic Sea since SAAR in the Baltic is a function of SP,
    # not space.
    if SA_baltic is not None:
        SA[~SA_baltic.mask] = SA_baltic[~SA_baltic.mask]

    return SA
