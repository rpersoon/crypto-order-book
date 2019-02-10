# Copyright (c) 2017 - 2019 Ricardo Persoon
# Distributed under the MIT software license, see the accompanying file LICENSE


from .exceptions import OrderBookError, OrderBookOutOfSync
from .binary_search import get_index

import datetime
import logging
import sortedcontainers
import threading
import time


logger = logging.getLogger('OrderBook')


class OrderBook(threading.Thread):

    def __init__(self, markets, timeout=10):
        """
        Initialise the order book

        :param markets: list with markets to connect to
        :param timeout: timeout of the websocket connection
        """

        # Initialise the thread
        threading.Thread.__init__(self)

        self.markets = markets
        self.timeout = timeout

        self.data_store = {}
        self.socket_handle = None
        self.restart = False
        self.running = True
        self.last_heartbeat = datetime.datetime.now()

        # Some exchanges specify that a delete of a non-existing order can happen. We do not raise errors if that
        # happens when this flag is set (in the child class).
        self.soft_delete_fail = False

    def run(self):
        """
        Main run function of the order book, executed in a thread using start(). Starts the order book and processes
        all communications.
        """

        # Continue as long as there is no stop signal
        while self.running:

            # Initial variables, specific to each connection
            connection_tries = 0
            connection_delay = 0

            # Initialise the data structure
            for currency_pair in self.markets:
                self.data_store[currency_pair['base_currency'], currency_pair['quote_currency']] = {
                    'order_book_ask': sortedcontainers.SortedListWithKey(key=lambda val: val[0]),
                    'order_book_bid': sortedcontainers.SortedListWithKey(key=lambda val: -val[0]),
                    'last_sequence': None,
                    'status': 'inactive',
                }

            # Connect to the order book. Continue trying in case of issues or a temporary downtime
            while self.socket_handle is None:

                # Delay connecting if required, to prevent flooding the remote server with connection tries
                time.sleep(connection_delay)

                # Call the connect function, implemented by the child class
                try:
                    self.socket_handle = self.connect()
                except OrderBookError as e:
                    logger.warning("Could not connect with the websocket API: %s" % e)

                    connection_tries += 1

                    # Delay the next connection if connecting failed more than 3 times. 1 second for the 4th try,
                    # up until 5 seconds for the 8th try and over
                    if connection_tries > 3:
                        connection_delay = min(connection_tries - 3, 5)

                    # Give up after 2000 failed tries to connect
                    if connection_tries > 2000:
                        raise OrderBookError("Failed to connect with the websocket after 2000 tries")

            logger.info("Order book connection established")

            # Subscribe to all specified markets
            for pair, _ in self.data_store.items():

                # Send subscription message
                self.subscribe(pair[0], pair[1])

                # Update status of market
                self.data_store[pair]['status'] = 'initialising'

            # Run in a loop to process messages until we want to stop, encounter an error or timeout
            while self.running and not self.restart:

                # Call the update method of the child. Each call returns a list with 0 or more update messages
                try:
                    updates = self.receive()
                except OrderBookError as e:
                    logger.warning("Error while receiving data: %s" % e)
                    self.restart = True

                else:
                    # Process all updates
                    if len(updates) > 0:
                        for item in updates[:-1]:
                            self.update(item)
                        self.update(updates[-1], True)

            # Initialise a restart if requested
            if self.restart and self.running:
                logger.info("Order book restart initiated")

                # Try to cleanly disconnect
                self.disconnect()

                # Reset data structures
                self.data_store = {}
                self.socket_handle = None
                self.restart = False

                # Instruct child class to reset its exchange specific data structures, if implemented
                self.reset_data_structures()

        # Disconnect when shutting down
        self.disconnect()

    def update(self, update_content, last_update=False):
        """
        Process an update message to update the state of the order book

        :param update_content: update message
        :param last_update: whether this update is the last one in this receive. In that case the market can be set to
                            'active' in case it is not yet, as all initial updates must have been processed
        """

        # Update the last heartbeat time
        self.last_heartbeat = datetime.datetime.now()

        # No further action required for heartbeats
        if update_content[0] == 'heartbeat':
            return

        market = (update_content[1], update_content[2])

        if update_content[0] == 'update_ask':
            index = get_index(update_content[3], self.data_store[market]['order_book_ask'])

            # Update the value if an existing entry is found, or insert it if the entry is new
            if index is False:
                self.data_store[market]['order_book_ask'].add([update_content[3], update_content[4]])
            else:
                self.data_store[market]['order_book_ask'][index] = [update_content[3], update_content[4]]

            # Make sure the market is set to active if we are sure that all possible initial updates are processed,
            # which we are if this is the last update of this receive
            if last_update and self.data_store[market]['status'] != 'active':
                self.data_store[market]['status'] = 'active'

        elif update_content[0] == 'update_bid':
            index = get_index(update_content[3], self.data_store[market]['order_book_bid'], True)

            # Update the value if an existing entry is found, or insert it if the entry is new
            if index is False:
                self.data_store[market]['order_book_bid'].add([update_content[3], update_content[4]])
            else:
                self.data_store[market]['order_book_bid'][index] = [update_content[3], update_content[4]]

            # Make sure the market is set to active if we are sure that all possible initial updates are processed,
            # which we are if this is the last update of this receive
            if last_update and self.data_store[market]['status'] != 'active':
                self.data_store[market]['status'] = 'active'

        elif update_content[0] == 'remove_ask':
            index = get_index(update_content[3], self.data_store[market]['order_book_ask'])

            if index is False:
                if not self.soft_delete_fail:
                    logger.error("Request to delete not existing sell order with rate %s. Restarting." %
                                 update_content[3])
                    self.restart = True
            else:
                del self.data_store[market]['order_book_ask'][index]

        elif update_content[0] == 'remove_bid':
            index = get_index(update_content[3], self.data_store[market]['order_book_bid'], True)

            if index is False:
                if not self.soft_delete_fail:
                    logger.error("Request to delete not existing buy order with rate %s. Restarting." %
                                 update_content[3])
                    self.restart = True

            else:
                del self.data_store[market]['order_book_bid'][index]

    def verify_status(self, base_currency, quote_currency, last_heartbeat_interval=10):
        """
        Verify the status of the order book. Initiates a restart and raises an exception if the order book is out of
        sync

        :param base_currency: market base currency
        :param quote_currency: market quote_currency
        :param last_heartbeat_interval: maximum allowed time in seconds since the last heartbeat
        """

        # Verify that the data structure is present
        if not isinstance(self.data_store, dict) or len(self.data_store) == 0:
            raise OrderBookOutOfSync("Order book is initialising")

        # Verify that the market exists
        try:
            self.data_store[(base_currency, quote_currency)]
        except KeyError:
            raise OrderBookError("The market %s - %s does not exist" % (base_currency.upper(),
                                                                        quote_currency.upper()))

        # Verify that we are not going to restart
        if self.restart:
            raise OrderBookOutOfSync("Restart initialised")

        # Check that the market status is active
        if self.data_store[(base_currency, quote_currency)]['status'] != 'active':
            raise OrderBookOutOfSync("Order book is not active")

        # Verify that the last heartbeat is less than the specified number of seconds ago
        if datetime.datetime.now() > self.last_heartbeat + datetime.timedelta(seconds=last_heartbeat_interval):

            # Raise out of sync error. We do not restart at this moment yet,
            raise OrderBookOutOfSync("No update in the entire order book for %s seconds" %
                                     (datetime.datetime.now() - self.last_heartbeat).seconds)

        # Verify that the top bid is not higher than or equal to the top ask, which would imply a problem
        if len(self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_ask']) > 0 and \
                len(self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_bid']) > 0:
            if self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_ask'][0] <= \
                    self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_bid'][0]:

                # Set the restart flag
                self.restart = True

                raise OrderBookOutOfSync("Inconsistent data in order book")

    def initialisation_completed(self):
        """
        Verify whether the order book is active and the order books for all markets have been initialised

        :return bool: True if all markets initialised, False if not
        """

        # Not completed at all when the data store has no content
        if len(self.data_store) == 0:
            return False

        # Each of the markets should be active
        for _, item in self.data_store.items():
            if item['status'] != 'active':
                return False

        return True

    def connect(self):
        """
        Connect with the websocket API and return the handle. Raises OrderBookError in case of connection issues. To
        be overridden by the child class.

        :return: handle of the socket connection
        """

        raise NotImplementedError("The connect method should be overridden by a child class")

    def disconnect(self):
        """
        Disconnect from the websocket API. No exceptions in case of issues, as failing to disconnect is not a problem.
        To be overridden by the child class.
        """

        raise NotImplementedError("The disconnect method should be overridden by a child class")

    def subscribe(self, base_currency, quote_currency):
        """
        Send subscribe command for a given market. To be overridden by the child class.

        :param base_currency: desired base currency
        :param quote_currency: desired quote currency
        """

        raise NotImplementedError("The subscribe method should be overridden by a child class")

    def receive(self):
        """
        Receive and process new websocket messages. To be overridden by the child class.
        """

        raise NotImplementedError("The receive method should be overridden by a child class")

    def reset_data_structures(self):
        """
        Reset child class data structures in case of an order book restart. Can be implemented by child class, but not
        required.
        """

        pass

    def get_top_asks(self, base_currency, quote_currency, amount, last_heartbeat_interval=10):
        """
        Get the top asks in the book

        :param base_currency: market base currency
        :param quote_currency: market quote_currency
        :param amount: number of asks
        :param last_heartbeat_interval: maximum allowed time in seconds since last heartbeat to still consider the
                                        order book to be 'in sync'
        """

        # Verify that the order book is still up to date
        self.verify_status(base_currency, quote_currency, last_heartbeat_interval)

        if not isinstance(amount, int) or amount < 1 or amount > 5000:
            raise OrderBookError("The number of requested asks should be an integer between 1 and 5000")

        try:
            return self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_ask'][:amount]
        except KeyError:
            raise OrderBookError("Unknown currency pair %s - %s" % (base_currency.upper(), quote_currency.upper()))

    def get_top_bids(self, base_currency, quote_currency, amount, last_heartbeat_interval=10):
        """
        Get the top bids in the book

        :param base_currency: market base currency
        :param quote_currency: market quote currency
        :param amount: number of bids
        :param last_heartbeat_interval: maximum allowed time in seconds since last heartbeat to still consider the
                                        order book to be 'in sync'
        """

        # Verify that the order book is still up to date
        self.verify_status(base_currency, quote_currency, last_heartbeat_interval)

        if not isinstance(amount, int) or amount < 1 or amount > 5000:
            raise OrderBookError("The number of requested bids should be an integer between 1 and 5000")

        try:
            return self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_bid'][:amount]
        except KeyError:
            raise OrderBookError("Unknown currency pair %s - %s" % (base_currency.upper(), quote_currency.upper()))

    def get_middle(self, base_currency, quote_currency, last_heartbeat_interval=10):
        """
        Get the middle of bid and ask in the book

        :param base_currency: market base currency
        :param quote_currency: market quote currency
        :param last_heartbeat_interval: maximum allowed time in seconds since last heartbeat to still consider the
                                        order book to be 'in sync'
        """

        # Verify that the order book is still up to date
        self.verify_status(base_currency, quote_currency, last_heartbeat_interval)

        top_bid = self.get_top_bids(base_currency, quote_currency, 1, last_heartbeat_interval)[0][0]
        top_ask = self.get_top_asks(base_currency, quote_currency, 1, last_heartbeat_interval)[0][0]

        return (top_bid + top_ask) / 2

    def get_ask_rate_amount(self, base_currency, quote_currency, rate, last_heartbeat_interval=10):
        """
        Determine how many is offered for a specific rate on the ask side of the book

        :param base_currency: market base currency
        :param quote_currency: market quote currency
        :param rate: the rate to retrieve the amount offered for
        :param last_heartbeat_interval: maximum allowed time in seconds since last heartbeat to still consider the
                                        order book to be 'in sync'
        :return: amount offered at the requested rate. 0 if no entry is available in the order book
        """

        # Verify that the order book is still up to date
        self.verify_status(base_currency, quote_currency, last_heartbeat_interval)

        if not isinstance(rate, float) or rate < 0:
            raise OrderBookError("The desired rate should be a positive float")

        # Verify that the market exists
        try:
            self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_ask']
        except KeyError:
            raise OrderBookError("Unknown currency pair %s - %s" % (base_currency.upper(), quote_currency.upper()))

        index = 0

        while index < len(self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_ask']):
            entry = self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_ask'][index]

            # If this is the desired rate, return amount offered
            if entry[0] == rate:
                return entry[1]

            # Otherwise if the rate is too high, an entry with this amount didn't exist. Return 0.
            elif entry[0] > rate:
                return 0

            # If this is not the case either, then the rate we are looking at is  too low. Continue to look at the next
            # iteration.
            index += 1

    def get_bid_rate_amount(self, base_currency, quote_currency, rate, last_heartbeat_interval=10):
        """
        Determine how many is offered for a specific rate on the bid side of the book

        :param base_currency: market base currency
        :param quote_currency: market quote currency
        :param rate: the rate to retrieve the amount offered for
        :param last_heartbeat_interval: maximum allowed time in seconds since last heartbeat to still consider the
                                        order book to be 'in sync'
        :return: amount offered at the requested rate. 0 if no entry is available in the order book
        """

        # Verify that the order book is still up to date
        self.verify_status(base_currency, quote_currency, last_heartbeat_interval)

        if not isinstance(rate, float) or rate < 0:
            raise OrderBookError("The desired rate should be a positive float")

        # Verify that the market exists
        try:
            self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_bid']
        except KeyError:
            raise OrderBookError("Unknown currency pair %s - %s" % (base_currency.upper(), quote_currency.upper()))

        index = 0

        while index < len(self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_bid']):
            entry = self.data_store[(base_currency.lower(), quote_currency.lower())]['order_book_bid'][index]

            # If this is the desired rate, return amount offered
            if entry[0] == rate:
                return entry[1]

            # Otherwise if the rate is too high, an entry with this amount didn't exist. Return 0.
            elif entry[0] < rate:
                return 0

            # If this is not the case either, then the rate we are looking at is  too low. Continue to look at the next
            # iteration.
            index += 1

    def stop(self):
        """
        Ends the order book updating and shuts it down
        """

        self.running = False

    def complete_initialisation(self):
        """
        Blocks until the order book initialisation is completed

        :return bool: True when initialisation completed
        """

        # Continuously poll whether the initialisation completed
        while True:
            if self.initialisation_completed():
                return True
            else:
                time.sleep(0.1)
