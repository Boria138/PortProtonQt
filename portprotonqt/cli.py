import argparse
from portprotonqt.logger import get_logger

logger = get_logger(__name__)

def parse_args():
    """
    Парсит аргументы командной строки.
    """
    parser = argparse.ArgumentParser(description="PortProtonQt CLI")
    parser.add_argument(
        "--fullscreen",
        action="store_true",
        help="Запустить приложение в полноэкранном режиме и сохранить эту настройку"
    )
    return parser.parse_args()
