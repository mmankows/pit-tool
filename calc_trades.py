#!/bin/env python3
import argparse
import logging
from datetime import datetime

from reports import SUPPORTED_REPORTS
from tradelog import TradeLog
from utils import load_nbp_rates


def main():
    """
    Example usage:
    ./calc_trades.py --year 2020 --log DEBUG --type exante_trades_report ~/Documents/exante_trades_only_2020.csv
    """
    parser = argparse.ArgumentParser(
        description='Extend csv file with official rates and calculate rates in selected currency.'
    )
    parser.add_argument('input_csv')
    parser.add_argument('--type',
                        help=f"Provide report type, supported reports: {SUPPORTED_REPORTS.keys()}",
                        choices=list(SUPPORTED_REPORTS.keys()),
                        ),
    parser.add_argument('--year', type=int, default=datetime.now().year - 1)
    parser.add_argument('--log', type=str, help="Log level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO")

    args = parser.parse_args()
    tax_year = args.year
    logging.basicConfig(level=getattr(logging, args.log))
    config = SUPPORTED_REPORTS[args.type]

    rates = load_nbp_rates(tax_year)
    trade_log = TradeLog(rates, config)
    trade_log.load_from_file(args.input_csv)
    trade_log.calculate_closed_positions(tax_year)


if __name__ == '__main__':
    main()
