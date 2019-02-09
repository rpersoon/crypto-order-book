# Copyright (c) 2017 - 2019 Ricardo Persoon
# Distributed under the MIT software license, see the accompanying file LICENSE


from .exceptions import OrderBookError
from .order_book import OrderBook

import json
import socket
import websocket


class PoloniexOrderBook(OrderBook):

    def __init__(self, markets, timeout=10, log_method=print, log_level=False):

        # Initialise the thread
        OrderBook.__init__(self, markets, timeout, log_method, log_level)

        # The Poloniex order book requires additional logic to translate the internal market ID to the actual market
        self.market_id_to_market = {}

    def connect(self):
        """
        Connect with the websocket API and return the handle. Raises OrderBookError in case of connection issues.

        :return: handle of the socket connection
        """

        try:
            socket_handle = websocket.create_connection("wss://api2.poloniex.com:443", timeout=self.timeout)

        except (websocket.WebSocketException, socket.timeout) as e:
            raise OrderBookError("Could not connect to websocket: %s" % e)

        return socket_handle

    def disconnect(self):
        """
        Disconnect from the websocket API. No exceptions in case of issues, as failing to disconnect is not a problem
        """

        # Close the websocket, while waiting for a maximum of 3 seconds. Any exceptions are discarded.
        try:
            self.socket_handle.close(timeout=3)

        except websocket.WebSocketException:
            pass

    def subscribe(self, base_currency, quote_currency):
        """
        Send subscribe command for a given market

        :param base_currency: desired base currency
        :param quote_currency: desired quote currency
        """

        # For Poloniex, the subscription command is a JSON instruction
        command = '{"command" : "subscribe", "channel" : "%s_%s"}' % (quote_currency.upper(), base_currency.upper())

        # Send the instruction
        self.socket_handle.send(command)

    def receive(self):
        """
        Receive and process new websocket messages

        :return list: list of all messages received
        """

        try:
            received_message = self.socket_handle.recv()

        except (websocket.WebSocketException, TimeoutError) as e:
            raise OrderBookError("Websocket receive failed: %s" % e)

        # Discard empty messages
        if len(str(received_message)) == 0:
            return []

        try:
            decoded_message = json.loads(received_message)

        except ValueError:
            raise OrderBookError("Couldn't decode JSON message after receiving update")

        # Verify that the decoded message is a list
        if not isinstance(decoded_message, list):
            raise OrderBookError("Decoded JSON message was not a list: %s" % decoded_message)

        # Compile a list of all messages to be processed in this receive
        message_list = []

        # Process heartbeat messages, for Poloniex consisting of a list with one integer: 1010
        if len(decoded_message) == 1 and decoded_message[0] == 1010:
            message_list.append(['heartbeat'])

        elif len(decoded_message) == 3:

            # Process all updates contained in the message in a loop. Index 2 contains the data, while index 0 is the
            # Poloniex market_id and index 1 the sequence number
            for update in decoded_message[2]:

                # Process initialisation update. Extend instead of append to the list, as a list with multiple
                # updates will be returned at once.
                if update[0] == 'i':
                    message_list.extend(self.process_initialisation(decoded_message[0], update[1]))

                # Process general order book update (addition / removal)
                elif update[0] == 'o':

                    # Call the process_update method and append the result data structure to the message_list
                    message_list.append(self.process_update(decoded_message[0], update[1:4]))

            # Verify the sequence number. Only doing this after processing the message, as the market currencies can
            # only be determined after receiving the initial message.
            [base_currency, quote_currency] = self.translate_market_id_to_market(decoded_message[0])
            self.verify_sequence(decoded_message[1], base_currency, quote_currency)

        else:
            self.log("Discarding unknown message: %s" % decoded_message, 'warning')

        return message_list

    def reset_data_structures(self):
        """
        Reset data structures in case of an order book restart
        """

        # Reset the market ID administration
        self.market_id_to_market = {}

    def process_initialisation(self, market_id, initial_data):

        """
        Processes the initial data of a market after receiving the initialisation response

        :param market_id: id of the market as reported by the API
        :param initial_data: the initial data
        :return list: list of updates to be processed by the book
        """

        # Verify that the given market is not yet defined
        try:
            self.translate_market_id_to_market(market_id)

        except OrderBookError:
            pass

        else:
            raise OrderBookError("Received initialisation for market with ID %s, which is already defined" % market_id)

        # Deduce the base and quote currency from the initialisation response
        currency_pair = initial_data['currencyPair'].split('_')

        if len(currency_pair) != 2:
            raise OrderBookError("Invalid currency pair received: %s" % currency_pair)

        # Insert the translation from market_id to market in the local storage
        base_currency = currency_pair[1].lower()
        quote_currency = currency_pair[0].lower()
        self.market_id_to_market[market_id] = [base_currency, quote_currency]

        # Compile all update messages in a list
        update_messages = []

        # Process all asks
        for rate, amount in initial_data['orderBook'][0].items():
            update_messages.append(['update_ask', base_currency, quote_currency, float(rate), float(amount)])

        # Process all bids
        for rate, amount in initial_data['orderBook'][1].items():
            update_messages.append(['update_bid', base_currency, quote_currency, float(rate), float(amount)])

        return update_messages

    def process_update(self, market_id, update_data):
        """
        Process an order book event

        :param market_id: ID of the currency as reported by the API
        :param update_data: the update data
        :return list: update data, containing the update type, base and quote currency and the rate
        """

        # Translate the currency ID reported by the API to the pair we know
        [base_currency, quote_currency] = self.translate_market_id_to_market(market_id)

        update_type = int(update_data[0])
        update_rate = float(update_data[1])
        update_amount = float(update_data[2])

        # Type 0 is an update on the ask side of the order book
        if update_type == 0:

            # Amount 0.0 indicates a removal from the book
            if update_amount == 0.0:
                return ['remove_ask', base_currency, quote_currency, update_rate]

            else:
                return ['update_ask', base_currency, quote_currency, update_rate, update_amount]

        # Type 1 is an update on the bid side of the order book
        elif update_type == 1:

            # Amount 0.0 indicates a removal from the book
            if update_amount == 0.0:
                return ['remove_bid', base_currency, quote_currency, update_rate]

            else:
                return ['update_bid', base_currency, quote_currency, update_rate, update_amount]

        else:
            raise OrderBookError("Unexpected update type %s" % update_type)

    def translate_market_id_to_market(self, market_id):
        """
        Translate a Poloniex internal market_id to the associated base and quote currency

        :param market_id: market_id as reported by Poloniex
        :return list: list with base and quote currency
        """

        try:
            return self.market_id_to_market[market_id]

        except KeyError:
            raise OrderBookError("Market with ID %s not yet defined" % market_id)

    def verify_sequence(self, sequence_number, base_currency, quote_currency):
        """
        As Poloniex provides sequence numbers with updates, we can use those to verify the integrity of the order book
        by verifying we have received all messages. Initialises a restart of the order book and raises an exception if
        the sequence is incorrect. Each market has its own individual sequence number.

        :param sequence_number: received sequence number
        :param base_currency: market base currency
        :param quote_currency: market quote currency
        """

        # The new sequence number should be exactly the old number + 1
        if self.data_store[(base_currency, quote_currency)]['last_sequence'] != sequence_number - 1 and \
                self.data_store[(base_currency, quote_currency)]['last_sequence'] is not None:

            self.log("Invalid sequence number in order book: old sequence was %s, while the new sequence is %s" %
                     (self.data_store[(base_currency, quote_currency)]['last_sequence'], sequence_number), 'error')

            # Initiate a restart of the order book
            self.restart = True

        # Update the sequence number
        self.data_store[(base_currency, quote_currency)]['last_sequence'] = sequence_number
