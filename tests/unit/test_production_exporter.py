import os
import shutil
import pytest
from monte_neo.core.optimization.production_exporter import ProductionExporter
from monte_neo.indicators.sma import SMAIndicator

@pytest.fixture
def exporter():
    export_dir = "tests/temp_exports"
    if os.path.exists(export_dir):
        shutil.rmtree(export_dir)
    yield ProductionExporter(export_dir=export_dir)
    if os.path.exists(export_dir):
        shutil.rmtree(export_dir)

def test_export_files_creation(exporter):
    from monte_neo.indicators.base import IndicatorConfig
    config = IndicatorConfig(name="SMA", parameters={"fast_period": 14, "slow_period": 28})
    indicator = SMAIndicator(config=config)
    validation_results = {
        "robustness_score": 85.0,
        "is_production_ready": True,
        "pbo": 0.05
    }
    
    export_path = exporter.export(indicator, validation_results)
    
    assert os.path.exists(export_path)
    assert os.path.exists(os.path.join(export_path, "config.json"))
    assert os.path.exists(os.path.join(export_path, "production_indicator.cpp"))
    assert os.path.exists(os.path.join(export_path, "production_indicator.metal"))
    assert os.path.exists(os.path.join(export_path, "compile.sh"))
    assert os.path.exists(os.path.join(export_path, "README.md"))

def test_cpp_content(exporter):
    from monte_neo.indicators.base import IndicatorConfig
    config = IndicatorConfig(name="SMA", parameters={"fast_period": 20, "slow_period": 50})
    indicator = SMAIndicator(config=config)
    export_path = exporter.export(indicator, {"robustness_score": 90.0})
    
    with open(os.path.join(export_path, "production_indicator.cpp"), 'r') as f:
        content = f.read()
        assert "SMAIndicator" in content
        assert "period" in content
        assert "1.0.0" not in content # Just checking structure

def test_metal_content(exporter):
    from monte_neo.indicators.base import IndicatorConfig
    config = IndicatorConfig(name="SMA", parameters={"fast_period": 10, "slow_period": 20})
    indicator = SMAIndicator(config=config)
    export_path = exporter.export(indicator, {})
    
    with open(os.path.join(export_path, "production_indicator.metal"), 'r') as f:
        content = f.read()
        assert "SMAIndicator_kernel" in content
        assert "Candle" in content
