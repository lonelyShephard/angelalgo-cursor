# c:\Users\user\projects\angelalgo\smartapi\log_utils.py
import logging
import logging.handlers
import logzero
import sys

def setup_loggers():
    """
    Configures and returns the main application logger and a dedicated tick logger.
    This function is executed once when the module is imported.
    """
    # --- Main Application Logger (logzero) ---
    # This is the default logzero logger. It's configured to log to both
    # the console and a rotating file 'live_trader.log'.
    logzero.loglevel(logging.INFO)
    logzero.logfile(
        "smartapi/live_trader.log",
        maxBytes=1e6,  # 1 Megabyte
        backupCount=3,
        loglevel=logging.INFO
    )

    # --- Dedicated Tick Logger (standard logging) ---
    # This logger writes *only* to 'price_ticks.log' and does not print to console.
    tick_logger = logging.getLogger('price_ticks')
    tick_logger.setLevel(logging.INFO)
    tick_logger.propagate = False  # Prevent ticks from going to the root logger/console

    # Ensure we don't add handlers if the logger is already configured
    if not tick_logger.handlers:
        tick_file_handler = logging.handlers.RotatingFileHandler(
            'smartapi/price_ticks.log', maxBytes=5e6, backupCount=5)  # 5 Megabytes
        tick_file_handler.setFormatter(logging.Formatter('%(message)s'))
        tick_logger.addHandler(tick_file_handler)

    return logzero.logger, tick_logger

# Setup loggers on import and expose them
logger, tick_logger = setup_loggers()