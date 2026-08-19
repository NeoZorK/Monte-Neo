from unittest.mock import MagicMock

from monte_neo.cli.menu.leadership_optimizer import SmartPipelineOptimizer


class MockValidationResult:
    def __init__(self, warnings=None):
        self.warnings = warnings or []

def test_optimizer_overfitting_adjustment():
    # Setup
    menu = MagicMock()
    menu._mutation_rate = 0.5
    menu._crossover_rate = 0.5
    menu._selected_timeframe = "1h"
    optimizer = SmartPipelineOptimizer(menu)
    
    # Mock validation result with overfitting warnings
    val_res = MockValidationResult(warnings=["OOS/IS ratio too high"])
    gate_results = {"final_score": 45.0}
    
    # Run
    optimizer.brainstorm_and_adjust(val_res, gate_results)
    
    # Verify
    assert menu._mutation_rate < 0.5
    assert menu._crossover_rate > 0.5
    assert "Overfitting" in optimizer.last_failure_reason
    # Initial is index 4 (1h), should move to index 5 (4h)
    assert menu._selected_timeframe == "4h"

def test_optimizer_low_trades_adjustment():
    # Setup
    menu = MagicMock()
    menu._pop_size = 50
    menu._selected_timeframe = "1h"
    optimizer = SmartPipelineOptimizer(menu)
    
    # Mock validation result with low trades warnings
    val_res = MockValidationResult(warnings=["Insufficient trades found"])
    gate_results = {"final_score": 30.0}
    
    # Run
    optimizer.brainstorm_and_adjust(val_res, gate_results)
    
    # Verify
    assert menu._pop_size > 50
    assert "selective" in optimizer.last_failure_reason
    assert menu._selected_timeframe == "30m" # Switched from 1h to 30m

def test_optimizer_ensure_data_auto_download():
    # Setup
    menu = MagicMock()
    menu.storage.load.return_value = None
    menu.config.auto_download_data = True
    optimizer = SmartPipelineOptimizer(menu)
    
    with MagicMock() as mock_downloader:
        from unittest.mock import patch
        with patch("monte_neo.cli.menu.leadership_optimizer.BinanceDownloader", return_value=mock_downloader):
            mock_downloader.download.return_value = MagicMock(empty=False)
            
            # Run
            res = optimizer.ensure_data("BTCUSDT", "1h")
            
            # Verify
            assert res is not None
            mock_downloader.download.assert_called()
            menu.storage.save.assert_called()

def test_optimizer_low_quality_adjustment():
    # Setup
    menu = MagicMock()
    menu._generations = 20
    menu._pop_size = 50
    optimizer = SmartPipelineOptimizer(menu)
    
    # Mock low quality score
    val_res = MockValidationResult(warnings=[])
    gate_results = {"final_score": 20.0}
    
    # Run
    optimizer.brainstorm_and_adjust(val_res, gate_results)
    
    # Verify
    assert menu._generations > 20
    assert menu._pop_size > 50
    assert "Low overall quality" in optimizer.last_failure_reason

def test_best_score_tracking():
    # Setup
    menu = MagicMock()
    menu._generations = 20
    menu._pop_size = 50
    optimizer = SmartPipelineOptimizer(menu)
    
    # Iteration 1
    optimizer.brainstorm_and_adjust(MockValidationResult(), {"final_score": 40.0})
    assert optimizer.best_score_ever == 40.0
    
    # Iteration 2 (lower score)
    optimizer.brainstorm_and_adjust(MockValidationResult(), {"final_score": 30.0})
    assert optimizer.best_score_ever == 40.0
    
    # Iteration 3 (higher score)
    optimizer.brainstorm_and_adjust(MockValidationResult(), {"final_score": 55.0})
    assert optimizer.best_score_ever == 55.0
