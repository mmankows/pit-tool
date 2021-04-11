from decimal import Decimal as D
import datetime

from tradelog import TradeRecord


class BaseTaxation:
    def __init__(self, tax_year: int) -> None:
        self.tax_year = tax_year

    @property
    def summary(self) -> str:
        """Returns formatted summary."""
        raise NotImplementedError()

    def exchange(self, currency: str, value: D, date: datetime.date) -> D:
        """Convert to taxation base currency for given event date."""
        raise NotImplementedError()

    def add_closed_transaction(self, open_trade: TradeRecord, close_trade: TradeRecord):
        """Calculate profit/lose between open and close trades."""
        raise NotImplementedError()

    def add_dividend(
            self,
            symbol: str,
            currency: str,
            value: D,
            date: datetime.date,
            withholding_tax_value: D
    ) -> None:
        """Calculate dividend income and tax."""
        raise NotImplementedError()

    def add_cost(self, currency: str, value: D, date: datetime.date) -> None:
        """Record cost."""
        raise NotImplementedError()