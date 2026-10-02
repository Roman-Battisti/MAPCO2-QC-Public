import numpy as np

def find_closest(search_array, pivot):
    """Finds the closest value to pivot in the search array. Pivot and values must support subtraction, absolute value,
    and comparison.

    Parameters
    -------------
    search_array: numpy sorted array
    pivot: value to search for. Must be of same type as values in search array

    output
    -------------
    closest value from search array
    """
    assert type(search_array) == np.ndarray
    
    index = np.searchsorted(search_array, pivot, side='left')
    if index != 0:
        values = search_array[index-1:index+1]
        distances = abs(values - pivot) # 2 values
        min_index = np.argmin(distances) # return index of smallest distance
        return values[min_index]
    else:
        return search_array[index]

    
def closest_within_distance(search_array, pivot, max_dist):
    """Finds the closest value to pivot in the search array. Pivot and values must support subtraction, absolute value,
    and comparison.

    Parameters
    -------------
    search_array: numpy sorted array
    pivot: value to search for. Must be of same type as values in search array
    max_dist: maximum allowable distance. Must be of appropriate type to work with the search array and pivot

    output
    -------------
    closest value from search array if within max_dist, else returns None
    """
    nearest_value = find_closest(search_array, pivot)
    return nearest_value if abs(nearest_value - pivot) <= max_dist else None


def align_arrays(search_array, pivot_array, max_dist=None):
    """Finds the closest value in search array for each pivot in the pivot array. Pivots and values must support
    subtraction, absolute value, and comparison.

    Parameters
    -------------
    search_array: numpy array
    pivot_array: array of pivots to search for. Pivots must be of same type as values in search array
    max_dist: maximum allowable distance. Must be of appropriate type to work with the search array values and pivots

    output
    -------------
    array of closest values from search_array
    """
    assert type(pivot_array) == np.ndarray
    
    output = [None] * pivot_array.shape[0]
    search_array = np.sort(search_array, kind='mergesort')
    for i, p in enumerate(pivot_array):
        output[i] = find_closest(search_array, p) if max_dist is None else closest_within_distance(search_array, p, max_dist)
    return np.array(output)