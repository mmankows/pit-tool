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
    column_type = 'Operation type'
    column_asset = 'Asset'
    column_value = 'Sum'
    column_timestamp = 'When'
    type_dividend = "DIVIDEND"
    type_dividend_tax = "TAX"
    type_commission = "COMMISSION"
    type_interest = "INTEREST"

    def calculate(self, taxation, filename):
        total_costs = 0
        for row in read_csv_file(filename):
            operation_type = row[self.column_type]
            value = D(row[self.column_value])
            timestamp = parse(row[self.column_timestamp])

            if timestamp.year != self.tax_year:
                continue

            if operation_type in {self.type_commission, self.type_interest}:
                currency = row[self.column_asset]
                total_costs += round(taxation.exchange(currency, value, timestamp.date()), 2)

        logger.info(f"Total INTEREST and COMMISSION costs: {total_costs}")
