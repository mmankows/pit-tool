import requests
import os
import datetime
from decimal import Decimal as D
import re

from cached_property import cached_property

from taxations.base_taxation import BaseTaxation
from tradelog import TradeRecord
from utils import read_csv_file, logger


class PolishNbpRatesFIFO(BaseTaxation):
    """
    Calculate using official National Bank exchange rates.

    For closed position executes first-in, first-out.
    Counts open value and close value separately, adjusted to PLN.

    https://dnarynkow.pl/jak-rozliczyc-podatek-od-dywidendy-i-zysku-z-inwestycji-w-spolki-zagraniczne/
    """
    RATES_URL_TEMPLATE = 'https://www.nbp.pl/kursy/Archiwum/archiwum_tab_a_{}.csv'
    BASE_CURRENCY = 'PLN'
    SUPPORTED_CURRENCIES = {
        'EUR': 1,
        'USD': 1,
        'RUB': 1,
        'CHF': 1,
    }
    TAX_RATE = D('0.19')

    def __init__(self, *args, **kwargs):
        super(PolishNbpRatesFIFO, self).__init__(*args, **kwargs)
        self.total_dividend_value = 0
        self.total_dividend_owed_tax = 0
        self.total_dividend_withholding_tax = 0
        self.total_transaction_income = 0
        self.total_transaction_cost = 0
        self.total_costs = 0

    @property
    def summary(self) -> str:
        profit = self.total_transaction_income - self.total_transaction_cost - self.total_costs
        return (
              f"\n=Total Transactions open        = {self.total_transaction_cost} {self.BASE_CURRENCY}"
              f"\n=Total Transactions closed      = {self.total_transaction_income} {self.BASE_CURRENCY}"
              f"\n=Total costs                    = {self.total_costs} {self.BASE_CURRENCY}"
              f"\n=Transactions Profit/Loss       = {profit} {self.BASE_CURRENCY}"
              f"\n=Total Dividend value           = {self.total_dividend_value} {self.BASE_CURRENCY}"
              f"\n=Total Dividend withholding tax = {self.total_dividend_withholding_tax} {self.BASE_CURRENCY}"
              f"\n================================================"
              f"\n=Total Dividend owed tax        = {self.total_dividend_owed_tax} {self.BASE_CURRENCY}"
              f"\n=Total Transactions owed tax    = {self.total_transaction_owed_tax} {self.BASE_CURRENCY}"
        )

    @property
    def total_transaction_owed_tax(self):
        profit = self.total_transaction_income - self.total_transaction_cost - self.total_costs
        return round(self.TAX_RATE * max(profit, 0))

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
        return round(exchange_rate * value, 2)

    def add_closed_transaction(self, open_trade: TradeRecord, close_trade: TradeRecord):
        closed_quantity = min(close_trade.quantity, open_trade.quantity)

        value_open = self.exchange(
            open_trade.currency,
            open_trade.price * closed_quantity * open_trade.multiplier,
            open_trade.timestamp.date()
        )
        value_close = self.exchange(
            close_trade.currency,
            close_trade.price * closed_quantity * close_trade.multiplier,
            close_trade.timestamp.date()
        )

        # Support shorts
        if open_trade.side == TradeRecord.SELL:
            value_open, value_close = value_close, value_open

        # Only closed in given tax year generate profit/loss
        if close_trade.timestamp.year != self.tax_year:
            value_open = 0
            value_close = 0

        self.total_transaction_cost += value_open
        self.total_transaction_income += value_close

    def add_dividend(self, symbol, currency, value, date, withholding_tax_value):
        dividend_income = D(round(self.exchange(currency, value, date)))
        model_tax = abs(round(dividend_income * self.TAX_RATE, 2))
        paid_tax = abs(round(self.exchange(currency, withholding_tax_value, date), 2))
        owed_tax = model_tax - paid_tax

        logger.debug(f"Dividend: {date.isoformat()} {symbol} {dividend_income} tax: ({paid_tax}/{model_tax})")

        self.total_dividend_value += dividend_income
        self.total_dividend_withholding_tax += paid_tax
        self.total_dividend_owed_tax += owed_tax

    def add_cost(self, currency: str, value: D, date: datetime.date) -> None:
        cost_value = round(self.exchange(currency, abs(value), date), 2)
        self.total_costs += cost_value
