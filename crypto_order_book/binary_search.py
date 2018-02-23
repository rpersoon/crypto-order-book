# Copyright (c) 2017 - 2018 Ricardo Persoon
# Distributed under the MIT software license, see the accompanying file LICENSE


def get_index(find_rate, search_list, reverse_sort=False):
    """
    Find the index of a timestamp in an order book list

    :param find_rate: desired time
    :param search_list: search list
    :param reverse_sort: whether the order book is sorted in reversed order (highest first)
    :return: index if found or false if not found
    """

    index_left = 0
    index_right = len(search_list) - 1

    while index_left <= index_right:

        index_middle = int((index_left + index_right) / 2)
        value = search_list[index_middle][0]

        if value == find_rate:
            return index_middle

        if reverse_sort:
            if find_rate > value:
                index_right = index_middle - 1
            else:
                index_left = index_middle + 1

        else:
            if find_rate < value:
                index_right = index_middle - 1
            else:
                index_left = index_middle + 1

    return False
