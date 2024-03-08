import csv
import logging
from decimal import Decimal as D

from dateutil.parser import parse

from reports.base_report import BaseReport
from utils import read_csv_file

logger = logging.getLogger("exante_all_transactions")


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

    column_account = "Account ID".lower()
    column_symbol = "Symbol ID".lower()
    column_type = "Operation type".lower()
    column_asset = "Asset".lower()
    column_value = "Sum".lower()
    column_timestamp = "When".lower()
    column_comment = "Comment".lower()
    comment_tax_recalc = "US TAX recalculation"
    type_dividend = "DIVIDEND"
    type_dividend_tax = ("TAX", "US TAX")
    type_commission = "COMMISSION"
    type_interest = "INTEREST"

    @classmethod
    def sniff(cls, filename):
        try:
            sample_row = next(read_csv_file(filename))
        except csv.Error:
            return False

        logger.debug("Sample header row: {}".format(sample_row))

        return all(
            column.lower() in sample_row
            for column in (
                cls.column_account,
                cls.column_timestamp,
                cls.column_type,
                cls.column_value,
            )
        )

    def process(self, taxation, filename):
        dividends_details = {}
        for row in read_csv_file(filename):
            operation_type = row[self.column_type]
            value = D(row[self.column_value])
            timestamp = parse(row[self.column_timestamp])
            comment = row[self.column_comment]
            key = f"{row[self.column_symbol]}@{row[self.column_account]}:{timestamp.date().isoformat()}"

            # Minor tax corrections for previous year are possible, skip if below $0.1
            if self.comment_tax_recalc in comment and abs(value) < D("0.1"):
                continue

            if timestamp.year != self.tax_year:
                continue

            # Calculate total costs
            elif operation_type in {self.type_commission, self.type_interest}:
                currency = row[self.column_asset]
                taxation.add_cost(currency, value, timestamp.date())

            # Collect dividends and taxes
            elif operation_type == self.type_dividend:
                dividends_details.setdefault(key, {})
                dividends_details[key].update(
                    {
                        "symbol": key,
                        "value": value,
                        "date": timestamp.date(),
                        "currency": row[self.column_asset],
                    }
                )

            elif operation_type in self.type_dividend_tax:
                dividends_details.setdefault(key, {})
                dividends_details[key].update(
                    {
                        "withholding_tax_value": value,
                    }
                )

        # Summarize dividends
        for dividend_name, details in dividends_details.items():
            taxation.add_dividend(**details)
