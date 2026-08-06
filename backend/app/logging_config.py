import os
import json
import logging
from datetime import datetime, timezone
import contextvars

# Context variables to track correlation_id and node_name across threads/async tasks
correlation_id_var = contextvars.ContextVar("correlation_id", default="system")
node_name_var = contextvars.ContextVar("node_name", default="main")

class JSONFormatter(logging.Formatter):
    """
    Custom Formatter that prints logs in a structured JSON format.
    Ensures every log line contains timestamp, level, correlation_id, and node_name.
    Extracts additional custom attributes from record.__dict__ dynamically.
    """
    def format(self, record: logging.LogRecord) -> str:
        cid = getattr(record, "correlation_id", None) or correlation_id_var.get()
        node = getattr(record, "node_name", None) or node_name_var.get()
        
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "correlation_id": cid,
            "node_name": node,
            "logger": record.name,
            "message": record.getMessage()
        }
        
        # Add extra custom fields, ignoring standard LogRecord attributes
        standard_attrs = {
            "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
            "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
            "created", "msecs", "relativeCreated", "thread", "threadName",
            "processName", "process", "message", "correlation_id", "node_name"
        }
        
        extra = {}
        for key, val in record.__dict__.items():
            if key not in standard_attrs and not key.startswith("_"):
                extra[key] = val
        if extra:
            log_data["extra"] = extra
            
        return json.dumps(log_data)


def setup_logging():
    """
    Configures the root logging stream handler to output structured JSON formatted logs.
    """
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
        
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(console_handler)
    
    level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_str, logging.INFO)
    root_logger.setLevel(level)


def get_logger(name: str) -> logging.Logger:
    """
    Consistent logger factory for Sentinel AI modules.
    """
    return logging.getLogger(name)


# Custom LangGraph/LangChain Tracing Callback Handler
import time
from uuid import UUID
from typing import Dict, Any, Optional
from langchain_core.callbacks import BaseCallbackHandler

logger = get_logger("sentinel.graph_tracing")

class LangGraphTracingCallbackHandler(BaseCallbackHandler):
    """
    LangChain callback handler that tracks LangGraph node execution.
    Logs entering and exiting node events alongside execution latencies.
    """
    def __init__(self, correlation_id: str):
        super().__init__()
        self.correlation_id = correlation_id
        self.runs = {}  # maps run_id (UUID) -> (node_name, start_time)

    def on_chain_start(
        self, serialized: Optional[Dict[str, Any]], inputs: Dict[str, Any], *, run_id: UUID, **kwargs
    ) -> None:
        name = "node"
        if serialized:
            name = serialized.get("name") or "node"
        elif kwargs and kwargs.get("name"):
            name = kwargs.get("name")
        self.runs[run_id] = (name, time.time())
        logger.info(
            f"Entering node: {name}",
            extra={
                "node_name": name,
                "correlation_id": self.correlation_id,
                "event": "node_entry"
            }
        )

    def on_chain_end(
        self, outputs: Dict[str, Any], *, run_id: UUID, **kwargs
    ) -> None:
        if run_id in self.runs:
            name, start_time = self.runs[run_id]
            duration = (time.time() - start_time) * 1000.0
            logger.info(
                f"Exiting node: {name} (duration: {duration:.2f}ms)",
                extra={
                    "node_name": name,
                    "correlation_id": self.correlation_id,
                    "duration_ms": duration,
                    "event": "node_exit"
                }
            )
