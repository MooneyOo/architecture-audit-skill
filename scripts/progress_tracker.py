#!/usr/bin/env python3
"""
Progress Tracker - Progress indicators and ETA estimation for long-running analysis.

This module provides progress tracking with visual progress bars, ETA calculation,
and support for multi-phase operations.

Usage:
    from progress_tracker import ProgressTracker

    progress = ProgressTracker(total=1000, phase="Analyzing files")
    for file in files:
        result = analyze(file)
        progress.update(1, message=file.name)
    progress.complete()
"""

import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Callable, Optional
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ProgressState:
    """Represents the current state of progress."""
    phase: str
    current: int
    total: int
    started_at: datetime
    items_per_second: float = 0.0
    eta: Optional[timedelta] = None
    message: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "phase": self.phase,
            "current": self.current,
            "total": self.total,
            "percent": round((self.current / self.total * 100) if self.total > 0 else 100, 1),
            "items_per_second": round(self.items_per_second, 2),
            "eta_seconds": int(self.eta.total_seconds()) if self.eta else None,
            "eta_formatted": self._format_timedelta(self.eta) if self.eta else None,
            "message": self.message
        }

    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """Format timedelta for display."""
        total_seconds = int(td.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m{seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes}m"


class ProgressTracker:
    """
    Track and display progress for long-running operations.

    Features:
    - Visual progress bar
    - ETA estimation
    - Processing rate calculation
    - Cancellation support
    - Callback support for external monitoring
    """

    def __init__(
        self,
        total: int,
        phase: str = "Processing",
        callback: Optional[Callable[[ProgressState], None]] = None,
        update_interval: float = 0.5,
        quiet: bool = False,
        json_output: bool = False
    ):
        """
        Initialize progress tracker.

        Args:
            total: Total number of items to process
            phase: Name of the current phase
            callback: Optional callback function called on each update
            update_interval: Minimum seconds between display updates
            quiet: If True, suppress progress bar output
            json_output: If True, output progress as JSON lines
        """
        self.total = total
        self.phase = phase
        self.callback = callback
        self.update_interval = update_interval
        self.quiet = quiet
        self.json_output = json_output

        self.current = 0
        self.started_at = datetime.now()
        self.last_update = self.started_at
        self.last_count = 0
        self.items_per_second = 0.0
        self.eta: Optional[timedelta] = None
        self._cancelled = False
        self._message = ""

    def update(self, increment: int = 1, message: str = None):
        """
        Update progress.

        Args:
            increment: Number of items completed
            message: Optional status message
        """
        self.current += increment
        if message:
            self._message = message

        now = datetime.now()

        # Throttle updates for performance
        elapsed_since_update = (now - self.last_update).total_seconds()
        if elapsed_since_update < self.update_interval and self.current < self.total:
            return

        # Calculate rate and ETA
        elapsed = (now - self.started_at).total_seconds()
        if elapsed > 0:
            self.items_per_second = self.current / elapsed
            remaining = self.total - self.current
            if self.items_per_second > 0:
                eta_seconds = remaining / self.items_per_second
                self.eta = timedelta(seconds=int(eta_seconds))

        self.last_update = now
        self.last_count = self.current

        # Display progress
        if not self.quiet:
            self._display()

        # Callback
        if self.callback:
            state = self.get_state()
            self.callback(state)

    def _display(self):
        """Display progress bar."""
        percent = (self.current / self.total) * 100 if self.total > 0 else 100
        bar_width = 40
        filled = int(bar_width * self.current / self.total) if self.total > 0 else bar_width
        bar = '█' * filled + '░' * (bar_width - filled)

        eta_str = ""
        if self.eta:
            eta_str = f" ETA: {self._format_timedelta(self.eta)}"

        rate_str = ""
        if self.items_per_second > 0:
            rate_str = f" [{self.items_per_second:.1f}/s]"

        msg_str = f" | {self._message}" if self._message else ""

        if self.json_output:
            # JSON output for tooling
            state = self.get_state()
            state_dict = state.to_dict()
            state_dict["type"] = "progress"
            sys.stderr.write(json.dumps(state_dict) + "\n")
        else:
            # Human-readable progress bar
            line = (
                f"\r{self.phase}: [{bar}] {percent:5.1f}% "
                f"({self.current}/{self.total}){rate_str}{eta_str}{msg_str}"
            )
            sys.stderr.write(line)
            sys.stderr.write("\033[K")  # Clear to end of line
        sys.stderr.flush()

    @staticmethod
    def _format_timedelta(td: timedelta) -> str:
        """Format timedelta for display."""
        total_seconds = int(td.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m{seconds}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h{minutes}m"

    def complete(self, message: str = "Done"):
        """
        Mark progress as complete.

        Args:
            message: Completion message
        """
        self.current = self.total
        self._message = message

        if not self.quiet:
            if self.json_output:
                state = self.get_state()
                state_dict = state.to_dict()
                state_dict["type"] = "complete"
                sys.stderr.write(json.dumps(state_dict) + "\n")
            else:
                self._display()
                sys.stderr.write("\n")
        sys.stderr.flush()

    def cancel(self):
        """Cancel the operation."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        """Check if cancelled."""
        return self._cancelled

    def get_state(self) -> ProgressState:
        """
        Get current progress state.

        Returns:
            ProgressState with current details
        """
        return ProgressState(
            phase=self.phase,
            current=self.current,
            total=self.total,
            started_at=self.started_at,
            items_per_second=self.items_per_second,
            eta=self.eta,
            message=self._message
        )

    def get_elapsed(self) -> timedelta:
        """Get elapsed time since start."""
        return datetime.now() - self.started_at


class MultiPhaseProgress:
    """
    Track progress across multiple phases of analysis.

    Useful for complex operations that have distinct stages.
    """

    def __init__(
        self,
        phases: list[tuple[str, int]],
        callback: Optional[Callable[[dict], None]] = None,
        quiet: bool = False
    ):
        """
        Initialize multi-phase progress tracker.

        Args:
            phases: List of (phase_name, total_items) tuples
            callback: Optional callback for progress updates
            quiet: If True, suppress output
        """
        self.phases = phases
        self.callback = callback
        self.quiet = quiet
        self.current_phase_idx = 0
        self.phase_progress: Optional[ProgressTracker] = None
        self.started_at = datetime.now()

    def start_phase(self, phase_idx: int = None):
        """
        Start a new phase.

        Args:
            phase_idx: Phase index to start (defaults to next phase)
        """
        if phase_idx is not None:
            self.current_phase_idx = phase_idx

        if self.current_phase_idx >= len(self.phases):
            return

        phase_name, total = self.phases[self.current_phase_idx]
        full_name = f"Phase {self.current_phase_idx + 1}/{len(self.phases)}: {phase_name}"

        self.phase_progress = ProgressTracker(
            total=total,
            phase=full_name,
            quiet=self.quiet
        )

    def update(self, increment: int = 1, message: str = None):
        """
        Update current phase progress.

        Args:
            increment: Items completed
            message: Status message
        """
        if self.phase_progress:
            self.phase_progress.update(increment, message)

            if self.callback:
                self.callback({
                    "phase_idx": self.current_phase_idx,
                    "phase_name": self.phases[self.current_phase_idx][0],
                    "current": self.phase_progress.current,
                    "phase_total": self.phase_progress.total,
                    "overall_progress": self.get_overall_progress()
                })

    def complete_phase(self):
        """Complete current phase and move to next."""
        if self.phase_progress:
            self.phase_progress.complete()
        self.current_phase_idx += 1

    def get_overall_progress(self) -> float:
        """
        Get overall progress percentage across all phases.

        Returns:
            Progress percentage (0-100)
        """
        if not self.phases:
            return 100.0

        total_items = sum(t for _, t in self.phases)
        if total_items == 0:
            return 100.0

        completed_items = sum(
            self.phases[i][1] for i in range(self.current_phase_idx)
        )

        if self.phase_progress:
            completed_items += self.phase_progress.current

        return (completed_items / total_items) * 100

    def get_elapsed(self) -> timedelta:
        """Get elapsed time since start."""
        return datetime.now() - self.started_at

    def complete_all(self):
        """Complete all phases."""
        # Complete current phase if any
        if self.phase_progress and self.phase_progress.current < self.phase_progress.total:
            self.phase_progress.complete()

        # Move through remaining phases
        while self.current_phase_idx < len(self.phases):
            self.complete_phase()

    def is_complete(self) -> bool:
        """Check if all phases are complete."""
        return self.current_phase_idx >= len(self.phases)


class SpinnerProgress:
    """
    Simple spinner for indeterminate progress.

    Use when total items is unknown.
    """

    SPINNER_CHARS = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']

    def __init__(self, message: str = "Processing", quiet: bool = False):
        """
        Initialize spinner.

        Args:
            message: Status message
            quiet: If True, suppress output
        """
        self.message = message
        self.quiet = quiet
        self.idx = 0
        self.started_at = datetime.now()

    def tick(self, message: str = None):
        """
        Advance spinner.

        Args:
            message: Optional new message
        """
        if message:
            self.message = message

        if self.quiet:
            return

        char = self.SPINNER_CHARS[self.idx % len(self.SPINNER_CHARS)]
        self.idx += 1

        elapsed = self._format_elapsed()
        line = f"\r{char} {self.message} ({elapsed})"
        sys.stderr.write(line)
        sys.stderr.write("\033[K")  # Clear to end of line
        sys.stderr.flush()

    def _format_elapsed(self) -> str:
        """Format elapsed time."""
        elapsed = datetime.now() - self.started_at
        total_seconds = int(elapsed.total_seconds())
        if total_seconds < 60:
            return f"{total_seconds}s"
        else:
            minutes = total_seconds // 60
            seconds = total_seconds % 60
            return f"{minutes}m{seconds}s"

    def complete(self, message: str = "Done"):
        """
        Complete spinner.

        Args:
            message: Completion message
        """
        if not self.quiet:
            elapsed = self._format_elapsed()
            sys.stderr.write(f"\r✓ {message} ({elapsed})\n")
            sys.stderr.flush()


def create_progress_callback(json_file=None) -> Callable[[ProgressState], None]:
    """
    Create a progress callback for external integration.

    Args:
        json_file: Optional file path to write JSON progress

    Returns:
        Callback function
    """
    def callback(state: ProgressState):
        data = state.to_dict()

        if json_file:
            with open(json_file, 'w') as f:
                json.dump(data, f)

    return callback


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Progress tracking demonstration",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run demo"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress output"
    )

    args = parser.parse_args()

    if args.demo:
        # Demo progress tracking
        total = 100

        progress = ProgressTracker(
            total=total,
            phase="Processing items",
            json_output=args.json,
            quiet=args.quiet
        )

        for i in range(total):
            time.sleep(0.02)  # Simulate work
            progress.update(1, message=f"item_{i}.py")

        progress.complete("All items processed")

        print(f"\nElapsed: {progress.get_elapsed()}")
