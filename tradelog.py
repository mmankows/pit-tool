import datetime
from decimal import Decimal as D
from enum import Enum
from typing import List, TYPE_CHECKING

from utils import logger

if TYPE_CHECKING:
    from taxations.base_taxation import BaseTaxation


class InstrumentType(Enum):
    STOCK = "STOCK"
    OPTION = "OPTION"
    CASH = "CASH"
    FOREX = "FOREX"


STOCK_EXCHANGE_COUNTRIES = {
    "ARCA": "US",
    "NASDAQ": "US",
    "AMEX": "US",
    "CBOE": "US",
    "NYSE": "US",
    "BATS": "US",
    "XETRA": "DE",
    "IBIS": "DE",
    "LSE": "DE",
    "SIX": "CH",
    "SBF": "FR",
    "BVME": "IT",  # Borsa italiana
    "WSE": "PL",
    "MOEX": "RU",
    "TMX": "CA",  # Toronto
    "FTA": "US",  # Chicago State Exchange System."
    "FOREX": "FOREX",
}


class TradeRecord:
    BUY = 1
    SELL = -BUY

    def __init__(
        self,
        symbol: str,
        exchange: str,
        account: str,
        quantity: int,
        price: D,
        currency: str,
        timestamp: datetime.datetime,
        side: int,
        instrument: InstrumentType,
        commission: D,
    ):
        self.symbol = symbol
        self.exchange = exchange if instrument != InstrumentType.FOREX else "FOREX"
        self.account = account
        self.quantity = quantity
        self.price = price
        self.currency = currency
        self.timestamp = timestamp
        self.side = side
        self.instrument = instrument
        self.multiplier = 100 if instrument == InstrumentType.OPTION else 1
        self.commission = commission
        assert (
            self.exchange in STOCK_EXCHANGE_COUNTRIES
        ), f"Unknown exchange {self.exchange} for {self.symbol}"

    def __str__(self) -> str:
        return f"<Trade: {self.timestamp.isoformat()} {self.symbol} {self.side * self.quantity}x{self.price}>"

    def __repr__(self) -> str:
        return self.__str__()

    @property
    def key(self):
        """Unique key to match trades in case of multiple sub-accounts."""
        return self.account, self.symbol

    @classmethod
    def format_trades(cls, trades) -> str:
        return "\n\t" + "\n\t".join(map(str, trades))

    def copy(self, **updates) -> "TradeRecord":
        params = dict(
            symbol=self.symbol,
            exchange=self.exchange,
            account=self.account,
            quantity=self.quantity,
            price=self.price,
            currency=self.currency,
            timestamp=self.timestamp,
            side=self.side,
            instrument=self.instrument,
            commission=self.commission,
        )
        params.update(**updates)
        return TradeRecord(**params)


class TradeLog:
    def __init__(self, taxation: "BaseTaxation") -> None:
        self.taxation = taxation
        self.records = {}
        self.outstanding_positions = []
        self.total_cost = self.total_income = 0

    def __str__(self) -> str:
        if self.outstanding_positions:
            return f"= Position left for next tax year: {TradeRecord.format_trades(self.outstanding_positions)}"
        else:
            return "No position left for next tax year."

    def reset_stats(self):
        self.outstanding_positions = []
        self.total_cost = 0
        self.total_income = 0

    def add_record(self, trade_record: TradeRecord) -> None:
        self.records[trade_record.key] = self.records.get(trade_record.key, [])
        self.records[trade_record.key].append(trade_record)

    def calc_profit_fifo(self, trades: List[TradeRecord], tax_year: int):
        """
        Calculates closed transactions profits for given instrument trades history.
        :param trades:
        :param tax_year:
        :return:
        """
        # Don't calculate for past years if all trades closed
        if not any(t.timestamp.year == tax_year for t in trades):
            return

        logger.debug(
            f"Calculating profit for following trades: {TradeRecord.format_trades(trades)}"
        )

        trades_by_side = {
            TradeRecord.BUY: [t for t in trades if t.side == TradeRecord.BUY][::-1],
            TradeRecord.SELL: [t for t in trades if t.side == TradeRecord.SELL][::-1],
        }

        def get_next_trade(cur_trade=None):
            if not (
                trades_by_side[TradeRecord.BUY] or trades_by_side[TradeRecord.SELL]
            ):
                return None

            if cur_trade is None:
                if not trades_by_side[TradeRecord.BUY]:
                    return trades_by_side[TradeRecord.SELL].pop()
                elif not trades_by_side[TradeRecord.SELL]:
                    return trades_by_side[TradeRecord.BUY].pop()
                elif (
                    trades_by_side[TradeRecord.SELL][0].timestamp
                    > trades_by_side[TradeRecord.BUY][0].timestamp
                ):
                    return trades_by_side[TradeRecord.BUY].pop()
                else:
                    return trades_by_side[TradeRecord.SELL].pop()
            else:
                # Get from other side
                try:
                    return trades_by_side[-cur_trade.side].pop()
                except IndexError:
                    return None

        cur_position = 0

        while open_trade := get_next_trade():
            logger.debug(open_trade)
            close_trade = get_next_trade(open_trade)
            # Meaning position stayed
            if not close_trade:
                trades_by_side[open_trade.side].append(open_trade)
                break

            closed_quantity = min(close_trade.quantity, open_trade.quantity)

            # Both sides closed
            if close_trade.quantity == open_trade.quantity:
                pass
            # Sell less than bought, update position
            elif close_trade.quantity < open_trade.quantity:
                trades_by_side[open_trade.side].append(
                    open_trade.copy(quantity=open_trade.quantity - closed_quantity)
                )
            # Sell more than bought, went short
            elif close_trade.quantity > open_trade.quantity:
                trades_by_side[close_trade.side].append(
                    close_trade.copy(quantity=close_trade.quantity - closed_quantity)
                )

            logger.debug(f"{open_trade} x {close_trade}")

            if close_trade.timestamp.year == tax_year:
                self.taxation.add_closed_transaction(open_trade, close_trade)

        # Update stats
        pos_left = trades_by_side[TradeRecord.BUY] + trades_by_side[TradeRecord.SELL]
        pos_left_size_from_trades = sum(t.quantity for t in trades)
        self.outstanding_positions.extend(pos_left)

        assert (
            not trades_by_side[TradeRecord.BUY] or not trades_by_side[TradeRecord.SELL]
        )
        assert not pos_left or pos_left_size_from_trades != 0

        logger.info(
            f"{trades[0].symbol} profit: {self.taxation.per_position_profit.get(trades[0].key, 0)} pos: {pos_left_size_from_trades} {pos_left}"
        )

    def calculate_closed_positions(self, tax_year):
        logger.info(f"Calculating closed positions for tax_year {tax_year}")
        # Only closed in current tax year should be calculated for tax!

        for trades in self.records.values():
            trades = sorted(trades, key=lambda t: t.timestamp)
            self.calc_profit_fifo(trades, tax_year)

        logger.info(f"TOTAL TRADES for {tax_year}:\n{self}")
