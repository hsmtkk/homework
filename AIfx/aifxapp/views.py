from datetime import datetime

from django.views import generic
from .models import UsdJpy1M, UsdJpy5M, UsdJpy15M

import constants
import set
from oanda.oanda import Ticker
# Create your views here.


class IndexView(generic.TemplateView):
    template_name = 'chart.html'


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
    current_candle = cls.objects.get(ticker_time)
    price = ticker.mid_price

    if current_candle is None:
        cls.objects.create(ticker_time, price, price, price, price, ticker.volume).save()
        return True

    if current_candle.high <= price:
        current_candle.high = price
    elif current_candle.low >= price:
        current_candle.low = price

    current_candle.volume += ticker.volume
    current_candle.close = price
    current_candle.save()
    return False


now1 = datetime.timestamp(datetime(2020, 1, 1, 1, 0, 0))
now2 = datetime.timestamp(datetime(2020, 1, 1, 1, 0, 1))
now3 = datetime.timestamp(datetime(2020, 1, 1, 1, 0, 2))
now4 = datetime.timestamp(datetime(2020, 1, 1, 1, 1, 0))

ticker = Ticker(set.product_code, now1, 100, 100, 1)
create_candle_with_duration(set.product_code, '1m', ticker)