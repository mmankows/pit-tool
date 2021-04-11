from decimal import Decimal as D
from dateutil.parser import parse

from reports.base_report import BaseReport
from utils import read_csv_file, logger


class ExanteAllTransactions(BaseReport):
    """
    {
        'Transaction ID': '55597951',
        'Account ID': 'LWX00XX.001',
        'Symbol ID': 'EUR/USD.EXANTE',
        'ISIN': 'None',
        'Operation type': 'TRADE',
        'When': '2020-04-06 14:10:00',
        'Sum': '-3766.0',
        'Asset': 'EUR',
        'EUR equivalent':
        '-3766.0',
        'Comment': 'None'
    }
    """
    column_account = 'Account ID'
    column_symbol = 'Symbol ID'
    column_type = 'Operation type'
    column_asset = 'Asset'
    column_value = 'Sum'
    column_timestamp = 'When'
    type_dividend = "DIVIDEND"
    type_dividend_tax = "TAX"
    type_commission = "COMMISSION"
    type_interest = "INTEREST"

    def process(self, taxation, filename):
        dividends_details = {}
        for row in read_csv_file(filename):
            operation_type = row[self.column_type]
            value = D(row[self.column_value])
            timestamp = parse(row[self.column_timestamp])
            key = f"{row[self.column_symbol]}@{row[self.column_account]}:{timestamp.date().isoformat()}"

            if timestamp.year != self.tax_year:
                continue

            # Calculate total costs
            if operation_type in {self.type_commission, self.type_interest}:
                currency = row[self.column_asset]
                taxation.add_cost(currency, value, timestamp.date())
                continue

            # Collect dividends and taxes
            if operation_type == self.type_dividend:
                dividends_details.setdefault(key, {})
                dividends_details[key].update({
                    'symbol': key,
                    'value': D(row[self.column_value]),
                    'date': timestamp.date(),
                    'currency': row[self.column_asset],
                })
                continue

            if operation_type == self.type_dividend_tax:
                dividends_details.setdefault(key, {})
                dividends_details[key].update({
                    'withholding_tax_value': D(row[self.column_value]),
                })

        # Summarize dividends
        for dividend_name, details in dividends_details.items():
            taxation.add_dividend(**details)
