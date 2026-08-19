from monte_neo.indicators.metal_parser import parse_metal_params


def test_parse_metal_params_sma():
    # Price > SMA(20)
    source = "data['close'] > data['close'].rolling(20).mean()"
    params = parse_metal_params(source)
    assert params is not None
    # sub_type 0 for Price > SMA
    assert params[1] == 0.0
    assert params[2] == 20.0

def test_parse_metal_params_sma_cross():
    # SMA(10) > SMA(20)
    source = "data['close'].rolling(10).mean() > data['close'].rolling(20).mean()"
    params = parse_metal_params(source)
    assert params is not None
    # type 0, sub_type 7 in parse_simple_cond becomes p2, p3 in result
    assert params[0] == 0.0
    assert params[1] == 10.0
    assert params[2] == 20.0

def test_parse_metal_params_rsi():
    source = "rsi(data['close'], 14) > 70"
    params = parse_metal_params(source)
    assert params is not None
    # sub_type 13 for RSI > thresh
    assert params[1] == 13.0
    assert params[2] == 14.0 # period
    assert params[3] == 70.0 # thresh

def test_parse_metal_params_complex():
    # SMA cross & RSI
    source = "data['close'] > data['close'].rolling(20).mean() & rsi(data['close'], 14) < 30"
    params = parse_metal_params(source)
    assert params is not None
    assert params[0] == 4.0 # type 4 for complex
    assert params[1] == 0.0 # op_type 0 for &

def test_parse_metal_params_invalid():
    assert parse_metal_params("invalid code") is None
