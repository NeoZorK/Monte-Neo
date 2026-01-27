"""
Custom Indicator Template for Monte-Neo.

Use this file to define your own indicator logic.
The system will load this class, validate it, and run it through
the Monte Carlo stress test suite.

Rules:
1. Class name must be 'MyIndicator'.
2. Must inherit from 'BaseIndicator'.
3. Implement the 'generate' method.
"""

import pandas as pd
import talib
from monte_neo.indicators.base import BaseIndicator, IndicatorConfig

class MyIndicator(BaseIndicator):
    """User-defined custom indicator."""

    def __init__(self, config: IndicatorConfig | None = None):
        super().__init__(config)
        self.name = "MyCustomStrategy_v1"
        # Define your optimized parameters here if needed
        self.rsi_period = 14
        self.rsi_upper = 70
        self.rsi_lower = 30

    def generate(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate signals based on your custom logic.
        
        Args:
            data: DataFrame with 'open', 'high', 'low', 'close', 'volume'.
            
        Returns:
            DataFrame with added 'signal' column:
            1  = Buy
            -1 = Sell
            0  = Hold
        """
        df = data.copy()
        
        # Example Logic: RSI Reversal
        # 1. Calculate RSI
        rsi = talib.RSI(df['close'].values, timeperiod=self.rsi_period)
        
        # 2. Create Signal Column (Default 0)
        df['signal'] = 0
        
        # 3. Buy when RSI crosses above 30 (Oversold)
        # Note: This is a simplified vector operation.
        # For real trading, ensure you don't look ahead!
        df.loc[rsi < self.rsi_lower, 'signal'] = 1
        
        # 4. Sell when RSI crosses below 70 (Overbought)
        df.loc[rsi > self.rsi_upper, 'signal'] = -1
        
        return df

# For testing this file directly
if __name__ == "__main__":
    print("This is a template file. Run 'monte-neo' and select 'Test Custom Formula'.")
