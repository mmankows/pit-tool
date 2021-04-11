from reports.exante_trades_report import ExanteTradesReport
from reports.exante_all_transactions import ExanteAllTransactions

SUPPORTED_REPORTS = {
    "EXANTE_TRADES": ExanteTradesReport,
    "EXANTE_TRANSACTIONS": ExanteAllTransactions,
}

__all__ = [
    SUPPORTED_REPORTS,
]