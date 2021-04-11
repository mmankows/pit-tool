from taxations.base_taxation import BaseTaxation


class BaseReport:
    def __init__(self, tax_year: int) -> None:
        self.tax_year = tax_year

    def calculate(self, taxation: BaseTaxation, filename: str) -> None:
        raise NotImplementedError()