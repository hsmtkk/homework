from oandapyV20 import API
from oandapyV20.endpoints.pricing import PricingStream

import set


accountID = set.account_id
api = API(access_token=set.access_token)
params = {
    'instruments': set.product_code,
}

r = PricingStream(accountID=accountID, params=params)
for res in api.request(r):
    print(res)