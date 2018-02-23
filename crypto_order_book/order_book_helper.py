# Copyright (c) 2017 - 2018 Ricardo Persoon
# Distributed under the MIT software license, see the accompanying file LICENSE


def print_order_book(order_book, base_currency, quote_currency, count):
    """
    Prints formatted order book data to standard output. Any order book exceptions are passed.

    :param order_book: instance of an order book
    :param base_currency: market base currency
    :param quote_currency: market quote currency
    :param count: number of rows to print
    """

    # Get the data
    asks = order_book.get_top_asks(base_currency, quote_currency, count)
    bids = order_book.get_top_bids(base_currency, quote_currency, count)

    if len(asks) != count or len(bids) != count:
        print("Not enough order book data available for printing")
        return

    print('============================================================================')
    print("Price ask        Amount              Price bid        Amount")
    print('============================================================================')

    for i in range(0, count):

        price_ask = "{0:.8f}".format(asks[i][0])
        for j in range(0, 14 - len(price_ask)):
            print(' ', end='')
        print('%s   ' % price_ask, end='')

        amount_ask = "{0:.8f}".format(asks[i][1])
        for j in range(0, 14 - len(amount_ask)):
            print(' ', end='')
        print('%s      ' % amount_ask, end='')

        price_bid = "{0:.8f}".format(bids[i][0])
        for j in range(0, 14 - len(price_bid)):
            print(' ', end='')
        print('%s   ' % price_bid, end='')

        amount_bid = "{0:.8f}".format(bids[i][1])
        for j in range(0, 14 - len(amount_bid)):
            print(' ', end='')
        print('%s      ' % amount_bid, end='')
        print()
