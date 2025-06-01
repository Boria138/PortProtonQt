import logging

def setup_logger():
    """Настройка базовой конфигурации логирования."""
    logging.basicConfig(
        level=logging.INFO,
        format='[%(levelname)s] %(message)s',
        handlers=[logging.StreamHandler()]
    )

def get_logger(name):
    """Возвращает логгер для указанного модуля."""
    return logging.getLogger(name)

# Инициализация логгера при импорте модуля
setup_logger()
