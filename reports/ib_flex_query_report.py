import datetime

from decimal import Decimal as D
import xml.etree.ElementTree as ET

from dateutil.parser import parse

from reports.base_report import BaseReport
from tradelog import TradeRecord, InstrumentType
from utils import logger


class IBFlexQueryReport(BaseReport):
    """
    Create FLEX Query and select custom range for last tax year
    - "Change in Dividend Accruals" - all fields
    - "Trades" - all fields
    - "Interest Accruals" - all fields
    - TODO: ? "Commission Details" - all fields
    - TODO - detect splits?
    """

    instrument_type_map = {
        "STK": InstrumentType.STOCK,
        "FXCFD": InstrumentType.FOREX,
        "OPT": InstrumentType.OPTION,
        "CASH": InstrumentType.CASH,
    }

    @classmethod
    def sniff(cls, filename):
        try:
            with open(filename) as file:
                return 'FlexQueryResponse' in file.read(50)
        except UnicodeDecodeError:
            return False

    def process(self, taxation, filename):
        tree = ET.parse(filename)
        self.calculate_transactions_and_commissions(tree, taxation)
        self.calculate_comissions_and_borrowing_fees(tree, taxation)
        self.calculate_dividends(tree, taxation)

    def get_splits(self):
        # TODO - detect automatically:
        return {
            'REMX': [
                (datetime.date(2020, 4, 15), 3, 1), # https://stooq.pl/q/m/?s=remx.us
             ],
            'URNM': [
                (datetime.date(2022, 12, 21), 1, 2), # https://stooq.pl/q/m/?s=urnm.us
            ],
        }

    def calculate_transactions_and_commissions(self, tree, taxation):
        splits = self.get_splits()

        for trade in tree.findall('.//Trade'):
            attrs = trade.attrib
            instrument = self.instrument_type_map.get(attrs['assetCategory'], attrs['assetCategory'])
            if instrument not in {InstrumentType.OPTION, InstrumentType.STOCK, InstrumentType.FOREX}:
                logger.warning(f"Unsupported instument type: {instrument}, skipping.")
                continue

            side_modifier = TradeRecord.BUY if attrs['buySell'] == 'BUY' else TradeRecord.SELL
            symbol = attrs['symbol']
            quantity = abs(D(attrs['quantity']))
            price = D(attrs['tradePrice'])
            timestamp = parse(attrs['dateTime'])

            # TODO - fix splits
            for split_date, rate_from, rate_to in splits.get(symbol, []):
                if timestamp.date() > split_date:
                    logger.warning(f"SPLIT DETECTED! {rate_from}:{rate_to} {price}, {quantity}")
                    price = price * rate_to / rate_from
                    quantity = int(quantity * rate_from / rate_to)
                    logger.warning(f"SPLIT DONE! {rate_from}:{rate_to} {price}, {quantity}")

            assert attrs['ibCommissionCurrency'] == attrs['currency']

            exchange = attrs['listingExchange'] or attrs['underlyingListingExchange']
            exchange = exchange.split('.')[0]
            account_id = "IB" + attrs['accountId'][-5:]  # only last 5 bcs of Lynx accounts migration
            self.trade_log.add_record(TradeRecord(
                symbol=symbol,
                exchange=exchange,
                account=account_id,
                quantity=quantity,
                price=price,
                currency=attrs['currency'],
                timestamp=timestamp,
                side=side_modifier,
                instrument=instrument,
                commission=abs(D(attrs['ibCommission'])),
            ))

    def calculate_comissions_and_borrowing_fees(self, tree, taxation):
        for fee in tree.findall('.//UnbundledCommissionDetail'):
            attrs = fee.attrib
            fee_date = parse(attrs['dateTime']).date()
            if fee_date.year == self.tax_year:
                taxation.add_cost(
                    value=D(attrs['totalCommission']),
                    currency=attrs['currency'],
                    date=fee_date,
                )

        # TODO - assuming base currency is PLN
        interests_accurals_base = tree.find('.//InterestAccrualsCurrency[@currency="BASE_SUMMARY"]')
        fee_date = parse(interests_accurals_base.attrib['toDate']).date()
        if fee_date.year == self.tax_year:
            taxation.add_cost(
                value=D(interests_accurals_base.attrib['accrualReversal']),
                currency='PLN',
                date=fee_date,
            )

    def calculate_dividends(self, tree, taxation):
        recorded_dividends = {}
        for dividend in tree.findall('.//ChangeInDividendAccrual'):
            attrs = dividend.attrib
            pay_date = parse(attrs['payDate']).date()
            value = D(attrs['grossAmount'])
            tax = D(attrs['tax'])

            # Only current tax rate
            if pay_date.year != self.tax_year:
                continue

            # Exclude reversals
            if attrs['code'] != 'Po':
                continue

            # IB reports have nasty duplicates
            dividend_key = (attrs['symbol'], abs(value), pay_date)
            if dividend_key in recorded_dividends:
                logger.debug(f"Dividend {dividend_key} already recorded - skipping")
                continue
            else:
                recorded_dividends[dividend_key] = True

            # Real dividend
            if value > 0:
                taxation.add_dividend(
                    symbol=attrs['symbol'],
                    value=value,
                    currency=attrs['currency'],
                    date=pay_date,
                    withholding_tax_value=tax,
                )
            else:
                # dividend on short position paid to lender, count as cost
                taxation.add_cost(
                    value=abs(value),
                    currency=attrs['currency'],
                    date=pay_date,
                )
