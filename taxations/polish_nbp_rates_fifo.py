import datetime
import os
import re
import tempfile
from decimal import Decimal as D
from functools import cached_property
from pathlib import Path

import requests

from taxations.base_taxation import BaseTaxation
from tradelog import TradeRecord, STOCK_EXCHANGE_COUNTRIES
from utils import read_csv_file, logger


class PolishNbpRatesFIFO(BaseTaxation):
    """
    Calculate using official National Bank exchange rates.

    For closed position executes first-in, first-out.
    Counts open value and close value separately, adjusted to PLN.

    https://dnarynkow.pl/jak-rozliczyc-podatek-od-dywidendy-i-zysku-z-inwestycji-w-spolki-zagraniczne/
    https://inwestomat.eu/jak-rozliczyc-podatek-z-gieldy/

    PIT-Z/G
        - dla kraju każdej giełdy na której handlowaliśmy!!!
        - jeśli nie było DOCHODU nie trzeba dla tego kraju składać ZG ale w PIT38 i tak trzeba przychod i koszt uwzglednic
        - tylko kwota dochodu wpisana (różnica pomiędzy sprzedaza a kupnem - prowizja), bez zaokraglenia do pelnych
        - dodac do PIT38 czesc C, oddzielic z pit8c (w czesci 1 pit8c)
        - TODO: prowizje uwzględnić w ZG razem z kosztem na bycia per instrumenty
        - wymiany waluty nie uwzględniać
        - w PIT38 kwoty z Z/G idą do pozycji drugiej
    """

    RATES_URL_TEMPLATE = "https://www.nbp.pl/kursy/Archiwum/archiwum_tab_a_{}.csv"
    BASE_CURRENCY = "PLN"
    SUPPORTED_CURRENCIES = {
        "EUR": 1,
        "USD": 1,
        "RUB": 1,
        "CHF": 1,
    }
    TAX_RATE = D("0.19")

    def __init__(self, *args, **kwargs):
        super(PolishNbpRatesFIFO, self).__init__(*args, **kwargs)

    @property
    def summary(self) -> str:
        total_transaction_costs_and_fees = (
            self.total_transaction_cost + self.total_costs
        )
        profit = self.total_transaction_income - total_transaction_costs_and_fees

        return (
            f"\n=Total Transactions closed      = {self.total_transaction_income} {self.BASE_CURRENCY} (PIT przychod)"
            f"\n=Total Transactions open & fees = {total_transaction_costs_and_fees} {self.BASE_CURRENCY} (PIT koszt)"
            f"\n=Total Transactions open        = {self.total_transaction_cost} {self.BASE_CURRENCY}"
            f"\n=Fees and Costs                 = {self.total_costs} {self.BASE_CURRENCY}"
            f"\n=Profit/Loss including costs    = {profit} {self.BASE_CURRENCY}"
            f"\n=Total Transactions owed tax    = {self.total_transaction_owed_tax} {self.BASE_CURRENCY}"
            f"\n========  DIVIDENDS  ==========================="
            f"\n=Total Dividend value           = {self.total_dividend_value} {self.BASE_CURRENCY} (PIT dywidendy otrzymane brutto)"
            f"\n=Total Dividend withholding tax = {round(self.total_dividend_withholding_tax, 2)} {self.BASE_CURRENCY} (PIT podatek u zrodla)"
            f"\n=Total Dividend owed tax        = {round(self.total_dividend_owed_tax, 2)} {self.BASE_CURRENCY} (PIT podatek nalezny)"
            f"\n========  PIT ZG ==============================="
            f"{self.summary_pit_zg}"
            f"\n !!!!!!!!!! COUNT BOSSA DIVIDENDS"
        )

    @property
    def summary_pit_zg(self) -> str:
        zgs = []
        for country, details in self.per_country_trades_breakdown.items():
            profit = details["income"] - details["cost"]
            msg = f"\n={country} profit: {profit}"
            if profit > 0:
                msg += " (form required)"
            zgs.append(msg)
        return "".join(zgs)

    @property
    def total_transaction_owed_tax(self):
        profit = (
            self.total_transaction_income
            - self.total_transaction_cost
            - self.total_costs
        )
        return round(self.TAX_RATE * max(profit, 0))

    @cached_property
    def rates(self):
        rates_by_date = {}

        # For early January transactions rates from previous tax year needed
        for tax_year in range(2020, self.tax_year + 1):
            url = self.RATES_URL_TEMPLATE.format(tax_year)
            saved_file = tempfile.gettempdir() / Path(f"nbp_rates_{tax_year}.csv")

            if not os.path.exists(saved_file):
                logger.info(
                    f"NBP Rates file not found, fetching {url} into {saved_file}"
                )
                r = requests.get(url)
                with open(saved_file, "wb") as f:
                    f.write(r.content)

            for row in read_csv_file(saved_file, delimiter=";", cols_to_lower=False):
                date = row["data"]
                if not re.match(r"^\d{8}$", date):
                    continue
                date = datetime.date(int(date[:4]), int(date[4:6]), int(date[6:8]))
                rates_by_date[date] = {}
                for currency_code, multiplier in self.SUPPORTED_CURRENCIES.items():
                    try:
                        rate = row[f"{multiplier}{currency_code}"].replace(",", ".")
                    except KeyError:
                        rate = None

                    if not rate:
                        logger.debug(
                            f"No rate found for {currency_code} on {date.isoformat()})"
                        )
                        continue
                    rates_by_date[date][currency_code] = D(rate)

        # Fill missing dates for faster processing
        min_date = min(rates_by_date.keys())
        max_date = max(rates_by_date.keys())
        cur_date = min_date
        while cur_date < max_date:
            cur_date += datetime.timedelta(days=1)
            if cur_date not in rates_by_date:
                rates_by_date[cur_date] = rates_by_date[
                    cur_date - datetime.timedelta(days=1)
                ]

        return rates_by_date

    def exchange(self, currency: str, value: D, date: datetime.date) -> D:
        if currency == "PLN":
            return value
        exchange_rate = self.rates[date - datetime.timedelta(days=1)][currency]
        return round(exchange_rate * value, 2)

    def add_closed_transaction(self, open_trade: TradeRecord, close_trade: TradeRecord):
        assert close_trade.timestamp.year == self.tax_year

        closed_quantity = min(close_trade.quantity, open_trade.quantity)

        value_open = self.exchange(
            open_trade.currency,
            open_trade.price * closed_quantity * open_trade.multiplier,
            open_trade.timestamp.date(),
        )
        value_close = self.exchange(
            close_trade.currency,
            close_trade.price * closed_quantity * close_trade.multiplier,
            close_trade.timestamp.date(),
        )

        # Support shorts
        if open_trade.side == TradeRecord.SELL:
            value_open, value_close = value_close, value_open

        value_open = round(value_open, 2)
        value_close = round(value_close, 2)
        commissions = round(
            self.exchange(
                close_trade.currency,
                close_trade.commission,
                close_trade.timestamp.date(),
            ),
            2,
        ) + round(
            self.exchange(
                open_trade.currency, open_trade.commission, open_trade.timestamp.date()
            ),
            2,
        )

        self.per_position_profit[open_trade.symbol] = (
            self.per_position_profit.get(open_trade.symbol, 0)
            + value_close
            - value_open
        )
        self.per_country_trades_breakdown[
            STOCK_EXCHANGE_COUNTRIES[open_trade.exchange]
        ]["cost"] += (value_open + commissions)
        self.per_country_trades_breakdown[
            STOCK_EXCHANGE_COUNTRIES[open_trade.exchange]
        ]["income"] += value_close

        self.total_transaction_cost += value_open
        self.total_transaction_income += value_close

    def add_dividend(self, symbol, currency, value, date, withholding_tax_value):
        assert date.year == self.tax_year

        dividend_income = D(round(self.exchange(currency, value, date)))
        model_tax = abs(round(dividend_income * self.TAX_RATE, 2))
        paid_tax = abs(round(self.exchange(currency, withholding_tax_value, date), 2))
        owed_tax = model_tax - paid_tax

        paid_tax_rate = round(100 * paid_tax / dividend_income)
        # TODO - remove hack, if we paid 30% with tax in us we gotta pay 4% anyway XD
        if paid_tax_rate == 30:
            owed_tax = round(D("0.4") * dividend_income, 2)
        logger.info(
            f"Dividend: {date.isoformat()} {symbol} {dividend_income} ({value} {currency}) tax: {paid_tax} ({paid_tax_rate}%) /{model_tax} ({100 * self.TAX_RATE}%)"
        )

        self.total_dividend_value += dividend_income
        self.total_dividend_withholding_tax += paid_tax
        self.total_dividend_owed_tax += owed_tax

    def add_cost(self, currency: str, value: D, date: datetime.date) -> None:
        assert date.year == self.tax_year

        cost_value = round(self.exchange(currency, abs(value), date), 2)
        self.total_costs += cost_value
