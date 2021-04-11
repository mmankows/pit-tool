import requests
import os
import datetime
from decimal import Decimal as D
import re

from cached_property import cached_property

from taxations.base_taxation import BaseTaxation
from tradelog import TradeRecord
from utils import read_csv_file


class PolishNbpRatesFIFO(BaseTaxation):
    """
    Calculate using official National Bank exchange rates.

    For closed position executes first-in, first-out.
    Counts open value and close value separately, adjusted to PLN.
    """
    RATES_URL_TEMPLATE = 'https://www.nbp.pl/kursy/Archiwum/archiwum_tab_a_{}.csv'
    SUPPORTED_CURRENCIES = {
        'EUR': 1,
        'USD': 1,
        'RUB': 1,
        'CHF': 1,
    }

    @cached_property
    def rates(self):
        url = self.RATES_URL_TEMPLATE.format(self.tax_year)
        saved_file = f'temp/nbp_rates_{self.tax_year}.csv'

        if not os.path.exists(saved_file):
            r = requests.get(url)
            with open(saved_file, 'wb') as f:
                f.write(r.content)

        rates_by_date = {}

        for row in read_csv_file(saved_file, delimiter=';'):
            date = row["data"]
            if not re.match(r'^\d{8}$', date):
                continue
            date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
            rates_by_date[date] = {
                currency_code: D(row[f"{multiplier}{currency_code}"].replace(',', '.'))
                for currency_code, multiplier in self.SUPPORTED_CURRENCIES.items()
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

    def exchange(self, currency: str, value: D, date: datetime.date) -> D:
        exchange_rate = self.rates[date - datetime.timedelta(days=1)][currency]
        return exchange_rate * value

    def calculate_closed_transaction_value(self, open_trade: TradeRecord, close_trade: TradeRecord):
        closed_quantity = min(close_trade.quantity, open_trade.quantity)

        value_open = round(self.exchange(
            open_trade.currency,
            open_trade.price * closed_quantity * open_trade.multiplier,
            open_trade.timestamp.date()
        ), 2)
        value_close = round(self.exchange(
            close_trade.currency,
            close_trade.price * closed_quantity * close_trade.multiplier,
            close_trade.timestamp.date()
        ), 2)

        # Support shorts
        if open_trade.side == TradeRecord.SELL:
            value_open, value_close = value_close, value_open

        # Only closed in given tax year generate profit/loss
        if close_trade.timestamp.year != self.tax_year:
            value_open = 0
            value_close = 0

        profit = value_close - value_open

        return value_open, value_close, profit
