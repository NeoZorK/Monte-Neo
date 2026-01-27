
import re

def parse_metal_params(source_code: str, commission_bps: float = 5.0, slippage_bps: float = 5.0) -> list[float] | None:
    """Parse dynamic indicator source code into Metal kernel parameters."""
    code = source_code.replace(" ", "")
    
    # Layout: [type, p1, p2, p3, atr_period, sl_mult, tp_mult, ts_mult, commission_bps, slippage_bps]
    # Default SL/TP/TS params
    common_tail = [14.0, 1.5, 3.0, 2.0, commission_bps, slippage_bps]

    def parse_simple_cond(cond_code: str) -> list[float] | None:
        # 0. Bollinger Bands (check first to avoid SMA collision)
        # Example: data['close']<(data['close'].rolling(20).mean()-2.0*data['close'].rolling(20).std())
        bb_pattern = r"rolling\((\d+)\)\.mean\(\)[\-\+]([\d\.]+)\*.*rolling\(\1\)\.std\(\)"
        bb_matches = re.findall(bb_pattern, cond_code)
        if bb_matches:
            return [5.0, float(bb_matches[0][0]), float(bb_matches[0][1])]

        # 1. SMA Crossover Pattern: SMA(f) > SMA(s) or Price > SMA(s)
        sma_pattern = r"rolling\((\d+)\)\.mean\(\)"
        matches = re.findall(sma_pattern, cond_code)
        
        if len(matches) == 2:
            if "<" in cond_code:
                return [5.0, float(matches[0]), float(matches[1])] # sub_type 5 (SMA < SMA)
            else:
                # sub_type 7: SMA(f) > SMA(s)
                return [7.0, float(matches[0]), float(matches[1])]
        elif len(matches) == 1:
            if "data['close']>" in cond_code:
                return [0.0, float(matches[0]), 0.0] # sub_type 0 (Price > SMA)
            elif "data['close']<" in cond_code:
                return [4.0, float(matches[0]), 0.0] # sub_type 4 (Price < SMA)
        
        # 2. Rolling Max/Min
        max_pattern = r"data\['high'\]\.rolling\((\d+)\)\.max\(\)"
        max_matches = re.findall(max_pattern, cond_code)
        if max_matches and "data['close']>" in cond_code:
            return [1.0, float(max_matches[0]), 0.0] # sub_type 1

        min_pattern = r"data\['low'\]\.rolling\((\d+)\)\.min\(\)"
        min_matches = re.findall(min_pattern, cond_code)
        if min_matches and "data['close']<" in cond_code:
            return [2.0, float(min_matches[0]), 0.0] # sub_type 2

        # 3. Momentum
        shift_pattern = r"data\['close'\]\.shift\((\d+)\)"
        shift_matches = re.findall(shift_pattern, cond_code)
        if shift_matches:
            if "data['close']>" in cond_code:
                return [3.0, float(shift_matches[0]), 0.0] # sub_type 3
            elif "data['close']<" in cond_code:
                return [6.0, float(shift_matches[0]), 0.0] # sub_type 6
        
        # 4. RSI Pattern
        rsi_pattern = r"rsi\(.*?,?(\d+)\)"
        rsi_matches = re.findall(rsi_pattern, cond_code)
        if rsi_matches:
            period = float(rsi_matches[0])
            if "<" in cond_code:
                thresh_match = re.findall(r"<([\d\.]+)", cond_code)
                if thresh_match:
                    return [12.0, period, float(thresh_match[0])]
            elif ">" in cond_code:
                thresh_match = re.findall(r">([\d\.]+)", cond_code)
                if thresh_match:
                    return [13.0, period, float(thresh_match[0])]

        return None

    # Check for complex logic AND/OR
    if "&" in code or "|" in code:
        op_type = 0.0 if "&" in code else 1.0
        parts = code.split("&" if "&" in code else "|")
        if len(parts) == 2:
            p1_params = parse_simple_cond(parts[0])
            p2_params = parse_simple_cond(parts[1])
            if p1_params and p2_params:
                # New Layout for type 4: [4, op_type, sub1, p2_1, p3_1, sub2, p2_2, p3_2, comm, slip]
                return [4.0, op_type, p1_params[0], p1_params[1], p1_params[2], p2_params[0], p2_params[1], p2_params[2], commission_bps, slippage_bps]

    # Fallback to single condition parsing
    res = parse_simple_cond(code)
    if res:
        sub_type, p2_val, p3_val = res
        if sub_type == 7.0:
            return [0.0, p2_val, p3_val, 0.0] + common_tail
        if sub_type == 5.0:
            return [5.0, p2_val, p3_val, 0.0] + common_tail
        return [3.0, sub_type, p2_val, p3_val] + common_tail

    return None
