# Authentication

## Binance API

Monte-Neo uses the official `binance-connector` library to fetch market data.

### Public Data
You do **not** need an API key to download public OHLCV data (Klines).

### Private Data
If you plan to use private data or want to avoid strict rate limits, provide your API keys in the `.env` file:

```bash
BINANCE_API_KEY=xxx
BINANCE_API_SECRET=xxx
```

### Security
Your API keys are never shared and are only used locally to communicate with Binance. Never commit your `.env` file to version control.
