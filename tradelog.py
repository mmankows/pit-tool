import datetime
from decimal import Decimal as D
from enum import Enum

from utils import logger, read_csv_file


class InstrumentType(Enum):
    STOCK = "STOCK"
    OPTION = "OPTION"


class TradeRecord:
    BUY = 1
    SELL = -BUY

    def __init__(self,
         symbol: str,
         quantity: int,
         price: D,
         currency: str,
         timestamp: datetime.datetime,
         side: int,
         instrument: InstrumentType,
    ):
        self.symbol = symbol
        self.quantity = quantity
        self.price = price
        self.currency = currency
        self.timestamp = timestamp
        self.side = side
        self.instrument = instrument
        self.multiplier = 100 if self.instrument == InstrumentType.OPTION else 1

    def __str__(self) -> str:
        return f"<Trade: {self.timestamp.isoformat()} {self.symbol} {self.side * self.quantity}x{self.price}>"

    @classmethod
    def format_trades(cls, trades) -> str:
        return "\n\t" + "\n\t".join(map(str, trades))

    def copy(self, **updates) -> "TradeRecord":
        params = dict(
            symbol=self.symbol,
            quantity=self.quantity,
            price=self.price,
            currency=self.currency,
            timestamp=self.timestamp,
            side=self.side,
            instrument=self.instrument,
        )
        params.update(**updates)
        return TradeRecord(**params)


class TradeLog:
    def __init__(self, report, taxation):
        self.report = report
        self.taxation = taxation
        self.records = {}
        self.outstanding_positions = []
        self.total_value_open = self.total_value_close = 0

    def __str__(self) -> str:
        return (
            f"= Value open  : {self.total_value_open}\n"
            f"= Value closed: {self.total_value_close}\n"
            f"= Position left for next tax year: {TradeRecord.format_trades(self.outstanding_positions)}"
        )

    def reset_stats(self):
        self.outstanding_positions = []
        self.total_value_open = 0
        self.total_value_close = 0

    def add_record(self, trade_record: TradeRecord) -> None:
        self.records[trade_record.symbol] = self.records.get(trade_record.symbol, [])
        self.records[trade_record.symbol].append(trade_record)

    def load_from_file(self, filename):
        for row in read_csv_file(filename):
            trade_record = self.report.parse_trade_log_record(row)
            if trade_record:
                self.add_record(trade_record)

    def calc_profit_fifo(self, trades, tax_year):
        """
        Calculates closed transactions profits for given instrument trades history.
        :param trades:
        :param tax_year:
        :return:
        """
        logger.debug(f"Calculating profit for following trades: {TradeRecord.format_trades(trades)}")

        trades_by_side = {
            TradeRecord.BUY: [t for t in trades if t.side == TradeRecord.BUY][::-1],
            TradeRecord.SELL: [t for t in trades if t.side == TradeRecord.SELL][::-1],
        }
        total_open = 0
        total_close = 0

        def get_next_trade(cur_trade=None):
            if not (trades_by_side[TradeRecord.BUY] or trades_by_side[TradeRecord.SELL]):
                return None

            if cur_trade is None:
                if not trades_by_side[TradeRecord.BUY]:
                    return trades_by_side[TradeRecord.SELL].pop()
                elif not trades_by_side[TradeRecord.SELL]:
                    return trades_by_side[TradeRecord.BUY].pop()
                elif trades_by_side[TradeRecord.SELL][0].timestamp > trades_by_side[TradeRecord.BUY][0].timestamp:
                    return trades_by_side[TradeRecord.BUY].pop()
                else:
                    return trades_by_side[TradeRecord.SELL].pop()
            else:
                # Get from other side
                try:
                    return trades_by_side[-cur_trade.side].pop()
                except IndexError:
                    return None

        while open_trade := get_next_trade():
            logger.debug(open_trade)
            close_trade = get_next_trade(open_trade)
            # Meaning position stayed
            if not close_trade:
                trades_by_side[open_trade.side].append(open_trade)
                break

            closed_quantity = min(close_trade.quantity, open_trade.quantity)
            value_open, value_close, profit = self.taxation.calculate_closed_transaction_value(open_trade, close_trade)
            total_open += value_open
            total_close += value_close

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

            logger.debug(f"{close_trade} ~ {open_trade} profit: {profit}")

        # Update stats
        pos_left = trades_by_side[TradeRecord.BUY] + trades_by_side[TradeRecord.SELL]
        self.outstanding_positions.extend(pos_left)
        self.total_value_open += total_open
        self.total_value_close += total_close

        assert not trades_by_side[TradeRecord.BUY] or not trades_by_side[TradeRecord.SELL]
        assert not pos_left or sum(t.quantity for t in trades) != 0

        logger.info(
            f"{trades[0].symbol} tot_open: {total_open} tot_close: {total_close} profit: {total_close - total_open} pos: {pos_left}")

    def calculate_closed_positions(self, tax_year):
        logger.info(f"Calculating closed positions for tax_year {tax_year}")
        # Only closed in current tax year should be calculated for tax!

        for symbol, trades in self.records.items():
            trades = sorted(trades, key=lambda t: t.timestamp)
            self.calc_profit_fifo(trades, tax_year)

        logger.info(f"TOTAL TRADES for {tax_year}:\n{self}")
