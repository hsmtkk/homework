import logging
from threading import Thread
import datetime

import numpy as np
import talib

from .models import UsdJpy1M, UsdJpy5M, UsdJpy15M, SignalEvent
from django.shortcuts import render
from django.http.response import JsonResponse

import constants
import set
from oanda.oanda import APIClient
from oanda.oanda import Ticker
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


"""indicator"""


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


"""real time ticker"""


class StreamData(object):

    def stream_data(self):
        api.get_realtime_ticker(callback=self.trade)

    def trade(self, ticker: Ticker):
        logger.info(f'trade ticker:{ticker.__dict__}')
        for duration in constants.DURATIONS:
            created = create_candle_with_duration(ticker.product_code, duration, ticker)
            print(created)


stream = StreamData()


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
        signal_events = get_signal_events_after_time(time)
        if len(signal_events) > 0:
            self.events = signal_events
            return True
        return False


""" signal event """


def get_signal_events_by_count(count, product_code=set.product_code):
    rows = SignalEvent.objects.filter(product_code=product_code == product_code).order_by('-time').limit(count).all()
    if rows is None:
        return []
    rows.reverse()
    return rows


def get_signal_events_after_time(time):
    rows = SignalEvent.objects.filter(time=time >= time).all()
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


""" main """


def candle(request):
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