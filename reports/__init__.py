from reports.exante_trades_report import ExanteTradesReport
from reports.exante_all_transactions import ExanteAllTransactions
from utils import read_csv_file

SUPPORTED_REPORTS = {
    "EXANTE_TRADES": ExanteTradesReport,
    "EXANTE_TRANSACTIONS": ExanteAllTransactions,
}


def sniff_report_type(filename):
    possible_reports = []
    for report_type, report_class in SUPPORTED_REPORTS.items():
        expected_columns = {
            key_value for key_name, key_value in report_class.__dict__.items() if key_name.startswith('column_')
        }
        sample_row = next(read_csv_file(filename))
        if not (expected_columns - set(sample_row.keys())):
            possible_reports.append(report_type)

    assert len(possible_reports) == 1, f"Couldn't sniff report type, possible types: {possible_reports}"
    return possible_reports[0]


__all__ = [
    SUPPORTED_REPORTS,
    sniff_report_type,
]