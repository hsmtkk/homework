import configparser

from utils.utils import str_bool


ini = configparser.ConfigParser()
ini.read('set.ini')

account_id = ini['oanda']['account_id']
access_token = ini['oanda']['access_token']
product_code = ini['oanda']['product_code']

trade_duration = ini['trading']['trade_duration'].lower()
back_test = str_bool(ini['trading']['back_test'])
use_percent = float(ini['trading']['use_percent'])
past_period = int(ini['trading']['past_period'])
stop_limit_percent = float(ini['trading']['stop_limit_percent'])
num_ranking = int(ini['trading']['num_ranking'])

db_name = ini['db']['name']
db_user = ini['db']['user']
db_pass = ini['db']['password']