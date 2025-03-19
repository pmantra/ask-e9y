from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from uuid import UUID, uuid4
from datetime import datetime
import time


@dataclass
class ProcessingContext:
    """Track the state throughout query processing."""
    query_id: UUID = field(default_factory=uuid4)
    conversation_id: UUID = field(default_factory=uuid4)
    request_id: str = field(default_factory=lambda: str(uuid4()))  # Added request_id

    # Core query information
    original_query: str = ""
    enhanced_query: str = ""

    # Results
    sql: Optional[str] = None  # Added SQL field
    results: List[Dict[str, Any]] = field(default_factory=list)  # Added results field
    results_explanation: Optional[str] = None  # Added explanation field

    # Processing state
    current_stage: str = "initialized"
    completed_stages: List[str] = field(default_factory=list)
    stage_results: Dict[str, Any] = field(default_factory=dict)

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)  # Added metadata

    # Performance tracking
    start_time: float = field(default_factory=time.time)
    stage_timings: Dict[str, float] = field(default_factory=dict)

    # Error information
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def start_stage(self, stage_name: str) -> None:
        """Mark the start of a processing stage."""
        self.current_stage = stage_name
        self.stage_timings[f"{stage_name}_start"] = time.time()

    def complete_stage(self, stage_name: str, result: Any = None) -> None:
        """Mark completion of a processing stage."""
        self.completed_stages.append(stage_name)

        end_time = time.time()
        start_time = self.stage_timings.get(f"{stage_name}_start", end_time)
        self.stage_timings[stage_name] = end_time - start_time

        if result is not None:
            self.stage_results[stage_name] = result

    def add_error(self, stage: str, error: Exception) -> None:
        """Add an error to the context."""
        self.errors.append({
            "stage": stage,
            "error_type": type(error).__name__,
            "message": str(error),
            "timestamp": datetime.now().isoformat()
        })

    def get_timing_metrics(self) -> Dict[str, float]:
        """Get timing metrics in milliseconds."""
        return {
            stage: duration * 1000  # Convert to ms
            for stage, duration in self.stage_timings.items()
            if not stage.endswith("_start")  # Skip start markers
        }

    def get_summary(self) -> Dict[str, Any]:
        """Get processing summary for logging/monitoring."""
        total_time = time.time() - self.start_time

        summary = {
            "query_id": str(self.query_id),
            "request_id": self.request_id,
            "conversation_id": str(self.conversation_id),
            "total_time_ms": total_time * 1000,
            "stages_completed": self.completed_stages,
            "error_count": len(self.errors),
            "stage_timings_ms": self.get_timing_metrics()
        }

        # Add cache status if available
        if "cache_lookup" in self.stage_results:
            summary["cache_status"] = self.metadata.get("cache_status", "unknown")
        else:
            summary["cache_status"] = self.stage_results.get("query_processing", {}).get("cache_status", "unknown")

        # Add result metrics if available
        if self.results:
            summary["row_count"] = len(self.results)
        else:
            summary["row_count"] = self.metadata.get("row_count", 0)

        return summary