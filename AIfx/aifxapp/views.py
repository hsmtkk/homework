import logging
from threading import Thread
import numpy as np
import talib

from .models import UsdJpy1M, UsdJpy5M, UsdJpy15M
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
    print(current_candle)

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

    def set_all_candles(self, limit=1000):
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


""" main """


def index(request):
    df = DataFrameCandle(set.product_code, set.trade_duration)
    df.set_all_candles(set.past_period)
    context = {
        'candles': df.value['candles'],
    }
    return render(request, 'chart.html', context)


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

        return JsonResponse({
            'product_code': df.value['product_code'],
            'duration': df.value['duration'],
            'candles': df.value['candles'],
            'smas': df.value['smas'],
        })