Robust cryptocurrency live websocket order book - Poloniex implementation
=========================================================================

A robust, high performance and extendable cryptocurrency order book implementation in Python 3, by default including an implementation for Poloniex. The order book streams live data through a websocket feed and provides easy access to the contents of the book through several methods. Multiple markets can be streamed simultaneously.

The implementation features automatic restarts in case of connection issues, data inconsistencies and timeouts, and verifies sequence numbers where provided to ensure the book is accurate. Internal logic has been reduced to a minimum and efficient sorting algorithms keep the book as fast, accurate and lightweight as possible.

The modular setup of the code enables straightforward implementation of order books for other exchanges, by creating a new interface that implements the exchange specific logic for the connection and data processing. This release comes with the Poloniex book by default. While Bittrex, Bitfinex and others have successfully been implemented, I am unable to open source those at this moment.

Usage
-----
This module requires the ``sortedcontainers`` and ``websocket-client`` modules. You can install them with ``python3 setup.py install``, or through pip, EasyInstall or another manager.

The ``example.py`` file demonstrates how to initialise an order book instance and display some data. You define the desired markets, start the book, wait until the first data is initialised and can then use the book handle. Multiple markets on a single exchange can be streamed simultaneously.

The order book exposes the following functional public methods:
* ``get_top_asks(base_currency, quote_currency, amount)`` - Get the top asks in the book
* ``get_top_bids(base_currency, quote_currency, amount)`` - Get the top bids in the book
* ``get_middle(base_currency, quote_currency)`` - Get the middle of bid and ask in the book
* ``get_ask_rate_amount(base_currency, quote_currency, rate)`` - Determine how many is offered for a specific rate on the ask side of the book
* ``get_bid_rate_amount(base_currency, quote_currency, rate)`` - Determine how many is offered for a specific rate on the bid side of the book
* ``complete_initialisation()`` - Blocks until the order book initialisation is completed

When the order book is connecting, restarting or waiting for the initial data to come in, any requests to the book will result in an ``OrderBookOutOfSync`` exception. This will resolve automatically when the connection re-establishes and you can choose to either continue retrying until no exception is thrown anymore, or call ``complete_initialisation``, which will block until the book has recovered. An ``OrderBookError`` is a permanent and unrecoverable error.

All but the last of the above methods also support the ``last_heartbeat_interval`` parameter, specifying the maximum amount of seconds since the last update in the order book to consider data up to date (10 by default). If the last update is longer than the specified number of seconds ago, an ``OrderBookOutOfSync`` exception will be raised.

Author
------
Ricardo Persoon - development@ricardopersoon.nl

If you use this software to make money, a small donation would be much appreciated: \
BTC address: 1JA6YtPK9vnWRAjLw7Yi8UBMf3Aqjom6Kv \
LTC address: 3Pj2AUQjXyykoU5vAZ9YAgsA46w7Gd7L42
