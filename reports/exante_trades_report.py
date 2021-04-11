from typing import Optional

from decimal import Decimal as D
from dateutil.parser import parse

from tradelog import TradeRecord, InstrumentType
from utils import logger


class ExanteTradesReport:
    """
    Designed to handle exante Trades report format.

    Known limitations:
    1) Only STOCK and OPTION trades are currently supported
    2) Stock splits/merge must be handled manually in report file by adjusting position size
      to match split/merge size and price has to be adjusted according to real price
      dividing Traded Volume by adjusted position size.

    """
    column_timestamp = 'Time'
    column_price = 'Price'
    column_quantity = 'Quantity'
    column_account = 'Account ID'
    column_currency = 'Currency'
    column_instrument = 'Symbol ID'
    column_side = 'Side'
    column_type = 'Type'
    side_buy = 'buy'
    side_sell = 'sell'

    instrument_map = {
        "STOCK": InstrumentType.STOCK,
        "OPTION": InstrumentType.OPTION,
    }

    @classmethod
    def get_trade_log_record(cls, row) -> Optional[TradeRecord]:
        # Skip pure asset rows and different transaction types
        instrument_type = cls.instrument_map.get(row[cls.column_type])
        if instrument_type not in {InstrumentType.STOCK, InstrumentType.OPTION}:
            logger.warning(f"Unsupported instument type: {row[cls.column_type]}, skipping.")
            return

        side_modifier = 1 if row[cls.column_side] == cls.side_buy else -1
        return TradeRecord(
            symbol=f"{row[cls.column_instrument]}@{row[cls.column_account]}",
            quantity=int(row[cls.column_quantity]),
            price=D(row[cls.column_price]),
            currency=row[cls.column_currency],
            timestamp=parse(row[cls.column_timestamp]),
            side=side_modifier,
            instrument=instrument_type,
        )
