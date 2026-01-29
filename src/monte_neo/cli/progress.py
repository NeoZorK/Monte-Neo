"""Progress tracking module.

Progress bars and ETA estimation.
"""

from __future__ import annotations

import time

from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from monte_neo.utils.console import console


class ProgressTracker:
    """Track progress with ETA estimation.
    
    V0.0.5 Development Stages:
    1. Metal Foundation: C++/Metal bridge and BaseKernel. [DONE]
    2. Indicators Library: SMA, EMA, RSI, ATR in MSL. [DONE]
    3. Optimization: GPU Grid Search and Walk-Forward. [DONE]
    4. Production Gate: Robustness scoring and Certification. [DONE]
    """

    def __init__(self) -> None:
        """Initialize tracker."""
        self._progress: Progress | None = None
        self._task_id: TaskID | None = None
        self._start_time: float = 0
        self._total: int = 0

    def start(self, total: int, description: str = "Processing...") -> None:
        """Start progress tracking.

        Args:
            total: Total number of items.
            description: Progress description.
        """
        if self._progress:
            self.stop()

        self._total = total
        self._start_time = time.time()

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(bar_width=40),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("•"),
            TimeElapsedColumn(),
            TextColumn("•"),
            TimeRemainingColumn(),
            TextColumn("[dim]{task.fields[status]}"),
            console=console,
            transient=False,  # Set to False to keep the bar visible during update
        )

        self._progress.start()
        self._task_id = self._progress.add_task(
            description,
            total=total,
            status="",
        )

    def update(self, current: int, total: int, status: str = "") -> None:
        """Update progress."""
        if self._progress and self._task_id is not None:
            # Ensure we don't exceed 100% in display
            val = min(current, total)
            self._progress.update(
                self._task_id,
                completed=val,
                total=total,
                status=status,
                refresh=True,  # Always refresh to keep UI snappy
            )

    def stop(self) -> None:
        """Stop progress tracking."""
        if self._progress:
            self._progress.stop()
            self._progress = None
            self._task_id = None

    def get_eta_minutes(self, current: int) -> float:
        """Get estimated time remaining in minutes.

        Args:
            current: Current position.

        Returns:
            Estimated minutes remaining.
        """
        if current == 0:
            return 0

        elapsed = time.time() - self._start_time
        rate = current / elapsed
        remaining = self._total - current

        if rate > 0:
            return (remaining / rate) / 60

        return 0


def estimate_generation_time(
    data_size: int,
    iterations: int,
    mc_methods: int,
) -> str:
    """Estimate generation time.

    Args:
        data_size: Number of data points.
        iterations: Generation iterations.
        mc_methods: Number of MC methods.

    Returns:
        Human-readable time estimate.
    """
    # Rough estimation based on typical performance
    base_time = 0.001  # seconds per iteration
    mc_factor = 1 + (mc_methods * 0.5)
    data_factor = data_size / 1000

    total_seconds = base_time * iterations * mc_factor * data_factor

    if total_seconds < 60:
        return f"~{int(total_seconds)} seconds"
    elif total_seconds < 3600:
        return f"~{int(total_seconds / 60)} minutes"
    else:
        return f"~{total_seconds / 3600:.1f} hours"
