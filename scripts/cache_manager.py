#!/usr/bin/env python3
"""
Cache Manager - File-based cache for incremental analysis using content hashes.

This module provides caching functionality to avoid re-analyzing unchanged files,
significantly speeding up repeated analysis runs on large codebases.

Usage:
    from cache_manager import CacheManager

    cache = CacheManager(project_path / ".audit_cache" / "analysis")

    # Check if file needs re-analysis
    cached = cache.get_cached_result(file_path)
    if cached:
        result = cached.result
    else:
        result = analyze_file(file_path)
        cache.store_result(file_path, result)
"""

import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Optional
import logging
import fnmatch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Represents a cached analysis result for a single file."""
    file_path: str
    file_hash: str
    analyzed_at: str
    result: Any
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "file_path": self.file_path,
            "file_hash": self.file_hash,
            "analyzed_at": self.analyzed_at,
            "result": self.result,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'CacheEntry':
        """Create from dictionary."""
        return cls(
            file_path=data["file_path"],
            file_hash=data["file_hash"],
            analyzed_at=data["analyzed_at"],
            result=data["result"],
            metadata=data.get("metadata", {})
        )


class CacheManager:
    """
    Manage file-based cache for incremental analysis.

    Features:
    - MD5 content hashing for change detection
    - Automatic cache invalidation for modified files
    - Pattern-based and age-based invalidation
    - Cache statistics
    """

    def __init__(self, cache_dir: Path = Path(".audit_cache"), cache_name: str = "analysis_cache"):
        """
        Initialize the cache manager.

        Args:
            cache_dir: Directory to store cache files
            cache_name: Name of the cache file (without extension)
        """
        if isinstance(cache_dir, str):
            cache_dir = Path(cache_dir)

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = cache_dir / f"{cache_name}.json"
        self._cache = self._load_cache()

    def _load_cache(self) -> dict:
        """
        Load cache from disk.

        Returns:
            Cache dictionary
        """
        if self.cache_file.exists():
            try:
                with open(self.cache_file, encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load cache: {e}")
                return {"entries": {}, "metadata": {}}
        return {"entries": {}, "metadata": {}}

    def _save_cache(self):
        """Save cache to disk."""
        self._cache["metadata"]["last_updated"] = datetime.now().isoformat()
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2, default=str)
        except IOError as e:
            logger.error(f"Failed to save cache: {e}")

    def _compute_file_hash(self, file_path: Path) -> str:
        """
        Compute MD5 hash of file contents.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal hash string
        """
        hasher = hashlib.md5()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except IOError as e:
            logger.debug(f"Failed to hash file {file_path}: {e}")
            return ""

    def get_cached_result(self, file_path: Path) -> Optional[CacheEntry]:
        """
        Get cached result if file hasn't changed.

        Args:
            file_path: Path to check

        Returns:
            CacheEntry if valid cache exists, None otherwise
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        str_path = str(file_path)

        if str_path not in self._cache["entries"]:
            return None

        entry = self._cache["entries"][str_path]
        current_hash = self._compute_file_hash(file_path)

        if not current_hash:
            return None

        if entry["file_hash"] == current_hash:
            return CacheEntry.from_dict(entry)

        return None

    def store_result(
        self,
        file_path: Path,
        result: Any,
        metadata: dict = None
    ):
        """
        Store analysis result in cache.

        Args:
            file_path: Path that was analyzed
            result: Analysis result to cache
            metadata: Optional metadata to store with result
        """
        if isinstance(file_path, str):
            file_path = Path(file_path)

        str_path = str(file_path)
        file_hash = self._compute_file_hash(file_path)

        if not file_hash:
            logger.debug(f"Skipping cache for unreadable file: {file_path}")
            return

        self._cache["entries"][str_path] = {
            "file_path": str_path,
            "file_hash": file_hash,
            "analyzed_at": datetime.now().isoformat(),
            "result": result,
            "metadata": metadata or {}
        }

        # Periodic save to avoid data loss on interruption
        if len(self._cache["entries"]) % 50 == 0:
            self._save_cache()

    def get_changed_files(self, files: list[Path]) -> tuple[list[Path], list[Path]]:
        """
        Separate files into changed and unchanged lists.

        Args:
            files: List of file paths to check

        Returns:
            Tuple of (changed_files, unchanged_files)
        """
        changed = []
        unchanged = []

        for file_path in files:
            if self.get_cached_result(file_path) is not None:
                unchanged.append(file_path)
            else:
                changed.append(file_path)

        return changed, unchanged

    def invalidate(self, file_path: Path = None):
        """
        Invalidate cache entries.

        Args:
            file_path: Specific file to invalidate, or None for all
        """
        if file_path:
            str_path = str(file_path)
            if str_path in self._cache["entries"]:
                del self._cache["entries"][str_path]
                logger.debug(f"Invalidated cache for: {file_path}")
        else:
            self._cache["entries"] = {}
            logger.info("Invalidated all cache entries")

        self._save_cache()

    def invalidate_by_pattern(self, pattern: str):
        """
        Invalidate entries matching a glob pattern.

        Args:
            pattern: Glob pattern to match file paths
        """
        count = 0
        for path in list(self._cache["entries"].keys()):
            if fnmatch.fnmatch(path, pattern):
                del self._cache["entries"][path]
                count += 1

        self._save_cache()
        logger.info(f"Invalidated {count} entries matching pattern: {pattern}")

    def invalidate_by_directory(self, directory: str):
        """
        Invalidate all entries in a directory.

        Args:
            directory: Directory path to invalidate
        """
        count = 0
        directory = str(directory).rstrip('/')

        for path in list(self._cache["entries"].keys()):
            if path.startswith(directory + '/') or path.startswith(directory + '\\'):
                del self._cache["entries"][path]
                count += 1

        self._save_cache()
        logger.info(f"Invalidated {count} entries in directory: {directory}")

    def invalidate_by_age(self, max_age_days: int):
        """
        Invalidate entries older than specified age.

        Args:
            max_age_days: Maximum age in days
        """
        cutoff = datetime.now() - timedelta(days=max_age_days)
        count = 0

        for path, entry in list(self._cache["entries"].items()):
            try:
                analyzed = datetime.fromisoformat(entry["analyzed_at"])
                if analyzed < cutoff:
                    del self._cache["entries"][path]
                    count += 1
            except (ValueError, KeyError):
                # Invalid date format, invalidate
                del self._cache["entries"][path]
                count += 1

        self._save_cache()
        logger.info(f"Invalidated {count} entries older than {max_age_days} days")

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
        entries = self._cache["entries"]
        cache_size = 0

        if self.cache_file.exists():
            cache_size = self.cache_file.stat().st_size

        # Calculate oldest and newest entries
        oldest = None
        newest = None

        for entry in entries.values():
            try:
                analyzed = datetime.fromisoformat(entry["analyzed_at"])
                if oldest is None or analyzed < oldest:
                    oldest = analyzed
                if newest is None or analyzed > newest:
                    newest = analyzed
            except (ValueError, KeyError):
                pass

        return {
            "total_entries": len(entries),
            "last_updated": self._cache["metadata"].get("last_updated"),
            "cache_size_bytes": cache_size,
            "cache_size_kb": round(cache_size / 1024, 2),
            "oldest_entry": oldest.isoformat() if oldest else None,
            "newest_entry": newest.isoformat() if newest else None
        }

    def flush(self):
        """Force save cache to disk."""
        self._save_cache()

    def get_cached_results_batch(self, file_paths: list[Path]) -> dict[str, CacheEntry]:
        """
        Get cached results for multiple files.

        Args:
            file_paths: List of file paths

        Returns:
            Dictionary mapping file paths to cache entries
        """
        results = {}
        for file_path in file_paths:
            entry = self.get_cached_result(file_path)
            if entry:
                results[str(file_path)] = entry
        return results

    def store_results_batch(self, results: dict[str, Any]):
        """
        Store multiple results at once.

        Args:
            results: Dictionary mapping file paths to results
        """
        for file_path, result in results.items():
            self.store_result(Path(file_path), result)
        self._save_cache()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Cache manager for incremental analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument(
        "cache_dir",
        help="Path to cache directory"
    )

    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show cache statistics"
    )

    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear all cache entries"
    )

    parser.add_argument(
        "--invalidate-pattern",
        type=str,
        help="Invalidate entries matching glob pattern"
    )

    parser.add_argument(
        "--invalidate-dir",
        type=str,
        help="Invalidate entries in directory"
    )

    parser.add_argument(
        "--invalidate-age",
        type=int,
        help="Invalidate entries older than N days"
    )

    args = parser.parse_args()

    cache = CacheManager(Path(args.cache_dir))

    if args.stats:
        stats = cache.get_stats()
        print("Cache Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")

    if args.clear:
        cache.invalidate()
        print("Cache cleared")

    if args.invalidate_pattern:
        cache.invalidate_by_pattern(args.invalidate_pattern)
        print(f"Invalidated entries matching: {args.invalidate_pattern}")

    if args.invalidate_dir:
        cache.invalidate_by_directory(args.invalidate_dir)
        print(f"Invalidated entries in: {args.invalidate_dir}")

    if args.invalidate_age:
        cache.invalidate_by_age(args.invalidate_age)
        print(f"Invalidated entries older than {args.invalidate_age} days")
