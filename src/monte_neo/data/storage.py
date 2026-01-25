"""Parquet storage module.

Efficient data storage and retrieval using Parquet format.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from monte_neo.utils.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


class ParquetStorage:
    """Efficient Parquet-based data storage."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        """Initialize storage.

        Args:
            base_dir: Base directory for data storage.
        """
        if base_dir is None:
            base_dir = os.getenv("MONTE_NEO_DATA_DIR", "./data")
        self.base_dir = Path(base_dir)
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Create necessary directories."""
        for subdir in ["raw", "processed", "results"]:
            (self.base_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _get_path(
        self,
        symbol: str,
        timeframe: str,
        category: str = "raw",
    ) -> Path:
        """Generate file path for data.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle interval.
            category: Data category (raw, processed, results).

        Returns:
            Path to the Parquet file.
        """
        filename = f"{symbol}_{timeframe}.parquet"
        return self.base_dir / category / filename

    def save(
        self,
        df: pd.DataFrame,
        symbol: str,
        timeframe: str,
        category: str = "raw",
        compression: str = "snappy",
    ) -> Path:
        """Save DataFrame to Parquet.

        Args:
            df: DataFrame to save.
            symbol: Trading pair symbol.
            timeframe: Candle interval.
            category: Data category.
            compression: Compression algorithm.

        Returns:
            Path to saved file.
        """
        path = self._get_path(symbol, timeframe, category)

        # Convert to PyArrow table for better control
        table = pa.Table.from_pandas(df)

        pq.write_table(
            table,
            path,
            compression=compression,
            use_dictionary=True,
            write_statistics=True,
        )

        logger.info(f"Saved {len(df)} rows to {path}")
        return path

    def load(
        self,
        symbol: str,
        timeframe: str,
        category: str = "raw",
        columns: list[str] | None = None,
    ) -> pd.DataFrame:
        """Load DataFrame from Parquet.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle interval.
            category: Data category.
            columns: Optional list of columns to load.

        Returns:
            Loaded DataFrame.
        """
        path = self._get_path(symbol, timeframe, category)

        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path}")

        df = pq.read_table(path, columns=columns).to_pandas()
        logger.info(f"Loaded {len(df)} rows from {path}")
        return df

    def exists(
        self,
        symbol: str,
        timeframe: str,
        category: str = "raw",
    ) -> bool:
        """Check if data file exists.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle interval.
            category: Data category.

        Returns:
            True if file exists.
        """
        return self._get_path(symbol, timeframe, category).exists()

    def list_files(self, category: str = "raw") -> list[dict]:
        """List all data files in category.

        Args:
            category: Data category.

        Returns:
            List of file info dictionaries.
        """
        category_dir = self.base_dir / category
        files = []

        for path in category_dir.glob("*.parquet"):
            parts = path.stem.split("_")
            if len(parts) >= 2:
                files.append(
                    {
                        "symbol": parts[0],
                        "timeframe": parts[1],
                        "path": path,
                        "size_mb": path.stat().st_size / (1024 * 1024),
                    }
                )

        return sorted(files, key=lambda x: x["symbol"])

    def delete(
        self,
        symbol: str,
        timeframe: str,
        category: str = "raw",
    ) -> bool:
        """Delete a data file.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle interval.
            category: Data category.

        Returns:
            True if file was deleted.
        """
        path = self._get_path(symbol, timeframe, category)
        if path.exists():
            path.unlink()
            logger.info(f"Deleted {path}")
            return True
        return False

    def get_info(
        self,
        symbol: str,
        timeframe: str,
        category: str = "raw",
    ) -> dict | None:
        """Get metadata about a data file.

        Args:
            symbol: Trading pair symbol.
            timeframe: Candle interval.
            category: Data category.

        Returns:
            Dictionary with file metadata or None.
        """
        path = self._get_path(symbol, timeframe, category)

        if not path.exists():
            return None

        parquet_file = pq.ParquetFile(path)
        metadata = parquet_file.metadata
        schema = parquet_file.schema_arrow

        # Try to get date range from statistics
        start_date = None
        end_date = None

        try:
            # Assuming timestamp is the index or first column
            # We check all row groups to find global min/max
            # This handles unsorted data too, though time data is usually sorted
            min_vals = []
            max_vals = []

            # Find timestamp column index
            ts_col_idx = -1
            for i, name in enumerate(schema.names):
                if name == "timestamp" or name == "__index_level_0__":
                    ts_col_idx = i
                    break

            if ts_col_idx >= 0:
                for rg in range(metadata.num_row_groups):
                    col_meta = metadata.row_group(rg).column(ts_col_idx)
                    if col_meta.is_stats_set:
                        stats = col_meta.statistics
                        if stats.has_min_max:
                            min_vals.append(stats.min)
                            max_vals.append(stats.max)

                if min_vals and max_vals:
                    start_date = min(min_vals)
                    end_date = max(max_vals)
        except Exception as e:
            logger.debug(f"Could not extract date range from metadata: {e}")

        return {
            "path": path,
            "rows": metadata.num_rows,
            "columns": [field.name for field in schema],
            "size_mb": path.stat().st_size / (1024 * 1024),
            "compression": metadata.row_group(0).column(0).compression,
            "start_date": start_date,
            "end_date": end_date,
        }
