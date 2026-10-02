# standard packages
from copy import copy
import math

# 3rd party packages
import numpy as np
from scipy import stats


class OutlierDetector:
    """Detects outliers using provided statistical methods
        Parameters:
        ------------
        generator_factory: (object) produces a generator that partitions the data into subsections
            according to the generator's business rules (ex. using a range or number of frames)
        outlier_algorithm: (object) contains the method to determine outliers (ex. interquartile range, z-score)
    """

    def __init__(self, generator_factory, outlier_algorithm):
        self._generator_factory = generator_factory
        self._outlier_algorithm = outlier_algorithm

    def outliers(self, data):
        outliers = self._outlier_algorithm.outliers(data, self._generator_factory)
        return outliers


class byFrameGeneratorFactory:
    """Generator Factory.
       For each datum, generator yields a subset of data that are within 'frame' positions away from the datum.
    """

    def __init__(self, frame=8):
        self._frame = math.ceil(frame)

    def generator(self, data):
        data = copy(data)
        for idx in range(data.shape[0]):
            if self._frame <= idx < (data.shape[0] - self._frame):
                output = data[(idx - self._frame):(idx + self._frame + 1), ]
            elif idx < self._frame:
                output = data[:(2 * self._frame + 1), ]
            else:
                output = data[(-2 * self._frame - 1):, ]
            yield output

    def span(self):
        return self._frame


class InterquartileVarianceAlgorithm:
    """ Returns truth matrix of outliers using variance estimated from interquartile range statistics to determine
        outliers. Estimated variance is used with median of data to determine

        Parameters
        ------------
        k_factor: (float/int) multiplication factor used to set range for outlier detection, generally agreed to be 1.5
		min_num_points: (int) minimum number of data necessary to peform statistics. If this number is larger than the size
						of the frame, the frame size will be used.
    """

    def __init__(self, stdev_limit=5, min_num_points=20):
        self._stdev_limit = stdev_limit
        self._min_num_points = min_num_points  # minimum number of data necessary for statistics

    def outliers(self, data, generator_factory):
        span = generator_factory.span()  # position of the center point yielded by the generator
        if len(data.shape) == 1:
            data = np.reshape(np.array(data), (data.shape[0], 1))
        outliers = np.zeros(data.shape)
        generator = generator_factory.generator(data)

        min_num_points = min(2 * span + 1, self._min_num_points)  # minimum number of non-NaN data to do statistics
        for count, frame in enumerate(generator):
            # find interquartile statistics then decide outliers
            q25 = [
                   np.nanpercentile(frame[:, column].astype(float), 25)
                   if sum(~np.isnan(frame[:, column].astype(float))) >= min_num_points
                   else float('nan') for column in range(frame.shape[1])
                  ]
            q75 = [
                   np.nanpercentile(frame[:, column].astype(float), 75)
                   if sum(~np.isnan(frame[:, column].astype(float))) >= min_num_points
                   else float('nan') for column in range(frame.shape[1])
                  ]
            iqr_stdev = [
                    (abs(q75[i] - q25[i]) / 1.35)
                   if int(sum(np.isnan([q75[i], q25[i]]))) == 0 else float('nan')
                   for i in range(frame.shape[1])
                  ]
            cut_off = [i * self._stdev_limit for i in iqr_stdev]
            row_outliers = [
                            False if math.isnan(cut_off[i]) | math.isnan(data[count, i]) |
                            ((np.nanmedian(frame[:, i]) - cut_off[i]) < data[count, i] < (np.nanmedian(frame[:, i]) + cut_off[i]))
                            else True for i in range(frame.shape[1])
                           ]
            outliers[count] = row_outliers
        return outliers.astype(bool)
