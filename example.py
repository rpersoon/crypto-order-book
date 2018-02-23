# Copyright (c) 2017 - 2018 Ricardo Persoon
# Distributed under the MIT software license, see the accompanying file LICENSE


import time

from crypto_order_book import PoloniexOrderBook, OrderBookError, OrderBookOutOfSync, order_book_helper


# Define the markets
markets = [
    {
        'base_currency': 'eth',
        'quote_currency': 'btc',
    },
    {
         'base_currency': 'ltc',
         'quote_currency': 'btc',
    }
]

# Initialise the order book
order_book = PoloniexOrderBook(markets)
order_book.start()

# Wait until it completes initialisation
order_book.complete_initialisation()

# Print the order book every 3 seconds for an hour
for _ in range(0, 1200):
    try:
        # Print the first 5 items on the ask and bid side of the order book in a formatted way using the helper
        order_book_helper.print_order_book(order_book, 'eth', 'btc', 5)

        # Retrieve the first 10 items on the ask side of the book
        # print(order_book.get_top_asks('eth', 'btc', 10))

        # Retrieve the first 10 items on the ask side of the book
        # print(order_book.get_top_bids('eth', 'btc', 10))

        # Get the middle between the highest bid and lowest ask in the book
        # print(order_book.get_middle('eth', 'btc'))

    except OrderBookOutOfSync as e:
        print("Order book out of sync: %s" % e)

    except OrderBookError as e:
        print("Order book failed: %s" % e)
        exit(-1)

    time.sleep(3)

# Stop the order book and close websocket connections
order_book.stop()
