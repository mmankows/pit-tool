from decimal import Decimal as D
import datetime
from tradelog import TradeRecord


class BaseTaxation:
    def __init__(self, tax_year: int) -> None:
        self.tax_year = tax_year

    def exchange(self, currency: str, value: D, date: datetime.date) -> D:
        """Convert to taxation base currency for given event date."""
        raise NotImplementedError()

    def calculate_closed_transaction_value(self, open_trade: TradeRecord, close_trade: TradeRecord) -> tuple:
        """Calculate profit/lose between open and close trades."""
        raise NotImplementedError()
