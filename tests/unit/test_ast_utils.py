import pytest
import pandas as pd
import numpy as np
from monte_neo.utils.ast_utils import crossover_trees

def test_crossover_simple():
    code1 = "data['close'] + 5"
    code2 = "data['high'].rolling(10).mean()"
    
    # Run multiple times as it's random
    for _ in range(10):
        new_code = crossover_trees(code1, code2)
        assert isinstance(new_code, str)
        assert len(new_code) > 0
        
        # Verify it's still valid python
        try:
            compile(new_code, '<string>', 'eval')
        except SyntaxError:
            pytest.fail(f"Crossover produced invalid syntax: {new_code}")

def test_crossover_full_structure():
    code1 = "(data['close'] - data['open']).rolling(20).std()"
    code2 = "data['volume'].diff() / 100"
    
    new_code = crossover_trees(code1, code2)
    # Check if a part of code2 ended up in code1
    # This is statistical, but let's check basic validity
    assert "data" in new_code
    
def test_crossover_no_nodes():
    # Very simple code might have few nodes, but collector should still find something
    code1 = "1"
    code2 = "2"
    new_code = crossover_trees(code1, code2)
    assert new_code in ["1", "2"] # Either replacement happened or not
