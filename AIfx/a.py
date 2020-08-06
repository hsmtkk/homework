from datetime import datetime

from oandapyV20 import API
from oandapyV20.endpoints.pricing import PricingStream
from aifxapp.views import create_candle_with_duration
from oanda.oanda import Ticker

import set


# accountID = set.account_id
# api = API(access_token=set.access_token)
# params = {
#     'instruments': set.product_code,
# }
#
# r = PricingStream(accountID=accountID, params=params)
# for res in api.request(r):
#     print(res)

if __name__ == '__main__':
    now1 = datetime.timestamp(datetime(2020, 1, 1, 1, 0, 0))
    now2 = datetime.timestamp(datetime(2020, 1, 1, 1, 0, 0))

    ticker = Ticker(set.product_code, now1, 100, 100, 1)
    create_candle_with_duration(set.product_code, '1m', ticker)