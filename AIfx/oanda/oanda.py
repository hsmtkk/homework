import logging
from datetime import datetime
import math
import time

import dateutil.parser
from oandapyV20 import API
from oandapyV20.endpoints import accounts
from oandapyV20.endpoints import instruments
from oandapyV20.endpoints import orders
from oandapyV20.endpoints import trades
from oandapyV20.endpoints.pricing import PricingInfo
from oandapyV20.exceptions import V20Error

import constants
import set

ORDER_FILLED = 'FILLED'

logger = logging.getLogger(__name__)


class Balance(object):
    def __init__(self, currency, balance):
        self.balance = balance
        self.currency = currency


class Ticker(object):
    def __init__(self, product_code, timestamp, bid, ask, volume):
        self.product_code = product_code
        self.timestamp = timestamp
        self.bid = bid
        self.ask = ask
        self.volume = volume

    @property
    def mid_price(self):
        return (self.bid + self.ask) / 2

    @property
    def time(self):
        return datetime.utcfromtimestamp(self.timestamp)

    def truncate_date_time(self, duration):
        ticker_time = self.time
        if duration == constants.DURATION_1M:
            time_format = '%Y-%m-%d %H:%M'
        elif duration == constants.DURATION_5M:
            new_5min = math.floor(self.time.minute / 5) * 5
            ticker_time = datetime(
                self.time.year, self.time.month, self.time.day,
                self.time.hour, new_5min,
            )
            time_format = '%Y-%m-%d %H:%M'
        elif duration == constants.DURATION_15M:
            new_15min = math.floor(self.time.minute / 15) * 15
            ticker_time = datetime(
                self.time.year, self.time.month, self.time.day,
                self.time.hour, new_15min,
            )
            time_format = '%Y-%m-%d %H:%M'
        else:
            logger.warning(f'truncate_date_time_no_datetime')
            return None

        str_date = datetime.strftime(ticker_time, time_format)
        return datetime.strptime(str_date, time_format)


class Order(object):
    def __init__(self, product_code, side, units, order_type='MARKET', order_state=None, filling_transaction_id=None):
        self.product_code = product_code
        self.side = side
        self.units = units
        self.order_type = order_type
        self.order_state = order_state
        self.filling_transaction_id = filling_transaction_id


class OrderTimeoutError(Exception):
    """order timeout error"""


class Trade(object):
    def __init__(self, trade_id, side, price, units):
        self.trade_id = trade_id
        self.side = side
        self.price = price
        self.units = units


class APIClient(object):
    def __init__(self, access_token=set.access_token, account_id=set.account_id, environment='practice'):
        self.access_token = access_token
        self.account_id = account_id
        self.client = API(access_token=access_token)

    def get_balance(self):
        r = accounts.AccountSummary(accountID=self.account_id)
        try:
            res = self.client.request(r)
        except V20Error as e:
            logger.error(f'get_balance_error:{e}')
            raise

        balance = float(res['account']['balance'])
        currency = res['account']['currency']
        return Balance(currency, balance)

    def get_ticker(self, product_code):
        params = {
            'instruments': product_code
        }
        r = PricingInfo(accountID=self.account_id, params=params)
        try:
            res = self.client.request(r)
        except V20Error as e:
            logger.error(f'get_ticker_error:{e}')
            raise

        timestamp = datetime.timestamp(
            dateutil.parser.parse(res['time'])
        )
        price = res['prices'][0]
        instrument = price['instrument']
        bid = float(price['bids'][0]['price'])
        ask = float(price['asks'][0]['price'])
        volume = self.get_candle_volume()
        return Ticker(instrument, timestamp, bid, ask, volume)

    def get_candle_volume(self, count=1, granularity=constants.TRADE_MAP[set.trade_duration]['granularity']):
        params = {
            'count': count,
            'granularity': granularity,
        }
        r = instruments.InstrumentsCandles(instrument=set.product_code, params=params)
        try:
            res = self.client.request(r)
        except V20Error as e:
            logger.error(f'get_candle_volume_error:{e}')
            raise

        return int(res['candles'][0]['volume'])

    def get_realtime_ticker(self, callback):
        params = {
            'instruments': set.product_code
        }
        r = PricingInfo(accountID=self.account_id, params=params)
        try:
            res = self.client.request(r)
        except V20Error as e:
            logger.error(f'get_ticker_error:{e}')
            raise
        timestamp = datetime.timestamp(
            dateutil.parser.parse(res['time'])
        )
        price = res['prices'][0]
        instrument = price['instrument']
        bid = float(price['bids'][0]['price'])
        ask = float(price['asks'][0]['price'])
        volume = self.get_candle_volume()
        ticker = Ticker(instrument, timestamp, bid, ask, volume)
        callback(ticker)
        # try:
        #     for res in self.client.request(r):
        #         print(res)
        #         if res['type'] == 'PRICE':
        #             timestamp = datetime.timestamp(
        #                 dateutil.parser.parse(res['time'])
        #             )
        #             instrument = res['instrument']
        #             bid = float(res['bids'][0]['price'])
        #             ask = float(res['asks'][0]['price'])
        #             volume = self.get_candle_volume()
        #             ticker = Ticker(instrument, timestamp, bid, ask, volume)
        #             callback(ticker)
        #
        # except V20Error as e:
        #     logger.error(f'get_realtime_ticker_error:{e}')
        #     logger.error(str(e.code))
        #     logger.error(e.msg)
        #     raise

    def send_order(self, order: Order) -> Trade:
        if order.side == constants.BUY:
            side = 1
        elif order.side == constants.SELL:
            side = -1
        order_data = {
            'order': {
                'type': order.order_type,
                'instrument': order.product_code,
                'units': order.units * side,
            }
        }
        r = orders.OrderCreate(accountID=self.account_id, data=order_data)
        try:
            res = self.client.request(r)
            logger.info(f'send_order:{res}')
        except V20Error as e:
            logger.error(f'send_order_error:{e}')
            raise
        order_id = res['orderCreateTransaction']['id']
        order = self.wait_order_complete(order_id)

        if not order:
            logger.error('send_order_timeout')
            raise OrderTimeoutError

        return self.trade_details(order.filling_transaction_id)

    def wait_order_complete(self, order_id) -> Order:
        count = 0
        timeout_count = 5
        while True:
            order = self.get_order(order_id)
            if order.order_state == ORDER_FILLED:
                return order
            time.sleep(1)
            count += 1
            if count > timeout_count:
                return None

    def get_order(self, order_id):
        r = orders.OrderDetails(accountID=self.account_id, orderID=order_id)
        try:
            res = self.client.request(r)
            logger.info(f'get_order:{res}')
        except V20Error as e:
            logger.error(f'get_order_eeror:{e}')
            raise

        order = Order(
            product_code=res['order']['instrument'],
            side=constants.BUY if float(res['order']['units']) > 0 else constants.SELL,
            units=float(res['order']['units']),
            order_type=res['order']['type'],
            order_state=res['order']['state'],
            filling_transaction_id=res['order'].get('fillingTransactionID')
        )
        return order

    def trade_details(self, trade_id) -> Trade:
        r = trades.TradeDetails(self.account_id, trade_id)
        try:
            res = self.client.request(r)
            logger.info(f'trade_details:{res}')
        except V20Error as e:
            logger.error(f'trade_details_eeror:{e}')
            raise

        trade = Trade(
            trade_id=trade_id,
            side=constants.BUY if float(res['trade']['currentUnits']) > 0 else constants.SELL,
            units=float(res['trade']['currentUnits']),
            price=float(res['trade']['price'])
        )
        return trade

    def get_open_trade(self) -> list:
        r = trades.OpenTrades(self.account_id)
        try:
            res = self.client.request(r)
            logger.info(f'get_open_trade:{res}')
        except V20Error as e:
            logger.error(f'get_open_trade_error:{e}')
            raise

        trades_list = []
        for trade in res['trades']:
            trades_list.insert(0, Trade(
                trade_id=trade['id'],
                side=constants.BUY if float(trade['currentUnits']) > 0 else constants.SELL,
                units=float(trade['currentUnits']),
                price=float(trade['price'])
            ))
        return trades_list

    def trade_close(self, trade_id):
        r = trades.TradeClose(self.account_id, trade_id)
        try:
            res = self.client.request(r)
            logger.info(f'trade_close:{res}')
        except V20Error as e:
            logger.error(f'trade_close_error:{e}')
            raise

        trade = Trade(
            trade_id=trade_id,
            side=constants.BUY if float(res['orderFillTransaction']['units']) > 0 else constants.SELL,
            units=float(res['orderFillTransaction']['units']),
            price=float(res['orderFillTransaction']['price']),
        )
        return trade
