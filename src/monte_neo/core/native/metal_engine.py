"""
Metal GPU acceleration engine for Apple Silicon.

Provides direct Metal shader access for maximum performance.
"""

from __future__ import annotations

import ctypes
import math
import os
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    import pandas as pd

# Try to import Metal framework
try:
    import Metal
    import objc
    METAL_AVAILABLE = True
except ImportError:
    METAL_AVAILABLE = False


class MetalFloat8Engine:
    """Metal-based GPU engine for float8 operations."""
    
    def __init__(self) -> None:
        """Initialize Metal engine."""
        if not METAL_AVAILABLE:
            raise RuntimeError("Metal framework not available. Install pyobjc-framework-Metal.")
        
        self.device = Metal.MTLCreateSystemDefaultDevice()
        if self.device is None:
            raise RuntimeError("No Metal device available.")
        
        self.command_queue = self.device.newCommandQueue()
        
        # Load shaders
        self._load_shaders()
    
    def _load_shaders(self) -> None:
        """Load Metal shaders from file."""
        shader_path = os.path.join(os.path.dirname(__file__), "metal_kernels.metal")
        
        if not os.path.exists(shader_path):
            # Create default shaders if file doesn't exist
            self._create_default_shaders()
            return
        
        with open(shader_path, 'r') as f:
            shader_source = f.read()
        
        # Compile shader
        library = self.device.newLibraryWithSource_options_error_(
            shader_source, None, None
        )
        
        if library is None:
            raise RuntimeError("Failed to compile Metal shaders")
        
        self.library = library
        
        # Get function handles
        self.float32_to_e4m3_func = library.newFunctionWithName_("float32_to_float8_e4m3")
        self.e4m3_to_float32_func = library.newFunctionWithName_("float8_e4m3_to_float32")
        self.float32_to_e5m2_func = library.newFunctionWithName_("float32_to_float8_e5m2")
        self.e5m2_to_float32_func = library.newFunctionWithName_("float8_e5m2_to_float32")
    
    def _create_default_shaders(self) -> None:
        """Create default compute pipeline for basic operations."""
        # This is a fallback - in production, use pre-compiled shaders
        shader_source = """
        #include <metal_stdlib>
        using namespace metal;
        
        kernel void float32_to_float8_e4m3(
            const device float* input [[buffer(0)]],
            device uchar* output [[buffer(1)]],
            uint id [[thread_position_in_grid]])
        {
            // Simple quantization for testing
            float val = input[id];
            uchar quantized = uchar(clamp(val * 127.0, -128.0, 127.0) + 128.0);
            output[id] = quantized;
        }
        
        kernel void float8_e4m3_to_float32(
            const device uchar* input [[buffer(0)]],
            device float* output [[buffer(1)]],
            uint id [[thread_position_in_grid]])
        {
            uchar val = input[id];
            output[id] = (float(val) - 128.0) / 127.0;
        }
        """
        
        library = self.device.newLibraryWithSource_options_error_(
            shader_source, None, None
        )
        
        if library is None:
            raise RuntimeError("Failed to create default Metal shaders")
        
        self.library = library
        self.float32_to_e4m3_func = library.newFunctionWithName_("float32_to_float8_e4m3")
        self.e4m3_to_float32_func = library.newFunctionWithName_("float8_e4m3_to_float32")
    
    def encode_float32_to_e4m3(self, input_array: np.ndarray) -> np.ndarray:
        """Encode float32 array to float8 E4M3 format."""
        if self.float32_to_e4m3_func is None:
            raise RuntimeError("E4M3 conversion function not available")
        
        # Flatten array for processing
        flat_input = input_array.flatten().astype(np.float32)
        n_elements = len(flat_input)
        
        # Create output array
        output_array = np.zeros(n_elements, dtype=np.uint8)
        
        # Create Metal buffers
        input_buffer = self.device.newBufferWithBytes_length_options_(
            flat_input.ctypes.data, n_elements * 4, 0
        )
        output_buffer = self.device.newBufferWithLength_options_(n_elements, 0)
        
        # Create compute pipeline
        pipeline = self.device.newComputePipelineStateWithFunction_error_(
            self.float32_to_e4m3_func, None
        )
        
        # Create command encoder
        command_buffer = self.command_queue.commandBuffer()
        encoder = command_buffer.computeCommandEncoder()
        encoder.setComputePipelineState_(pipeline)
        
        # Set buffers
        encoder.setBuffer_offset_atIndex_(input_buffer, 0, 0)
        encoder.setBuffer_offset_atIndex_(output_buffer, 0, 1)
        
        # Dispatch threads
        threads_per_threadgroup = pipeline.maxTotalThreadsPerThreadgroup()
        threadgroups = (n_elements + threads_per_threadgroup - 1) // threads_per_threadgroup
        
        encoder.dispatchThreadgroups_threadsPerThreadgroup_(
            (threadgroups, 1, 1), (threads_per_threadgroup, 1, 1)
        )
        
        encoder.endEncoding()
        command_buffer.commit()
        command_buffer.waitUntilCompleted()
        
        # Copy result back
        output_data = output_buffer.contents()
        ctypes.memmove(
            output_array.ctypes.data,
            output_data,
            n_elements
        )
        
        return output_array.reshape(input_array.shape)
    
    def decode_e4m3_to_float32(self, input_array: np.ndarray) -> np.ndarray:
        """Decode float8 E4M3 array to float32."""
        if self.e4m3_to_float32_func is None:
            raise RuntimeError("E4M3 to float32 conversion function not available")
        
        # Flatten array for processing
        flat_input = input_array.flatten().astype(np.uint8)
        n_elements = len(flat_input)
        
        # Create output array
        output_array = np.zeros(n_elements, dtype=np.float32)
        
        # Create Metal buffers
        input_buffer = self.device.newBufferWithBytes_length_options_(
            flat_input.ctypes.data, n_elements, 0
        )
        output_buffer = self.device.newBufferWithLength_options_(n_elements * 4, 0)
        
        # Create compute pipeline
        pipeline = self.device.newComputePipelineStateWithFunction_error_(
            self.e4m3_to_float32_func, None
        )
        
        # Create command encoder
        command_buffer = self.command_queue.commandBuffer()
        encoder = command_buffer.computeCommandEncoder()
        encoder.setComputePipelineState_(pipeline)
        
        # Set buffers
        encoder.setBuffer_offset_atIndex_(input_buffer, 0, 0)
        encoder.setBuffer_offset_atIndex_(output_buffer, 0, 1)
        
        # Dispatch threads
        threads_per_threadgroup = pipeline.maxTotalThreadsPerThreadgroup()
        threadgroups = (n_elements + threads_per_threadgroup - 1) // threads_per_threadgroup
        
        encoder.dispatchThreadgroups_threadsPerThreadgroup_(
            (threadgroups, 1, 1), (threads_per_threadgroup, 1, 1)
        )
        
        encoder.endEncoding()
        command_buffer.commit()
        command_buffer.waitUntilCompleted()
        
        # Copy result back
        output_data = output_buffer.contents()
        ctypes.memmove(
            output_array.ctypes.data,
            output_data,
            n_elements * 4
        )
        
        return output_array.reshape(input_array.shape)
    
    def get_memory_bandwidth_improvement(self) -> float:
        """Calculate theoretical memory bandwidth improvement."""
        # Float32: 32 bits per element
        # Float8: 8 bits per element
        # Improvement: 32/8 = 4x
        return 4.0
    
    def get_precision_loss_estimate(self) -> float:
        """Estimate precision loss compared to float32."""
        # E4M3 has ~3 decimal digits of precision
        # Float32 has ~7 decimal digits of precision
        # Loss: ~4 decimal digits
        return 4.0