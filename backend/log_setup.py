import logging
import logging.handlers
import os
import config # Assuming config.py is in the same directory or PYTHONPATH is set

def setup_logger(logger_name, log_file, level=logging.INFO):
    """Sets up a logger to write to a rotating file."""
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
        except OSError as e:
            print(f"Error creating log directory {log_dir}: {e}")
            # Fallback to basic console logging if directory creation fails
            logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            return logging.getLogger(logger_name)

    logger = logging.getLogger(logger_name)
    logger.setLevel(level)
    logger.propagate = False # Prevent duplicate logging to root logger if already configured

    # Avoid adding handlers if they already exist
    if not logger.handlers:
        # Formatter
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

        # Rotating File Handler
        try:
            # Use absolute path for log file based on project root derived from config path
            project_root = os.path.dirname(os.path.dirname(os.path.abspath(config.__file__)))
            absolute_log_path = os.path.join(project_root, log_file)

            rfh = logging.handlers.RotatingFileHandler(
                absolute_log_path,
                maxBytes=config.LOG_MAX_BYTES,
                backupCount=config.LOG_BACKUP_COUNT,
                encoding='utf-8'
            )
            rfh.setLevel(level)
            rfh.setFormatter(formatter)
            logger.addHandler(rfh)

            # Optional: Console Handler for simultaneous console output
            # ch = logging.StreamHandler()
            # ch.setLevel(level)
            # ch.setFormatter(formatter)
            # logger.addHandler(ch)

        except Exception as e:
            print(f"Error setting up file handler for {log_file}: {e}")
            # Fallback to basic console logging
            logging.basicConfig(level=level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            return logging.getLogger(logger_name) # Return the logger even if file handler failed

    return logger
