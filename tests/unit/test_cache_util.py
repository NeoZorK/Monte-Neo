import os

import numpy as np
import pytest

from monte_neo.utils.cache import (
    CACHE_DIR,
    clear_cache,
    get_data_hash,
    load_cache,
    load_calibration,
    save_cache,
    save_calibration,
)


@pytest.fixture(autouse=True)
def cleanup_cache():
    clear_cache()
    yield
    clear_cache()

def test_save_load_json():
    data = {"key": "value", "list": [1, 2, 3]}
    assert save_cache("test.json", data) is True
    loaded = load_cache("test.json")
    assert loaded == data

def test_save_load_pickle():
    data = np.array([1, 2, 3])
    assert save_cache("test.pkl", data, use_pickle=True) is True
    loaded = load_cache("test.pkl", use_pickle=True)
    assert np.array_equal(loaded, data)

def test_get_data_hash():
    d1 = "some data"
    d2 = "some data"
    d3 = "other data"
    assert get_data_hash(d1) == get_data_hash(d2)
    assert get_data_hash(d1) != get_data_hash(d3)

def test_calibration_cache():
    params = {"p1": 10, "p2": 20}
    data = "mock_data"
    assert save_calibration("SMA", data, params) is True
    loaded = load_calibration("SMA", data)
    assert loaded == params

def test_clear_cache():
    save_cache("f1.json", {"a": 1})
    save_cache("f2.json", {"b": 2})
    assert len(os.listdir(CACHE_DIR)) == 2
    clear_cache("f1.json")
    assert len(os.listdir(CACHE_DIR)) == 1
    clear_cache()
    assert len(os.listdir(CACHE_DIR)) == 0
