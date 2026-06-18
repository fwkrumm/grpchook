"""
Logging utilities: ``GrpcLogger`` subclass with project-specific levels and
a ``get_logger`` factory that attaches console + rotating file handlers.
"""
import logging
import tempfile
import warnings
from datetime import datetime
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

import coloredlogs

INTERNAL_DEBUG = 5
INTERNAL_INFO = 7
logging.addLevelName(INTERNAL_DEBUG, "INTERNAL_DEBUG")
logging.addLevelName(INTERNAL_INFO, "INTERNAL_INFO")


class GrpcLogger(logging.Logger):
    """Logger subclass that adds INTERNAL_INFO (7) and INTERNAL_DEBUG (5) levels below DEBUG."""

    def iinfo(self, message, *args, **kwargs):
        """Log at INTERNAL_INFO level (7) — framework lifecycle events, below DEBUG."""
        if self.isEnabledFor(INTERNAL_INFO):
            self._log(INTERNAL_INFO, message, args, **kwargs)

    def idebug(self, message, *args, **kwargs):
        """Log at INTERNAL_DEBUG level (5) — fine-grained framework tracing, below INTERNAL_INFO."""
        if self.isEnabledFor(INTERNAL_DEBUG):
            self._log(INTERNAL_DEBUG, message, args, **kwargs)

    def setLevel(self, level) -> None:
        """Set level on the logger and all attached handlers simultaneously."""
        super().setLevel(level)
        for handler in self.handlers:
            handler.setLevel(level)


logging.setLoggerClass(GrpcLogger)


def get_logger(
    name: str = "default",
    *,
    log_level: int = logging.INFO,
    log_dir: str = None,
    enable_file_logging: bool = True,
    enable_console_logging: bool = True,
    use_colored_output: bool = True
) -> GrpcLogger:
    """
    Get or create a configured logger instance.

    Parameters
    ----------
    name : str
        Logger name (default: "default")
    log_level : int
        Base logging level (default: logging.INFO)
    log_dir : str
        Directory for log files. If None, uses system temp dir.
    enable_file_logging : bool
        Whether to enable file logging (default: True)
    enable_console_logging : bool
        Whether to enable console logging (default: True)
    use_colored_output : bool
        Whether to use colored console output (default: True)

    Returns
    -------
    GrpcLogger
        Configured logger instance
    """
    logger = logging.getLogger(name)
    assert isinstance(logger, GrpcLogger), (
        f"Expected GrpcLogger but got {type(logger).__name__}. "
        f"Ensure no other code called logging.getLogger('{name}') before setLoggerClass was set."
    )

    # Avoid adding handlers multiple times
    if logger.handlers:
        return logger

    # Logger level must be INTERNAL to allow file handler to capture everything
    # Individual handlers control their own output levels
    logger.setLevel(INTERNAL_DEBUG)
    logger.propagate = False

    # Determine log directory
    if log_dir is None:
        log_location = Path(tempfile.gettempdir()) / "grpcLogs"
    else:
        log_location = Path(log_dir)

    # Create file formatter
    file_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console handler with coloredlogs
    if enable_console_logging:
        if use_colored_output:
            # coloredlogs installs directly on the logger with field-level colors
            coloredlogs.install(
                level=log_level,
                logger=logger,
                fmt="%(asctime)s %(hostname)s %(name)s[%(process)d] %(levelname)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
                level_styles={
                    "internal_debug": {"color": "blue"},
                    "internal_info": {"color": "white"},
                    "debug": {"color": "cyan"},
                    "info": {"color": "green"},
                    "warning": {"color": "yellow", "bold": True},
                    "error": {"color": "red", "bold": True},
                    "critical": {"color": "red", "bold": True, "background": "white"}
                },
                field_styles={
                    "asctime": {"color": "white", "bold": True},
                    "hostname": {"color": "magenta"},
                    "levelname": {"color": "white", "bold": True},
                    "name": {"color": "cyan"},
                    "programname": {"color": "cyan"},
                    "process": {"color": "magenta"}
                }
            )
        else:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(log_level)
            console_handler.setFormatter(file_formatter)
            logger.addHandler(console_handler)

    # File handler with rotation
    if enable_file_logging:
        try:
            log_location.mkdir(parents=True, exist_ok=True)

            # Generate timestamp for log filename
            timestamp = datetime.now().strftime("%Y%m%d")
            log_filename = log_location / f"{name}_{timestamp}.log"

            # Use TimedRotatingFileHandler for automatic daily rotation
            file_handler = TimedRotatingFileHandler(
                log_filename,
                when="midnight",
                interval=1,
                backupCount=30,  # Keep 30 days of logs
                encoding="utf-8"
            )
            file_handler.setLevel(INTERNAL_DEBUG)
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
            logger.info("Logging files to %s", log_location)

        except (PermissionError, OSError) as e:
            warnings.warn(
                f"Could not create log directory at {log_location}: {e}. "
                "File logging disabled.",
                stacklevel=2
            )

    return logger
