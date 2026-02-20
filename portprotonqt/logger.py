import logging

def setup_logger(level='NOTSET'):
    """Set up basic logging configuration."""
    # Clear existing handlers to prevent duplicates
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Convert string level to logging level constant, map ALL to DEBUG
    if level.upper() == 'ALL':
        log_level = logging.DEBUG
    else:
        log_level = getattr(logging, level.upper(), logging.NOTSET)

    # Configure logging with null handler if level is NOTSET
    if log_level == logging.NOTSET:
        logging.basicConfig(
            level=logging.NOTSET,
            handlers=[logging.NullHandler()]
        )
    else:
        logging.basicConfig(
            level=log_level,
            format='[%(levelname)s] %(message)s',
            handlers=[logging.StreamHandler()]
        )

def get_logger(name):
    """Return a logger for the specified module."""
    return logging.getLogger(name)

# Initialize logger on module import (no logs by default)
setup_logger()
