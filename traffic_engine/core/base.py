"""AIToolNotes Traffic Engine - Base Module"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime
import logging
import json

from traffic_engine.config.settings import PATHS

logger = logging.getLogger(__name__)


@dataclass
class ActionRecord:
    """Record of a traffic engine action."""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    module: str = ""
    action: str = ""
    target: str = ""
    status: str = "pending"  # pending, success, failed, skipped
    details: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class BaseModule(ABC):
    """Base class for all traffic engine modules."""

    module_name: str = "base"
    description: str = "Base module"

    def __init__(self):
        self.actions: List[ActionRecord] = []
        self.config: Dict[str, Any] = {}

    @abstractmethod
    def run(self) -> List[ActionRecord]:
        """Execute the module's primary function."""
        pass

    def record_action(self, action: str, target: str, status: str,
                      details: Optional[Dict] = None, error: Optional[str] = None) -> ActionRecord:
        """Record an action for audit and measurement."""
        record = ActionRecord(
            module=self.module_name,
            action=action,
            target=target,
            status=status,
            details=details or {},
            error=error,
        )
        self.actions.append(record)
        logger.info(f"[{self.module_name}] {action} -> {status}: {target}")
        return record

    def save_actions(self) -> str:
        """Persist actions to disk."""
        filename = PATHS["reports"] / f"{self.module_name}_actions.json"
        data = [{
            "timestamp": a.timestamp,
            "module": a.module,
            "action": a.action,
            "target": a.target,
            "status": a.status,
            "details": a.details,
            "error": a.error,
        } for a in self.actions]
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return str(filename)

    def load_previous_actions(self) -> List[ActionRecord]:
        """Load previous actions from disk."""
        filename = PATHS["reports"] / f"{self.module_name}_actions.json"
        if not filename.exists():
            return []
        with open(filename, "r", encoding="utf-8") as f:
            data = json.load(f)
        return [ActionRecord(**item) for item in data]
