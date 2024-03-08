import csv
import datetime
import logging
import chardet


logger = logging.getLogger()


CSV_SAMPLE_SIZE = 5000


def get_file_encoding(filename):
    with open(filename, "rb") as f:
        result = chardet.detect(f.read(CSV_SAMPLE_SIZE))
        return result["encoding"]


def sniff_file_dialect(filename, encoding):
    with open(filename, encoding=encoding) as csvfile:
        dialect = csv.Sniffer().sniff(csvfile.read(CSV_SAMPLE_SIZE))
    return dialect


def read_csv_file(filename, delimiter=None, cols_to_lower=True):
    encoding = get_file_encoding(filename)
    if delimiter:
        reader_kwargs = dict(delimiter=delimiter)
    else:
        dialect = sniff_file_dialect(filename, encoding)
        reader_kwargs = dict(dialect=dialect, delimiter=dialect.delimiter)

    logger.debug(
        "Recognized reader kwargs: {} encoding: {}".format(reader_kwargs, encoding)
    )

    with open(filename, encoding=encoding) as f:
        for row in csv.DictReader(f, **reader_kwargs):
            if cols_to_lower:
                yield {key.lower(): value for key, value in row.items()}
            else:
                yield row


# TODO - detect automatically:
SPLITS = {
    "REMX": [
        (datetime.date(2020, 4, 15), 3, 1),  # https://stooq.pl/q/m/?s=remx.us
    ],
    "URNM": [
        (datetime.date(2022, 12, 21), 1, 2),  # https://stooq.pl/q/m/?s=urnm.us
    ],
}


def support_stock_split(symbol, quantity, price, timestamp):

    for split_date, rate_from, rate_to in SPLITS.get(symbol, []):
        if timestamp.date() > split_date:
            logger.warning(f"SPLIT DETECTED! {rate_from}:{rate_to} {price}, {quantity}")
            price = price * rate_to / rate_from
            quantity = int(quantity * rate_from / rate_to)
            logger.warning(f"SPLIT DONE! {rate_from}:{rate_to} {price}, {quantity}")

    return quantity, price
