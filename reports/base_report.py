from taxations.base_taxation import BaseTaxation


class BaseReport:
    """
    Report class parse and recognize tax incurring events and calls relevant
    taxation event handler
    """
    def __init__(self, tax_year: int) -> None:
        self.tax_year = tax_year

    def process(self, taxation: BaseTaxation, filename: str) -> None:
        """Start report processing."""
        raise NotImplementedError()
