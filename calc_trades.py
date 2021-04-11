#!/bin/env python3
import argparse
import logging
from datetime import datetime

from reports import SUPPORTED_REPORTS, sniff_report_type
from taxations import SUPPORTED_TAXATIONS
from utils import logger


def main():
    """
    Example usage:
    ./calc_trades.py --year 2020 --log DEBUG --type EXANTE_TRADES --tax PL_NBP_FIFO ~/Documents/exante_trades_only_2020.csv
    """

    parser = argparse.ArgumentParser(
        description='Extend csv file with official rates and calculate rates in selected currency.'
    )
    parser.add_argument('input_csv', nargs='+')
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

    taxation = SUPPORTED_TAXATIONS[args.tax](tax_year)

    for input_file_path in args.input_csv:
        report_type = sniff_report_type(input_file_path)
        logger.info(f"Parsing {input_file_path}, identified report type {report_type}")

        report = SUPPORTED_REPORTS[report_type](tax_year)
        report.process(taxation, input_file_path)

    logger.info(taxation.summary)
    # logger.info(f"{taxation}")


if __name__ == '__main__':
    main()
