"""Binance data downloader module.

Downloads OHLCV data from Binance API and saves in Parquet format.
"""

from __future__ import annotations

import os
import time
from collections.abc import Callable
from datetime import datetime, timedelta

import pandas as pd
from binance.spot import Spot

from monte_neo.utils.logger import get_logger

logger = get_logger(__name__)


class BinanceDownloader:
    """Download OHLCV data from Binance."""

    TIMEFRAME_MAP = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "1h",
        "4h": "4h",
        "1d": "1d",
        "1w": "1w",
    }

    COLUMNS = [
        "timestamp",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "close_time",
        "quote_volume",
        "trades",
        "taker_buy_base",
        "taker_buy_quote",
        "ignore",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        api_secret: str | None = None,
    ) -> None:
        """Initialize Binance client.

        Args:
            api_key: Optional Binance API key.
            api_secret: Optional Binance API secret.
        """
        self.api_key = api_key or os.getenv("BINANCE_API_KEY", "")
        self.api_secret = api_secret or os.getenv("BINANCE_API_SECRET", "")
        self.client = Spot(api_key=self.api_key, api_secret=self.api_secret)
        logger.info("Binance client initialized")

    def get_available_symbols(self) -> list[str]:
        """Get list of available trading symbols.

        Returns:
            List of symbol strings (e.g., ['BTCUSDT', 'ETHUSDT']).
        """
        info = self.client.exchange_info()
        return sorted(
            [s["symbol"] for s in info["symbols"] if s["status"] == "TRADING"]
        )

    def _fetch_klines(
        self,
        symbol: str,
        interval: str,
        start_ms: int,
        end_ms: int,
    ) -> list[list[str | int | float]]:
        klines: list[list[str | int | float]] = []
        current_start = start_ms
        while current_start < end_ms:
            try:
                batch = self.client.klines(
                    symbol=symbol,
                    interval=interval,
                    startTime=current_start,
                    endTime=end_ms,
                    limit=1000,
                )
                if not batch:
                    break
                klines.extend(batch)
                last_close = int(batch[-1][6])
                next_start = last_close + 1

                # Compliance with Binance rate limits (small delay between batches)
                if len(batch) >= 1000:
                    time.sleep(0.1) # 100ms delay between 1000-candle batches

                if next_start <= current_start:
                    break
                current_start = next_start
            except Exception as e:
                if "429" in str(e) or "rate limit" in str(e).lower():
                    logger.warning("Rate limit hit, sleeping for 10 seconds...")
                    time.sleep(10)
                    continue
                raise e
        return klines

    def download(
        self,
        symbol: str,
        timeframe: str,
        start_date: datetime | str,
        end_date: datetime | str | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> pd.DataFrame:
        """Download OHLCV data from Binance.

        Args:
            symbol: Trading pair symbol (e.g., 'BTCUSDT').
            timeframe: Candle interval (e.g., '1h', '4h', '1d').
            start_date: Start date for data.
            end_date: End date for data (default: now).

        Returns:
            DataFrame with OHLCV data.
        """
        if isinstance(start_date, str):
            start_date = datetime.fromisoformat(start_date)
        if end_date is None:
            end_date = datetime.now()
        elif isinstance(end_date, str):
            end_date = datetime.fromisoformat(end_date)

        interval = self.TIMEFRAME_MAP.get(timeframe)
        if interval is None:
            raise ValueError(f"Invalid timeframe: {timeframe}")

        if progress_callback:
            progress_callback(0, 100, "Initializing...")

        chunks = []
        current_start = start_date
        total_days = (end_date - start_date).days or 1

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=30), end_date)

            logger.debug(f"Fetching chunk: {current_start} to {current_end}")
            if progress_callback:
                pct = int(((current_start - start_date).days / total_days) * 100)
                progress_callback(
                    pct, 100, f"Fetching {current_start.strftime('%Y-%m')}"
                )

            start_ms = int(current_start.timestamp() * 1000)
            end_ms = int(current_end.timestamp() * 1000)
            klines = self._fetch_klines(
                symbol=symbol,
                interval=interval,
                start_ms=start_ms,
                end_ms=end_ms,
            )
            chunks.extend(klines)
            current_start = current_end + timedelta(milliseconds=1)

        if progress_callback:
            progress_callback(100, 100, "Processing...")

        df = pd.DataFrame(chunks, columns=self.COLUMNS)
        df = self._process_dataframe(df)

        if progress_callback:
            progress_callback(100, 100, "Done")

        logger.info(f"Downloaded {len(df)} candles")
        return df

    def _process_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process raw Binance data.

        Args:
            df: Raw DataFrame from Binance API.

        Returns:
            Processed DataFrame with proper types.
        """
        # Convert timestamp to datetime
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)

        # Convert price and volume columns to float
        price_cols = ["open", "high", "low", "close", "volume", "quote_volume"]
        for col in price_cols:
            df[col] = df[col].astype(float)

        # Keep only essential columns
        df = df[["open", "high", "low", "close", "volume"]]

        return df

    def download_multiple(
        self,
        symbols: list[str],
        timeframe: str,
        start_date: datetime | str,
        end_date: datetime | str | None = None,
    ) -> dict[str, pd.DataFrame]:
        """Download data for multiple symbols.

        Args:
            symbols: List of trading pair symbols.
            timeframe: Candle interval.
            start_date: Start date for data.
            end_date: End date for data.

        Returns:
            Dictionary mapping symbols to DataFrames.
        """
        result = {}
        for symbol in symbols:
            try:
                result[symbol] = self.download(symbol, timeframe, start_date, end_date)
            except Exception as e:
                logger.error(f"Failed to download {symbol}: {e}")
        return result


def download_sample_data(
    symbol: str = "BTCUSDT",
    timeframe: str = "1h",
    days: int = 365,
) -> pd.DataFrame:
    """Convenience function to download sample data.

    Args:
        symbol: Trading pair symbol.
        timeframe: Candle interval.
        days: Number of days of historical data.

    Returns:
        DataFrame with OHLCV data.
    """
    downloader = BinanceDownloader()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    return downloader.download(symbol, timeframe, start_date, end_date)
