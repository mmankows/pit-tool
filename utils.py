import logging

import requests
import csv
import os
import datetime
from decimal import Decimal as D
import re
import chardet


logger = logging.getLogger()


SUPPORTED_CURRENCIES = {
    'EUR': 1,
    'USD': 1,
    'RUB': 1,
    'CHF': 1,
}


def get_file_encoding(filename):
    with open(filename, 'rb') as f:
        result = chardet.detect(f.read(5000))
        return result['encoding']


def load_nbp_rates(year):
    url = f'https://www.nbp.pl/kursy/Archiwum/archiwum_tab_a_{year}.csv'
    saved_file = f'temp/nbp_rates_{year}.csv'

    if not os.path.exists(saved_file):
        r = requests.get(url)
        with open(saved_file, 'wb') as f:
            f.write(r.content)

    rates_by_date = {}
    with open(saved_file, encoding=get_file_encoding(saved_file)) as f:
        reader = csv.DictReader(f, delimiter=';')
        for row in reader:
            date = row["data"]
            if not re.match(r'^\d{8}$', date):
                continue
            date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
            rates_by_date[date] = {
                currency_code: D(row[f"{multiplier}{currency_code}"].replace(',', '.'))
                for currency_code, multiplier in SUPPORTED_CURRENCIES.items()
            }

    # Fill missing dates for faster processing
    min_date = min(rates_by_date.keys())
    max_date = max(rates_by_date.keys())
    cur_date = min_date
    while cur_date < max_date:
        cur_date += datetime.timedelta(days=1)
        if cur_date not in rates_by_date:
            rates_by_date[cur_date] = rates_by_date[cur_date - datetime.timedelta(days=1)]

    return rates_by_date
