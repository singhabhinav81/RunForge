import logging
import sys

# Configure the logger
def configure_logger(name: str) -> logging.Logger:
    """
    Configures and returns a logger with the specified name.

    Args:
        name (str): The name of the logger.

    Returns:
        logging.Logger: Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler('run_forge.log')

    # Create formatter and add it to the handler
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(lineno)d - %(message)s')
    console_handler.setFormatter(formatter)

    # Add the handler to the logger
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger
# Create a logger instance for the application
logger = configure_logger("job_queue_system")   
# Example usage of the logger
if __name__ == "__main__":
    logger.info("Logger configured successfully.")
    logger.debug("This is a debug message.")
    logger.error("This is an error message.")
    logger.warning("This is a warning message.")
    logger.critical("This is a critical message.")
# This logger can be used throughout the application to log messages at different levels.
# The logger can be imported and used in other modules as follows:
# from app.core.logger import logger
# logger.info("This is an info message.")
# The logger will output messages to the console with timestamps, logger name, log level, and the message itself.
# This allows for easy tracking of application behavior and debugging.
# The logger can be further configured to log to files or other outputs as needed.          