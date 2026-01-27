import json
import os
from typing import Dict, Any, List
from monte_neo.indicators.base import BaseIndicator

class ProductionExporter:
    """Exports validated indicators for production use."""
    
    def __init__(self, export_dir: str = "exports/production"):
        self.export_dir = export_dir
        os.makedirs(self.export_dir, exist_ok=True)
        
    def export(self, indicator: BaseIndicator, validation_results: Dict[str, Any], metadata: Dict[str, Any] = None) -> str:
        """
        Exports indicator config and validation certificate to JSON.
        
        Returns:
            Path to the exported file.
        """
        export_data = {
            "indicator_type": indicator.__class__.__name__,
            "parameters": indicator.get_parameters(),
            "formula": indicator.get_formula(),
            "validation": validation_results,
            "metadata": metadata or {},
            "version": "1.0.0"
        }
        
        # Create a safe filename
        safe_name = f"indicator_{indicator.__class__.__name__}_{id(indicator)}.json"
        export_path = os.path.join(self.export_dir, safe_name)
        
        with open(export_path, 'w') as f:
            json.dump(export_data, f, indent=4)
            
        return export_path
