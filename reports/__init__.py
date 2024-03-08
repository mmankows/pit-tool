from reports.exante_trades_report import ExanteTradesReport
from reports.exante_all_transactions import ExanteAllTransactions
from reports.ib_flex_query_report import IBFlexQueryReport
from utils import read_csv_file

SUPPORTED_REPORTS = {
    "EXANTE_TRADES": ExanteTradesReport,
    "EXANTE_TRANSACTIONS": ExanteAllTransactions,
    "IB_FLEX_QUERY": IBFlexQueryReport,
}


def sniff_report_type(filename):
    possible_reports = []

    for report_type, report_class in SUPPORTED_REPORTS.items():
        if report_class.sniff(filename):
            possible_reports.append(report_type)

    assert (
        len(possible_reports) == 1
    ), f"Couldn't sniff report type, possible types: {possible_reports}"
    return possible_reports[0]


__all__ = [
    SUPPORTED_REPORTS,
    sniff_report_type,
]
