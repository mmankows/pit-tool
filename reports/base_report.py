from typing import TYPE_CHECKING

from taxations.base_taxation import BaseTaxation

if TYPE_CHECKING:
    from tradelog import TradeLog


class BaseReport:
    """
    Report class parse and recognize tax incurring events and calls relevant
    taxation event handler
    """

    def __init__(self, trade_log: "TradeLog", tax_year: int) -> None:
        self.trade_log = trade_log
        self.tax_year = tax_year

    @classmethod
    def sniff(cls, filename) -> bool:
        """Rule out if file is an instance of this report."""
        raise NotImplementedError()

    def process(self, taxation: BaseTaxation, filename: str) -> None:
        """Start report processing."""
        raise NotImplementedError()
