#!/bin/env python3
import argparse
import logging
from datetime import datetime

from reports import SUPPORTED_REPORTS
from taxations import SUPPORTED_TAXATIONS
from tradelog import TradeLog


def main():
    """
    Example usage:
    ./calc_trades.py --year 2020 --log DEBUG --type EXANTE_TRADES --tax PL_NBP_FIFO ~/Documents/exante_trades_only_2020.csv
    """

    parser = argparse.ArgumentParser(
        description='Extend csv file with official rates and calculate rates in selected currency.'
    )
    parser.add_argument('input_csv')
    parser.add_argument('--type',
                        help=f"Provide report type, supported reports: {SUPPORTED_REPORTS.keys()}",
                        choices=list(SUPPORTED_REPORTS.keys()),
                        ),
    parser.add_argument('--tax',
                        help=f"Provide taxation method, supported: {SUPPORTED_TAXATIONS.keys()}",
                        choices=list(SUPPORTED_REPORTS.keys()),
                        default="PL_NBP_FIFO"
                        ),
    parser.add_argument('--year', type=int, default=datetime.now().year - 1)
    parser.add_argument('--log', type=str, help="Log level", choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO")

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log))

    tax_year = args.year
    report = SUPPORTED_REPORTS[args.type](tax_year)
    taxation = SUPPORTED_TAXATIONS[args.tax](tax_year)

    report.calculate(taxation, args.input_csv)


if __name__ == '__main__':
    main()
