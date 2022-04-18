#!/usr/bin/env python3

import argparse
import logging
from datetime import datetime

from reports import SUPPORTED_REPORTS, sniff_report_type
from taxations import SUPPORTED_TAXATIONS
from tradelog import TradeLog
from utils import logger


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description='Calculate tax obligations for popular brokers reports.',
        usage="./calc_trades.py [--tax PL_NBP_FIFO] [--year 2020] [--log DEBUG] file_path1 file_path2 ..."
    )
    parser.add_argument(
        'input_csv_files',
        nargs='+',
        help="list of CSV report files"
    )
    parser.add_argument(
        '--tax',
        help=f"taxation method",
        choices=list(SUPPORTED_TAXATIONS.keys()),
        default="PL_NBP_FIFO"
    ),
    parser.add_argument(
        '--year',
        help='tax year',
        type=int,
        default=datetime.now().year - 1
    )
    parser.add_argument(
        '--log',
        type=str,
        help="log level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO"
    )

    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log))

    taxation = SUPPORTED_TAXATIONS[args.tax](args.year)
    # TODO - get rid of VIXL split! ratio
    # DEBUG:root:Calculating profit for following trades:
    # 	<Trade: 2020-10-28T13:30:24 VIXL.LSE@EXLWX0093.001 200000x0.0053>
    # 	<Trade: 2020-11-09T12:34:04 VIXL.LSE@EXLWX0093.001 -3x128.81>
    # DEBUG:root:<Trade: 2020-10-28T13:30:24 VIXL.LSE@EXLWX0093.001 200000x0.0053>
    # DEBUG:root:<Trade: 2020-11-09T12:34:04 VIXL.LSE@EXLWX0093.001 -3x128.81> ~ <Trade: 2020-10-28T13:30:24 VIXL.LSE@EXLWX0093.001 200000x0.0053>
    # DEBUG:root:<Trade: 2020-10-28T13:30:24 VIXL.LSE@EXLWX0093.001 199997x0.0053>

    # Share TradeLog object to support multiple files from the same broker
    # and calculate positions that spread through multiple years
    trade_log = TradeLog(taxation)

    for input_file_path in args.input_csv_files:
        report_type = sniff_report_type(input_file_path)
        logger.info(f"Parsing {input_file_path}, identified report type {report_type}")

        report = SUPPORTED_REPORTS[report_type](trade_log, args.year)
        report.process(taxation, input_file_path)

    trade_log.calculate_closed_positions(args.year)
    logger.info(taxation.summary)

