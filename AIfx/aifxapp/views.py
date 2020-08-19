import logging
from threading import Thread
from threading import Lock
import datetime
from datetime import timezone
import time
import sys
import warnings

import numpy as np
import talib
from dict2obj import Dict2Obj
from functools import partial

from .models import UsdJpy1M, UsdJpy5M, UsdJpy15M, SignalEvent
from django.shortcuts import render
from django.http.response import JsonResponse

import constants
import set
from oanda.oanda import APIClient
from oanda.oanda import Ticker
from oanda.oanda import Order
from utils.utils import Serializer

api = APIClient(set.access_token, set.account_id)
logger = logging.getLogger(__name__)


"""insert db"""


def factory_candle_class(product_code, duration):
    if product_code == constants.PRODUCT_CODE_USD_JPY:
        if duration == constants.DURATION_1M:
            return UsdJpy1M
        if duration == constants.DURATION_5M:
            return UsdJpy5M
        if duration == constants.DURATION_15M:
            return UsdJpy15M


def create_candle_with_duration(product_code, duration, ticker):
    cls = factory_candle_class(product_code, duration)
    ticker_time = ticker.truncate_date_time(duration)
    current_candle = cls.objects.filter(time=ticker_time).values()
    price = ticker.mid_price
    if not current_candle:
        cls.objects.create(time=ticker_time, open=price, close=price,
                           high=price, low=price, volume=ticker.volume)
        return True

    if current_candle[0]['high'] <= price:
        current_candle[0]['high'] = price
    elif current_candle[0]['low'] >= price:
        current_candle[0]['low'] = price

    current_candle[0]['volume'] += ticker.volume
    current_candle[0]['close'] = price
    current_candle.update(close=current_candle[0]['close'], high=current_candle[0]['high'],
                          low=current_candle[0]['low'], volume=current_candle[0]['volume'])

    return False


""" indicator """


def nan_zero(values):
    values[np.isnan(values)] = 0
    return values


def empty_none(input_list):
    if not input_list:
        return None
    return input_list


class Sma(Serializer):
    def __init__(self, period: int, values: list):
        self.period = period
        self.values = values


class Ema(Serializer):
    def __init__(self, period: int, values: list):
        self.period = period
        self.values = values


class BBands(Serializer):
    def __init__(self, n: int, k: float, high: list, mid: list, low: list):
        self.n = n
        self.k = k
        self.high = high
        self.mid = mid
        self.low = low


class Rsi(Serializer):
    def __init__(self, period: int, high: int, low: int, values: list):
        self.period = period
        self.high = high
        self.low = low
        self.values = values


class Macd(Serializer):
    def __init__(self, fast_period: int, slow_period: int, signal_period: int,
                 macd: list, macd_signal: list, macd_hist: list):
        self.fast_period = fast_period
        self.slow_period = slow_period
        self.signal_period = signal_period
        self.macd = macd
        self.macd_signal = macd_signal
        self.macd_hist = macd_hist


""" signal event """


def get_signal_events_by_count(count, product_code=set.product_code):
    rows = SignalEvent.objects.filter(product_code=product_code).order_by('-time')[:count].all()
    if rows is None:
        return []
    return rows


def get_signal_events_after_time(time):
    rows = SignalEvent.objects.filter(time__gte=time).all()
    if rows is None:
        return []
    return rows


class SignalEvents(object):
    def __init__(self, signals=None):
        if signals is None:
            self.signals = []
        else:
            self.signals = signals

    def can_buy(self, time):
        if len(self.signals) == 0:
            return True

        last_signal = self.signals[-1]
        if last_signal.side == constants.SELL and last_signal.time < time:
            return True

        return False

    def can_sell(self, time):
        if len(self.signals) == 0:
            return False

        last_signal = self.signals[-1]
        if last_signal.side == constants.BUY and last_signal.time < time:
            return True

        return False

    def buy(self, product_code, time, price, units, save):
        if not self.can_buy(time):
            return False

        signal_event = SignalEvent(time=time, product_code=product_code, side=constants.BUY,
                                   price=price, units=units)
        if save:
            signal_event.save()

        self.signals.append(signal_event)
        return True

    def sell(self, product_code, time, price, units, save):
        if not self.can_sell(time):
            return False

        signal_event = SignalEvent(time=time, product_code=product_code, side=constants.SELL,
                                   price=price, units=units)
        if save:
            signal_event.save()

        self.signals.append(signal_event)
        return True

    @staticmethod
    def get_signal_events_by_count(count: int):
        signal_events = get_signal_events_by_count(count=count)
        return SignalEvents(signal_events)

    @staticmethod
    def get_signal_events_after_time(time: datetime.datetime.time):
        signal_events = get_signal_events_after_time(time=time)
        return SignalEvents(signal_events)

    @property
    def profit(self):
        total = 0.0
        before_sell = 0.0
        is_holding = False
        for i in range(len(self.signals)):
            signal_event = self.signals[i]
            if i == 0 and signal_event.side == constants.SELL:
                continue
            if signal_event.side == constants.BUY:
                total -= signal_event.price * signal_event.units
                is_holding = True
            if signal_event.side == constants.SELL:
                total += signal_event.price * signal_event.units
                is_holding = False
                before_sell = total
        if is_holding:
            return before_sell
        return total

    @property
    def value(self):
        signals = [s.value for s in self.signals]
        if not signals:
            signals = None

        profit = self.profit
        if not self.profit:
            profit = None

        return {'signals': signals, 'profit': profit}


""" DateFrame """


class DataFrameCandle(object):
    def __init__(self, product_code=set.product_code, duration=set.trade_duration):
        self.product_code = product_code
        self.duration = duration
        self.candle_cls = factory_candle_class(self.product_code, self.duration)
        self.candles = []
        self.smas = []
        self.emas = []
        self.bbands = BBands(0, 0, [], [], [])
        self.rsi = Rsi(0, 0, 0, [])
        self.macd = Macd(0, 0, 0, [], [], [])
        self.events = SignalEvents()

    def set_all_candles(self, limit):
        try:
            self.candles = self.candle_cls.objects.order_by('time')[:limit]
        except self.candle_cls.DoesNotExist:
            return None
        return self.candles

    @property
    def value(self):
        return {
            'product_code': self.product_code,
            'duration': self.duration,
            'candles': [c.value for c in self.candles],
            'smas': empty_none([s.value for s in self.smas]),
            'emas': empty_none([s.value for s in self.emas]),
            'bbands': self.bbands.value,
            'rsi': self.rsi.value,
            'macd': self.macd.value,
            'events': self.events.value,
        }

    @property
    def opens(self):
        values = []
        for candle in self.candles:
            values.append(candle.open)
        return values

    @property
    def closes(self):
        values = []
        for candle in self.candles:
            values.append(candle.close)
        return values

    @property
    def highs(self):
        values = []
        for candle in self.candles:
            values.append(candle.high)
        return values

    @property
    def lows(self):
        values = []
        for candle in self.candles:
            values.append(candle.low)
        return values

    @property
    def volumes(self):
        values = []
        for candle in self.candles:
            values.append(candle.volume)
        return values

    def add_sma(self, period):
        if len(self.closes) > period:
            values = talib.SMA(np.asarray(self.closes), period)
            sma = Sma(period, nan_zero(values).tolist())
            self.smas.append(sma)
            return True
        return False

    def add_ema(self, period):
        if len(self.closes) > period:
            values = talib.EMA(np.asarray(self.closes), period)
            ema = Ema(period, nan_zero(values).tolist())
            self.emas.append(ema)
            return True
        return False

    def add_bbands(self, n: int, k: float):
        if n <= len(self.closes):
            high, mid, low = talib.BBANDS(np.asarray(self.closes), n, k, k, 0)
            high_list = nan_zero(high).tolist()
            mid_list = nan_zero(mid).tolist()
            low_list = nan_zero(low).tolist()
            self.bbands = BBands(n, k, high_list, mid_list, low_list)
            return True
        return False

    def add_rsi(self, period, high, low):
        if len(self.closes) > period:
            values = talib.RSI(np.asarray(self.closes), period)
            rsi = Rsi(period, high, low, nan_zero(values).tolist())
            self.rsi = rsi
            return True
        return False

    def add_macd(self, fast_period: int, slow_period: int, signal_period: int):
        if len(self.candles) > 1:
            macd, macd_signal, macd_hist = talib.MACD(
                np.asarray(self.closes), fast_period, slow_period, signal_period
            )
            macd_list = nan_zero(macd).tolist()
            macd_signal_list = nan_zero(macd_signal).tolist()
            macd_hist_list = nan_zero(macd_hist).tolist()
            self.macd = Macd(fast_period, slow_period, signal_period, macd_list, macd_signal_list, macd_hist_list)
            return True
        return False

    def add_events(self, time):
        signal_events = SignalEvents.get_signal_events_after_time(time)
        if len(signal_events.signals) > 0:
            self.events = signal_events
            return True
        return False

    """ test indicator """

    def back_test_ema(self, period_1: int, period_2: int):
        if len(self.candles) <= period_1 or len(self.candles) <= period_2:
            return None

        signal_events = SignalEvents()
        ema_value_1 = talib.EMA(np.array(self.closes), period_1)
        ema_value_2 = talib.EMA(np.array(self.closes), period_2)

        for i in range(1, len(self.candles)):
            if i < period_1 or i < period_2:
                continue

            if ema_value_1[i-1] < ema_value_2[i-1] and ema_value_1[i] >= ema_value_2[i]:
                signal_events.buy(product_code=self.product_code, time=self.candles[i].time,
                                  price=self.candles[i].close, units=1.0, save=False)
            elif ema_value_1[i-1] > ema_value_2[i-1] and ema_value_1[i] <= ema_value_2[i]:
                signal_events.sell(product_code=self.product_code, time=self.candles[i].time,
                                   price=self.candles[i].close, units=1.0, save=False)

        return signal_events

    def optimize_ema(self):
        performance = 0
        best_period_1 = 7
        best_period_2 = 14

        for period_1 in range(5, 15):
            for period_2 in range(12, 20):
                signal_events = self.back_test_ema(period_1, period_2)
                if signal_events is None:
                    continue
                profit = signal_events.profit
                if performance < profit:
                    performance = profit
                    best_period_1 = period_1
                    best_period_2 = period_2

        return performance, best_period_1, best_period_2

    def back_test_bb(self, n: int, k: float):
        if len(self.candles) <= n:
            return None

        signal_events = SignalEvents()
        up, _, down = talib.BBANDS(np.array(self.closes), n, k, k, 0)

        for i in range(1, len(self.candles)):
            if i < n:
                continue

            if down[i-1] > self.candles[i-1].close and down[i] <= self.candles[i].close:
                signal_events.buy(product_code=self.product_code, time=self.candles[i].time,
                                  price=self.candles[i].close, units=1.0, save=False)
            elif up[i-1] > self.candles[i-1].close and up[i] <= self.candles[i].close:
                signal_events.sell(product_code=self.product_code, time=self.candles[i].time,
                                   price=self.candles[i].close, units=1.0, save=False)

        return signal_events

    def optimize_bb(self):
        performance = 0
        best_n = 20
        best_k = 2.0

        for n in range(10, 20):
            for k in np.arange(1.9, 2.1, 0.1):
                signal_events = self.back_test_bb(n, k)
                if signal_events is None:
                    continue
                profit = signal_events.profit
                if performance < profit:
                    performance = profit
                    best_n = n
                    best_k = k

        return performance, best_n, best_k

    def back_test_rsi(self, period: int, buy_low: float, sell_high: float):
        if len(self.candles) <= period:
            return None

        signal_events = SignalEvents()
        values = talib.RSI(np.array(self.closes), period)

        for i in range(1, len(self.candles)):
            if values[i-1] == 0 or values[i-1] == 100:
                continue

            if values[i-1] < buy_low and values[i] >= buy_low:
                signal_events.buy(product_code=self.product_code, time=self.candles[i].time,
                                  price=self.candles[i].close, units=1.0, save=False)
            elif values[i-1] > sell_high and values[i] <= sell_high:
                signal_events.sell(product_code=self.product_code, time=self.candles[i].time,
                                   price=self.candles[i].close, units=1.0, save=False)

        return signal_events

    def optimize_rsi(self):
        performance = 0
        best_period = 14
        best_buy_low = 30.0
        best_sell_high = 70.0

        for period in range(10, 20):
            for buy_low in np.arange(29.9, 30.1, 0.1):
                for sell_high in np.arange(69.9, 70.1, 0.1):
                    signal_events = self.back_test_rsi(period, buy_low, sell_high)
                    if signal_events is None:
                        continue
                    profit = signal_events.profit
                    if performance < profit:
                        performance = profit
                        best_period = period
                        best_buy_low = buy_low
                        best_sell_high = sell_high

        return performance, best_period, best_buy_low, best_sell_high

    def back_test_macd(self, period: int, period2: int, signal: int):
        if len(self.candles) <= period or len(self.candles) <= period2 or len(self.candles) <= signal:
            return None

        signal_events = SignalEvents()
        macd, macd_signal, _ = talib.MACD(np.array(self.closes), period2, period, signal)

        for i in range(1, len(self.candles)):
            if macd[i] < 0 and macd_signal[i] < 0 and macd[i-1] < macd_signal[i-1] and macd[i] >= macd_signal[i]:
                signal_events.buy(product_code=self.product_code, time=self.candles[i].time,
                                  price=self.candles[i].close, units=1.0, save=False)
            elif macd[i] > 0 and macd_signal[i] > 0 and macd[i-1] > macd_signal[i-1] and macd[i] <= macd_signal[i]:
                signal_events.sell(product_code=self.product_code, time=self.candles[i].time,
                                   price=self.candles[i].close, units=1.0, save=False)

        return signal_events

    def optimize_macd(self):
        performance = 0
        best_period = 12
        best_period_2 = 26
        best_signal = 9

        for period in range(10, 19):
            for period_2 in range(20, 30):
                for signal in range(5, 15):
                    signal_events = self.back_test_macd(period, period_2, signal)
                    if signal_events is None:
                        continue
                    profit = signal_events.profit
                    if performance < profit:
                        performance = profit
                        best_period = period
                        best_period_2 = period_2
                        best_signal = signal

        return performance, best_period, best_period_2, best_signal

    """ indicator ranking """

    def optimize_params(self):
        ema_performance, ema_period_1, ema_period_2 = self.optimize_ema()
        bb_performance, bb_n, bb_k = self.optimize_bb()
        rsi_performance, rsi_period, rsi_buy_low, rsi_sell_high = self.optimize_rsi()
        macd_performance, macd_period, macd_period_2, macd_signal = self.optimize_macd()

        ema_ranking = Dict2Obj({'performance': ema_performance, 'enable': False})
        bb_ranking = Dict2Obj({'performance': bb_performance, 'enable': False})
        rsi_ranking = Dict2Obj({'performance': rsi_performance, 'enable': False})
        macd_ranking = Dict2Obj({'performance': macd_performance, 'enable': False})

        rankings = [ema_ranking, bb_ranking, rsi_ranking, macd_ranking]
        rankings = sorted(rankings, key=lambda o: o.performance, reverse=True)

        is_enable = False
        for i, ranking in enumerate(rankings):
            if i >= set.num_ranking:
                break

            if ranking.performance > 0:
                ranking.enable = True
                is_enable = True

        if not is_enable:
            return None

        return Dict2Obj({
            'ema_enable': ema_ranking.enable,
            'ema_period_1': ema_period_1,
            'ema_period_2': ema_period_2,
            'bb_enable': bb_ranking.enable,
            'bb_n': bb_n,
            'bb_k': bb_k,
            'rsi_enable': rsi_ranking.enable,
            'rsi_period': rsi_period,
            'rsi_buy_low': rsi_buy_low,
            'rsi_sell_high': rsi_sell_high,
            'macd_enable': macd_ranking.enable,
            'macd_period': macd_period,
            'macd_period_2': macd_period_2,
            'macd_signal': macd_signal,
        })


""" AI """


def duration_seconds(duration: str) -> int:
    if duration == constants.DURATION_1M:
        return 60
    elif duration == constants.DURATION_5M:
        return 60 * 5
    elif duration == constants.DURATION_15M:
        return 60 * 15
    else:
        return 0


class AI(object):
    def __init__(self, product_code, use_percent, duration, past_period, stop_limit_percent, back_test):
        self.API = APIClient(set.access_token, set.account_id)

        if back_test:
            self.signal_events = SignalEvents()
        else:
            self.signal_events = SignalEvents.get_signal_events_by_count(1)

        self.product_code = product_code
        self.use_percent = use_percent
        self.duration = duration
        self.past_period = past_period
        self.optimized_trade_params = None
        self.stop_limit = 0
        self.stop_limit_percent = stop_limit_percent
        self.back_test = back_test
        self.start_trade = datetime.datetime.now(timezone.utc)
        self.candle_cls = factory_candle_class(self.product_code, self.duration)
        self.update_optimize_params(False)

    def update_optimize_params(self, is_continue: bool):
        logger.info('action=update_optimize_params status=run')
        df = DataFrameCandle(self.product_code, self.duration)
        df.set_all_candles(self.past_period)
        if df.candles:
            self.optimized_trade_params = df.optimize_params()
        if self.optimized_trade_params is not None:
            logger.info(f'action=update_optimize_params params={self.optimized_trade_params.__dict__}')

        if is_continue and self.optimized_trade_params is None:
            time.sleep(10 * duration_seconds(self.duration))
            self.update_optimize_params(is_continue)

    def buy(self, candle):
        if self.back_test:
            could_buy = self.signal_events.buy(self.product_code, candle.time, candle.close, 1.0, save=False)
            return could_buy

        if self.start_trade > candle.time:
            logger.warning('action=buy status=old_time')
            return False

        if not self.signal_events.can_buy(candle.time):
            logger.warning('action=buy status=previous_buy')
            return False

        balance = self.API.get_balance()
        units = int(balance.balance * self.use_percent)
        order = Order(product_code=self.product_code, side=constants.BUY, units=units)
        trade = self.API.send_order(order)
        could_by = self.signal_events.buy(self.product_code, candle.time, trade.price, trade.units, save=True)
        return could_by

    def sell(self, candle):
        if self.back_test:
            could_sell = self.signal_events.sell(self.product_code, candle.time, candle.close, 1.0, save=False)
            return could_sell

        if self.start_trade > candle.time:
            logger.warning('action=sell status=old_time')
            return False

        if not self.signal_events.can_sell(candle.time):
            logger.warning('action=sell status=previous_sell')
            return False

        trades = self.API.get_open_trade()
        sum_price = 0
        units = 0
        for trade in trades:
            closed_trade = self.API.trade_close(trade.trade_id)
            sum_price += closed_trade.price * abs(closed_trade.units)
            units += abs(closed_trade.units)

        could_sell = self.signal_events.sell(self.product_code, candle.time, sum_price / units, units, save=True)
        return could_sell

    def trade(self):
        logger.info('action=trade status=run')
        params = self.optimized_trade_params
        if params is None:
            return

        df = DataFrameCandle(self.product_code, self.duration)
        df.set_all_candles(self.past_period)

        if params.ema_enable:
            ema_values_1 = talib.EMA(np.array(df.closes), params.ema_period_1)
            ema_values_2 = talib.EMA(np.array(df.closes), params.ema_period_2)

        if params.bb_enable:
            bb_high, _, bb_low = talib.BBANDS(np.array(df.closes), params.bb_n, params.bb_k, params.bb_k, 0)

        if params.rsi_enable:
            rsi_values = talib.RSI(np.array(df.closes), params.rsi_period)

        if params.macd_enable:
            macd, macd_signal, _ = talib.MACD(np.array(df.closes), params.macd_period, params.macd_period_2,
                                              params.macd_signal)

        for i in range(1, len(df.candles)):
            buy_point, sell_point = 0, 0

            if params.ema_enable and params.ema_period_1 <= i and params.ema_period_2 <= i:
                if ema_values_1[i-1] < ema_values_2[i-1] and ema_values_1[i] >= ema_values_2[i]:
                    buy_point += 1
                if ema_values_1[i-1] > ema_values_2[i-1] and ema_values_1[i] <= ema_values_2[i]:
                    sell_point += 1

            if params.bb_enable and params.bb_n <= i:
                if bb_low[i-1] > df.candles[i-1].close and bb_low[i] <= df.candles[i].close:
                    buy_point += 1
                if bb_high[i-1] < df.candles[i-1].close and bb_high[i] >= df.candles[i].close:
                    sell_point += 1

            if params.rsi_enable and rsi_values[i-1] != 0 and rsi_values[i-1] != 100:
                if rsi_values[i-1] < params.rsi_buy_low and rsi_values[i] >= params.rsi_buy_low:
                    buy_point += 1
                if rsi_values[i-1] > params.rsi_sell_high and rsi_values[i] <= params.rsi_sell_high:
                    sell_point += 1

            if params.macd_enable:
                if macd[i] < 0 and macd_signal[i] < 0 and macd[i-1] < macd_signal[i-1] and macd[i] >= macd_signal[i]:
                    buy_point += 1
                if macd[i] > 0 and macd_signal[i] > 0 and macd[i-1] > macd_signal[i-1] and macd[i] <= macd_signal[i]:
                    sell_point += 1

            if buy_point > 0:
                if not self.buy(df.candles[i]):
                    continue

                self.stop_limit = df.candles[i].close * self.stop_limit_percent

            if sell_point > 0 or self.stop_limit > df.candles[i].close:
                if not self.sell(df.candles[i]):
                    continue

                self.stop_limit = 0.0
                self.update_optimize_params(is_continue=True)


"""real time ticker"""


class StreamData(object):
    def __init__(self):
        self.ai = AI(
            product_code=set.product_code,
            use_percent=set.use_percent,
            duration=set.trade_duration,
            past_period=set.past_period,
            stop_limit_percent=set.stop_limit_percent,
            back_test=set.back_test
        )
        self.trade_lock = Lock()

    def stream_data(self):
        trade_with_ai = partial(self.trade, ai=self.ai)
        self.ai.API.get_realtime_ticker(callback=trade_with_ai)

    def trade(self, ticker: Ticker, ai: AI):
        logger.info(f'trade ticker:{ticker.__dict__}')
        for duration in constants.DURATIONS:
            created = create_candle_with_duration(ticker.product_code, duration, ticker)
            if created and duration == set.trade_duration:
                thread = Thread(target=self._trade, args=(ai,))
                thread.start()

    def _trade(self, ai: AI):
        with self.trade_lock:
            ai.trade()


stream = StreamData()


""" main """


def candle(request):
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    warnings.simplefilter('ignore')
    streamThread = Thread(target=stream.stream_data)
    streamThread.start()
    if request.method == 'GET':
        product_code = request.GET.get('product_code')
        if not product_code:
            return render(request, 'chart.html')

        limit_str = request.GET.get('limit')
        limit = 1000
        if limit_str:
            limit = int(limit_str)

        if limit < 0 or limit > 1000:
            limit = 1000

        duration = request.GET.get('duration')
        if not duration:
            duration = constants.DURATION_1M

        duration_time = constants.TRADE_MAP[duration]['duration']
        df = DataFrameCandle(product_code, duration_time)
        df.set_all_candles(limit)

        sma = request.GET.get('sma')
        if sma:
            sma_period1 = request.GET.get('smaPeriod1')
            sma_period2 = request.GET.get('smaPeriod2')
            sma_period3 = request.GET.get('smaPeriod3')
            if sma_period1:
                period1 = int(sma_period1)
            if sma_period2:
                period2 = int(sma_period2)
            if sma_period3:
                period3 = int(sma_period3)
            if not sma_period1 or period1 < 0:
                period1 = 7
            if not sma_period2 or period2 < 0:
                period2 = 14
            if not sma_period3 or period3 < 0:
                period3 = 50
            df.add_sma(period1)
            df.add_sma(period2)
            df.add_sma(period3)

        ema = request.GET.get('ema')
        if ema:
            ema_period1 = request.GET.get('emaPeriod1')
            ema_period2 = request.GET.get('emaPeriod2')
            ema_period3 = request.GET.get('emaPeriod3')
            if ema_period1:
                period1 = int(ema_period1)
            if ema_period2:
                period2 = int(ema_period2)
            if ema_period3:
                period3 = int(ema_period3)
            if not ema_period1 or period1 < 0:
                period1 = 7
            if not ema_period2 or period2 < 0:
                period2 = 14
            if not ema_period3 or period3 < 0:
                period3 = 50
            df.add_ema(period1)
            df.add_ema(period2)
            df.add_ema(period3)

        bbands = request.GET.get('bbands')
        if bbands:
            str_n = request.GET.get('bbandsN')
            str_k = request.GET.get('bbandsK')
            if str_n:
                n = int(str_n)
            if str_k:
                k = float(str_k)
            if not str_n or n < 0 or n is None:
                n = 20
            if not str_k or k < 0 or k is None:
                k = 2.0
            df.add_bbands(n, k)

        rsi = request.GET.get('rsi')
        if rsi:
            str_period = request.GET.get('rsiPeriod')
            str_high = request.GET.get('rsiHigh')
            str_low = request.GET.get('rsiLow')
            if str_period:
                period = int(str_period)
            else:
                period = 14
            if str_high:
                high = int(str_high)
            else:
                high = 70
            if str_low:
                low = int(str_low)
            else:
                low = 30
            df.add_rsi(period, high, low)

        macd = request.GET.get('macd')
        if macd:
            macd_period1 = request.GET.get('macdPeriod1')
            macd_period2 = request.GET.get('macdPeriod2')
            macd_period3 = request.GET.get('macdPeriod3')
            if macd_period1:
                period1 = int(macd_period1)
            if macd_period2:
                period2 = int(macd_period2)
            if macd_period3:
                period3 = int(macd_period3)
            if not macd_period1 or period1 < 0:
                period1 = 12
            if not macd_period2 or period2 < 0:
                period2 = 26
            if not macd_period3 or period3 < 0:
                period3 = 9
            df.add_macd(period1, period2, period3)

        events = request.GET.get('events')
        if events:
            if set.back_test:
                df.events = stream.ai.signal_events
            else:
                df.add_events(df.candles[0].time)

        return JsonResponse({
            'product_code': df.value['product_code'],
            'duration': df.value['duration'],
            'candles': df.value['candles'],
            'smas': df.value['smas'],
            'emas': df.value['emas'],
            'bbands': df.value['bbands'],
            'rsi': df.value['rsi'],
            'macd': df.value['macd'],
            'events': df.value['events'],
        })