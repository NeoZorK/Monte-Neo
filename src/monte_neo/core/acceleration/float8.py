"""
Float8 precision support for GPU acceleration.

Supports E4M3 and E5M2 formats for memory bandwidth optimization.
"""

from __future__ import annotations

import numpy as np


class Float8Encoder:
    """Encoder for float8 formats."""
    
    def __init__(self, format_type: str = "e4m3") -> None:
        """
        Initialize float8 encoder.
        
        Args:
            format_type: 'e4m3' or 'e5m2'
        """
        self.format_type = format_type
        if format_type == "e4m3":
            self.mantissa_bits = 3
            self.exponent_bits = 4
            self.bias = 7
            self.max_exp = 15
        elif format_type == "e5m2":
            self.mantissa_bits = 2
            self.exponent_bits = 5
            self.bias = 15
            self.max_exp = 31
        else:
            raise ValueError(f"Unsupported format: {format_type}")
        
        self.mantissa_mask = (1 << self.mantissa_bits) - 1
        self.exponent_mask = (1 << self.exponent_bits) - 1
    
    def encode_scalar(self, value: float) -> int:
        """Encode single float32 to float8."""
        if np.isnan(value):
            return 0x7F if self.format_type == "e4m3" else 0x7C
        
        if value == 0.0:
            return 0
        
        # Handle infinity
        if np.isinf(value):
            sign = 1 if value < 0 else 0
            exp = self.exponent_mask
            mant = 0
            return (sign << 7) | (exp << self.mantissa_bits) | mant
        
        # Extract sign
        sign = 1 if value < 0 else 0
        value = abs(value)
        
        # Convert to binary representation
        bits = np.float32(value).view(np.uint32)
        
        # Extract exponent and mantissa from float32
        float32_bias = 127
        float32_exp = ((bits >> 23) & 0xFF) - float32_bias
        float32_mant = bits & 0x7FFFFF
        
        # Convert exponent
        mantissa_shift = 23 - self.mantissa_bits
        if float32_exp >= self.max_exp - self.bias:
            # Overflow -> infinity
            exp = self.exponent_mask
            mant = 0
        elif float32_exp < -self.bias:
            # Underflow -> zero
            return 0
        else:
            exp = float32_exp + self.bias
            # Convert mantissa
            # Shift mantissa to match float8 precision
            mant = (float32_mant >> mantissa_shift) & self.mantissa_mask
        
        # Round if necessary (round to nearest even)
        if mantissa_shift > 0:
            round_bit = (float32_mant >> (mantissa_shift - 1)) & 1
            sticky_bits = float32_mant & ((1 << (mantissa_shift - 1)) - 1)
            if round_bit and (sticky_bits or (mant & 1)):
                mant += 1
                if mant > self.mantissa_mask:
                    mant = 0
                    exp += 1
                    if exp > self.exponent_mask:
                        exp = self.exponent_mask
        
        return (sign << 7) | (exp << self.mantissa_bits) | mant
    
    def decode_scalar(self, encoded: int) -> float:
        """Decode float8 to float32."""
        if encoded == 0:
            return 0.0
        
        # Extract components
        sign = (encoded >> 7) & 1
        exp = (encoded >> self.mantissa_bits) & self.exponent_mask
        mant = encoded & self.mantissa_mask
        
        # Handle special cases
        if exp == self.exponent_mask:
            if mant == 0:
                return -np.inf if sign else np.inf
            else:
                # NaN
                return np.nan
        
        # Denormalized numbers
        if exp == 0:
            if mant == 0:
                return -0.0 if sign else 0.0
            else:
                # Denormalized: (-1)^sign * 2^(-bias+1) * mant/2^mantissa_bits
                value = (mant / (1 << self.mantissa_bits)) * (2 ** (-self.bias + 1))
                return -value if sign else value
        
        # Normalized numbers: (-1)^sign * 2^(exp-bias) * (1 + mant/2^mantissa_bits)
        value = (1 + mant / (1 << self.mantissa_bits)) * (2 ** (exp - self.bias))
        return -value if sign else value
    
    def encode_array(self, arr: np.ndarray) -> np.ndarray:
        """Encode numpy array to float8."""
        encoded = np.zeros(arr.shape, dtype=np.uint8)
        flat_arr = arr.flatten()
        flat_encoded = encoded.flatten()
        
        for i in range(flat_arr.size):
            flat_encoded[i] = self.encode_scalar(float(flat_arr[i]))
        
        return flat_encoded.reshape(arr.shape)
    
    def decode_array(self, encoded: np.ndarray) -> np.ndarray:
        """Decode float8 array to float32."""
        decoded = np.zeros(encoded.shape, dtype=np.float32)
        flat_encoded = encoded.flatten()
        flat_decoded = decoded.flatten()
        
        for i in range(flat_encoded.size):
            flat_decoded[i] = self.decode_scalar(int(flat_encoded[i]))
        
        return decoded.reshape(encoded.shape)


def pack_float8_array(arr: np.ndarray, format_type: str = "e4m3") -> tuple[np.ndarray, Float8Encoder]:
    """
    Pack float32 array into float8 format.
    
    Args:
        arr: Input float32 array
        format_type: 'e4m3' or 'e5m2'
    
    Returns:
        Tuple of (packed_uint8_array, encoder)
    """
    encoder = Float8Encoder(format_type)
    return encoder.encode_array(arr.astype(np.float32)), encoder


def unpack_float8_array(packed: np.ndarray, encoder: Float8Encoder) -> np.ndarray:
    """
    Unpack float8 array to float32.
    
    Args:
        packed: Packed uint8 array
        encoder: Float8Encoder instance
    
    Returns:
        Unpacked float32 array
    """
    return encoder.decode_array(packed)