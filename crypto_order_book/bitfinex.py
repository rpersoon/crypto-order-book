# Copyright (c) 2017 - 2019 Ricardo Persoon
# Distributed under the MIT software license, see the accompanying file LICENSE

from .exceptions import OrderBookError
from .order_book import OrderBook

import json
import socket
import websocket


class BitfinexOrderBook(OrderBook):

    def __init__(self, markets, timeout=10):

        # Initialise the thread
        OrderBook.__init__(self, markets, timeout)

        self.channel_id_to_market = {}

    def connect(self):
        """
        Connect with the websocket API and return the handle. Raises OrderBookError in case of connection issues.

        :return: handle of the socket connection
        """

        try:
            socket_handle = websocket.create_connection("wss://api.bitfinex.com/ws/2:443", timeout=self.timeout)
        except (websocket.WebSocketException, socket.timeout, ConnectionError, TimeoutError) as e:
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

        # Subscribe to the market with P0 precision and live updating
        request_data = {
            'event': 'subscribe',
            'channel': 'book',
            'prec': 'P0',
            'symbol': 't%s%s' % (base_currency.upper(), quote_currency.upper()),
            'len': '100',
            'freq': 'F0'
        }

        # Send the instruction
        self.socket_handle.send(json.dumps(request_data))

    def receive(self):
        """
        Receive and process new websocket messages

        :return list: list of all messages received
        """

        try:
            received_message = self.socket_handle.recv()
        except (websocket.WebSocketException, TimeoutError, ConnectionError) as e:
            raise OrderBookError("Websocket connection failed: %s" % e)

        # Discard empty messages
        if len(str(received_message)) == 0:
            return []

        try:
            decoded_message = json.loads(received_message)
        except ValueError:
            raise OrderBookError("Couldn't decode JSON message after receiving update")

        if isinstance(decoded_message, dict):
            try:
                event = decoded_message['event']
            except KeyError:
                raise OrderBookError("Received dictionary response without event")

            if event == 'subscribed':
                self.process_subscription(decoded_message)
            elif event != 'info':
                raise OrderBookError("Received unexpected event %s" % event)

        elif isinstance(decoded_message, list):
            return self.process_update(decoded_message)
        else:
            raise OrderBookError("Received unexpected message format")

        return []

    def process_subscription(self, subscription_message):

        """
        Processes the initial data of a market after receiving the initialisation response

        :param subscription_message: the initial data
        :return list: list of updates to be processed by the book
        """

        try:
            pair = subscription_message['pair']
        except KeyError:
            raise OrderBookError("No pair defined in subscribed message")

        if len(pair) != 6:
            raise OrderBookError("Unexpected pair: %s" % pair)

        try:
            channel_id = subscription_message['chanId']
        except KeyError:
            raise OrderBookError("No channel ID defined in message")

        # Verify that the given channel is not yet defined
        try:
            self.channel_id_to_market[channel_id]
        except KeyError:
            pass
        else:
            raise OrderBookError("Received initialisation with channel ID %s, which is already defined" % channel_id)

        currency_base = pair[0:3]
        currency_quote = pair[3:6]

        self.channel_id_to_market[channel_id] = [currency_base.lower(), currency_quote.lower()]

    def process_update(self, update_data):
        """
        Process an order book event

        :param update_data: the update data
        :return list: update data, containing the update type, base and quote currency and the rate
        """

        if len(update_data) < 2:
            raise OrderBookError("Received unexpected update message: %s" % update_data)

        channel_id = update_data[0]

        if not isinstance(channel_id, int):
            raise OrderBookError("Invalid channel ID %s" % channel_id)

        # Translate the currency ID reported by the API to the pair we know
        [base_currency, quote_currency] = self.channel_id_to_market[channel_id]

        update_messages = []

        if len(update_data) == 2:
            if update_data[1] == 'hb':
                update_messages.append(['heartbeat'])
            elif isinstance(update_data[1], list):
                for item in update_data[1]:
                    update_messages.append(self.process_single_update(base_currency, quote_currency, item))

        elif len(update_data) == 4:
            update_messages.append(self.process_single_update(base_currency, quote_currency, update_data[1:]))

        return update_messages

    @staticmethod
    def process_single_update(base_currency, quote_currency, update):
        """
        Process a single update (out of a list of many messages) and extract the internal update message

        :param base_currency: market base currency
        :param quote_currency: market quote currency
        :param update: update message
        :return list: internal update message, telling the order book what to change
        """

        rate = update[0]
        count = update[1]
        amount = update[2]

        if count == 0:
            # Delete at bids when amount is 1
            if amount == 1:
                return ['remove_bid', base_currency, quote_currency, rate]
            # Delete at asks when amount is 1
            elif amount == -1:
                return ['remove_ask', base_currency, quote_currency, rate]
            else:
                raise OrderBookError("Unexpected data in delete command")

        # Add an order
        else:
            if amount > 0:
                return ['update_bid', base_currency, quote_currency, rate, amount]
            else:
                return ['update_ask', base_currency, quote_currency, rate, abs(amount)]
