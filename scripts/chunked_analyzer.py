#!/usr/bin/env python3
"""
Chunked Analyzer - Process files in batches to manage memory and enable progress tracking.

This module provides utilities for analyzing large codebases in configurable batch sizes,
with support for resume from interruption and intermediate result caching.

Usage:
    from chunked_analyzer import ChunkedAnalyzer, ChunkConfig

    config = ChunkConfig(chunk_size=100, resume=True)
    analyzer = ChunkedAnalyzer(config)

    for chunk_result in analyzer.analyze_project(project_path, my_analyzer_func):
        # Process chunk results
        pass

    final_results = analyzer.merge_results()
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterator, Callable, Any, Optional
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ChunkConfig:
    """Configuration for chunked analysis."""
    chunk_size: int = 100
    output_dir: Path = field(default_factory=lambda: Path(".audit_cache"))
    resume: bool = True
    progress_callback: Optional[Callable[[int, int, int], None]] = None
    file_extensions: set[str] = field(default_factory=lambda: {'.py', '.ts', '.tsx', '.js', '.jsx', '.vue'})
    exclude_dirs: set[str] = field(default_factory=lambda: {
        'node_modules', '__pycache__', '.git', 'venv', '.venv',
        'dist', 'build', '.next', 'coverage', '.pytest_cache',
        'migrations', 'alembic', 'env', '.env'
    })


@dataclass
class ChunkResult:
    """Result from processing a single chunk."""
    chunk_id: int
    total_chunks: int
    files_processed: int
    results: list[dict]
    errors: list[str] = field(default_factory=list)


class ChunkedAnalyzer:
    """
    Analyze projects in chunks for memory-efficient processing of large codebases.

    Features:
    - Configurable chunk sizes
    - Resume from interruption via cached chunks
    - Progress callbacks for tracking
    - Automatic file collection with exclusion filters
    """

    def __init__(self, config: ChunkConfig):
        """
        Initialize the chunked analyzer.

        Args:
            config: ChunkConfig with processing settings
        """
        self.config = config
        if isinstance(self.config.output_dir, str):
            self.config.output_dir = Path(self.config.output_dir)
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    def analyze_project(
        self,
        project_path: Path,
        analyzer_func: Callable[[Path], dict],
        file_filter: Optional[Callable[[Path], bool]] = None
    ) -> Iterator[ChunkResult]:
        """
        Analyze project in chunks, yielding results for each chunk.

        Args:
            project_path: Root path of the project to analyze
            analyzer_func: Function that takes a file path and returns analysis result
            file_filter: Optional function to filter files (return True to include)

        Yields:
            ChunkResult for each processed chunk
        """
        if isinstance(project_path, str):
            project_path = Path(project_path)

        all_files = self._collect_files(project_path, file_filter)
        total_files = len(all_files)
        total_chunks = (total_files + self.config.chunk_size - 1) // self.config.chunk_size

        logger.info(f"Found {total_files} files to process in {total_chunks} chunks")

        for i, chunk in enumerate(self._chunk_list(all_files)):
            chunk_id = i + 1

            # Check for existing chunk (resume support)
            if self.config.resume:
                cached = self._load_cached_chunk(chunk_id)
                if cached:
                    logger.debug(f"Loaded cached chunk {chunk_id}/{total_chunks}")
                    yield ChunkResult(
                        chunk_id=chunk_id,
                        total_chunks=total_chunks,
                        files_processed=cached.get("files_processed", 0),
                        results=cached.get("results", []),
                        errors=cached.get("errors", [])
                    )
                    continue

            # Process chunk
            results = []
            errors = []

            for file_path in chunk:
                try:
                    result = analyzer_func(file_path)
                    if result:
                        results.append(result)
                except Exception as e:
                    errors.append({
                        "file": str(file_path),
                        "error": str(e)
                    })
                    logger.debug(f"Error processing {file_path}: {e}")

            # Build chunk result
            chunk_result = ChunkResult(
                chunk_id=chunk_id,
                total_chunks=total_chunks,
                files_processed=len(results),
                results=results,
                errors=errors
            )

            # Save intermediate results
            self._save_chunk(chunk_id, chunk_result)

            # Progress callback
            if self.config.progress_callback:
                self.config.progress_callback(chunk_id, total_chunks, len(results))

            yield chunk_result

    def _collect_files(
        self,
        project_path: Path,
        file_filter: Optional[Callable[[Path], bool]] = None
    ) -> list[Path]:
        """
        Collect all files to analyze.

        Args:
            project_path: Root path to search
            file_filter: Optional filter function

        Returns:
            Sorted list of file paths
        """
        files = []

        for file_path in project_path.rglob("*"):
            if not file_path.is_file():
                continue

            # Skip excluded directories
            if any(excluded in file_path.parts for excluded in self.config.exclude_dirs):
                continue

            # Include only specified extensions
            if file_path.suffix not in self.config.file_extensions:
                continue

            # Apply custom filter if provided
            if file_filter and not file_filter(file_path):
                continue

            files.append(file_path)

        return sorted(files)

    def _chunk_list(self, items: list) -> Iterator[list]:
        """
        Split list into chunks.

        Args:
            items: List to split

        Yields:
            Chunks of the list
        """
        for i in range(0, len(items), self.config.chunk_size):
            yield items[i:i + self.config.chunk_size]

    def _save_chunk(self, chunk_id: int, data: ChunkResult):
        """
        Save chunk results to file.

        Args:
            chunk_id: Chunk identifier
            data: ChunkResult to save
        """
        chunk_file = self.config.output_dir / f"chunk_{chunk_id:04d}.json"

        # Convert ChunkResult to dict for serialization
        chunk_data = {
            "chunk_id": data.chunk_id,
            "total_chunks": data.total_chunks,
            "files_processed": data.files_processed,
            "results": data.results,
            "errors": data.errors
        }

        with open(chunk_file, 'w', encoding='utf-8') as f:
            json.dump(chunk_data, f, indent=2, default=str)

    def _load_cached_chunk(self, chunk_id: int) -> Optional[dict]:
        """
        Load cached chunk if exists.

        Args:
            chunk_id: Chunk identifier

        Returns:
            Cached chunk data or None
        """
        chunk_file = self.config.output_dir / f"chunk_{chunk_id:04d}.json"

        if chunk_file.exists():
            try:
                with open(chunk_file, encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cached chunk {chunk_id}: {e}")
                return None
        return None

    def merge_results(self) -> dict:
        """
        Merge all chunk results into a single result.

        Returns:
            Combined results from all chunks
        """
        all_results = []
        all_errors = []
        total_files = 0
        total_chunks = 0

        for chunk_file in sorted(self.config.output_dir.glob("chunk_*.json")):
            try:
                with open(chunk_file, encoding='utf-8') as f:
                    chunk_data = json.load(f)
                    all_results.extend(chunk_data.get("results", []))
                    all_errors.extend(chunk_data.get("errors", []))
                    total_files += chunk_data.get("files_processed", 0)
                    total_chunks = max(total_chunks, chunk_data.get("total_chunks", 0))
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to merge chunk {chunk_file}: {e}")

        return {
            "total_files": total_files,
            "total_chunks": total_chunks,
            "results": all_results,
            "errors": all_errors
        }

    def cleanup(self):
        """Remove intermediate chunk files."""
        import shutil

        if self.config.output_dir.exists():
            shutil.rmtree(self.config.output_dir)
            logger.info(f"Cleaned up cache directory: {self.config.output_dir}")

    def get_progress(self) -> dict:
        """
        Get current progress based on cached chunks.

        Returns:
            Progress information dict
        """
        cached_chunks = list(self.config.output_dir.glob("chunk_*.json"))
        total_cached = len(cached_chunks)

        if total_cached == 0:
            return {"completed_chunks": 0, "total_chunks": 0, "percent": 0}

        # Read total from any cached chunk
        with open(cached_chunks[0], encoding='utf-8') as f:
            data = json.load(f)
            total_chunks = data.get("total_chunks", total_cached)

        percent = (total_cached / total_chunks * 100) if total_chunks > 0 else 100

        return {
            "completed_chunks": total_cached,
            "total_chunks": total_chunks,
            "percent": round(percent, 1)
        }


def count_files(
    project_path: Path,
    file_extensions: set[str] = None,
    exclude_dirs: set[str] = None
) -> int:
    """
    Count files that would be processed without doing analysis.

    Useful for progress tracking setup.

    Args:
        project_path: Root path to search
        file_extensions: File extensions to include
        exclude_dirs: Directories to exclude

    Returns:
        Number of files matching criteria
    """
    if isinstance(project_path, str):
        project_path = Path(project_path)

    file_extensions = file_extensions or {'.py', '.ts', '.tsx', '.js', '.jsx', '.vue'}
    exclude_dirs = exclude_dirs or {
        'node_modules', '__pycache__', '.git', 'venv', '.venv',
        'dist', 'build', '.next', 'coverage'
    }

    count = 0
    for file_path in project_path.rglob("*"):
        if not file_path.is_file():
            continue
        if any(excluded in file_path.parts for excluded in exclude_dirs):
            continue
        if file_path.suffix in file_extensions:
            count += 1

    return count


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Chunked file processor for large projects",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "project_path",
        help="Path to the project directory"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=100,
        help="Number of files per chunk (default: 100)"
    )

    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Only count files, don't process"
    )

    parser.add_argument(
        "--cleanup",
        action="store_true",
        help="Remove cached chunk files"
    )

    args = parser.parse_args()

    project_path = Path(args.project_path)

    if args.count_only:
        count = count_files(project_path)
        print(f"Files to process: {count}")
    elif args.cleanup:
        config = ChunkConfig(output_dir=project_path / ".audit_cache")
        analyzer = ChunkedAnalyzer(config)
        analyzer.cleanup()
    else:
        config = ChunkConfig(
            chunk_size=args.chunk_size,
            output_dir=project_path / ".audit_cache"
        )
        analyzer = ChunkedAnalyzer(config)

        # Example: just count files in each chunk
        for chunk_result in analyzer.analyze_project(
            project_path,
            lambda f: {"file": str(f), "size": f.stat().st_size}
        ):
            print(f"Chunk {chunk_result.chunk_id}/{chunk_result.total_chunks}: "
                  f"{chunk_result.files_processed} files")
