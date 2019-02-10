Cryptocurrency websocket order book - Bitfinex and Poloniex implementation
==========================================================================

A robust, high performance and extendable cryptocurrency order book implementation in Python 3 for Bitfinex and Poloniex. The module streams live data from websocket feeds and provides access to the order books through several methods. Multiple markets can be streamed simultaneously.

The books restart automatically in case of connection issues, data inconsistencies and timeouts, and when provided sequence numbers are verified to ensure the book is accurate. Internal logic has been minimised and efficient sorting algorithms keep the book fast, accurate and lightweight.

The modular setup enables easy implementation of books for other exchanges, by creating a new interface that implements the exchange specific logic for the connection and data processing.

Usage
-----
This module requires the ``sortedcontainers`` (v1.5) and ``websocket-client`` modules. Install them with ``python3 setup.py install`` or using your package manager.

The ``example.py`` file demonstrates how to initialise an order book instance and display some data. You define the desired markets, start the book, wait until the first data is initialised and can then use the book handle. Multiple markets on a single exchange can be streamed simultaneously.

The module exposes the following public methods:
* ``get_top_asks(base_currency, quote_currency, amount)`` - Get the top asks in the book
* ``get_top_bids(base_currency, quote_currency, amount)`` - Get the top bids in the book
* ``get_middle(base_currency, quote_currency)`` - Get the middle of bid and ask in the book
* ``get_ask_rate_amount(base_currency, quote_currency, rate)`` - Determine how many is offered for a specific rate on the ask side of the book
* ``get_bid_rate_amount(base_currency, quote_currency, rate)`` - Determine how many is offered for a specific rate on the bid side of the book
* ``complete_initialisation()`` - Blocks until the order book initialisation is completed

When the order book is connecting, restarting or waiting for the initial data to come in, any requests to the book will result in an ``OrderBookOutOfSync`` exception. This will resolve automatically when the connection (re-)establishes and you can choose to either continue retrying until no exception is thrown anymore or call ``complete_initialisation``, which will block until the book has recovered. An ``OrderBookError`` is a permanent and unrecoverable error.

All but the last of the above methods also support the ``last_heartbeat_interval`` parameter, specifying the maximum amount of seconds since the last update in the order book to consider data up to date (10 by default). If the last update is longer than the specified number of seconds ago, an ``OrderBookOutOfSync`` exception will be raised.

Author
------
Ricardo Persoon - development@ricardopersoon.nl
