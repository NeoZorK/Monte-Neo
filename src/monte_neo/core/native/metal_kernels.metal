#include <metal_stdlib>
#include <simd/simd.h>

using namespace metal;

// Float8 E4M3 format
struct float8_e4m3 {
    uchar data;
    
    float8_e4m3() : data(0) {}
    float8_e4m3(uchar d) : data(d) {}
    
    // Convert to float32
    float to_float() const {
        if (data == 0) return 0.0f;
        
        uchar sign = (data >> 7) & 0x1;
        uchar exponent = (data >> 3) & 0xF;
        uchar mantissa = data & 0x7;
        
        if (exponent == 0xF) {
            // Infinity or NaN
            return (mantissa == 0) ? 
                ((sign ? -1.0f : 1.0f) * INFINITY) : NAN;
        }
        
        float result;
        if (exponent == 0) {
            // Denormalized
            result = mantissa / 8.0f * pow(2.0f, -6.0f);
        } else {
            // Normalized
            result = (1.0f + mantissa / 8.0f) * pow(2.0f, float(exponent) - 7.0f);
        }
        
        return sign ? -result : result;
    }
    
    // Convert from float32
    static float8_e4m3 from_float(float f) {
        if (isnan(f)) return float8_e4m3(0x7F);
        if (isinf(f)) return float8_e4m3(0x7F);
        if (f == 0.0f) return float8_e4m3(0);
        
        uint sign_bit = f < 0.0f ? 1 : 0;
        float abs_f = fabs(f);
        
        // Find exponent
        int exponent = 0;
        float mantissa = abs_f;
        
        if (abs_f >= 1.0f) {
            while (mantissa >= 2.0f && exponent < 15) {
                mantissa /= 2.0f;
                exponent++;
            }
        } else {
            while (mantissa < 1.0f && exponent > -6) {
                mantissa *= 2.0f;
                exponent--;
            }
        }
        
        if (exponent > 15) {
            // Overflow to infinity
            return float8_e4m3((sign_bit << 7) | 0x7F);
        }
        
        if (exponent < -6) {
            // Underflow to zero
            return float8_e4m3(sign_bit << 7);
        }
        
        // Quantize mantissa
        uchar quantized_mant = uchar(round((mantissa - 1.0f) * 8.0f));
        if (quantized_mant >= 8) {
            quantized_mant = 0;
            exponent++;
        }
        
        uchar result = (sign_bit << 7) | ((exponent + 7) << 3) | quantized_mant;
        return float8_e4m3(result);
    }
};

// Float8 E5M2 format
struct float8_e5m2 {
    uchar data;
    
    float8_e5m2() : data(0) {}
    float8_e5m2(uchar d) : data(d) {}
    
    // Convert to float32
    float to_float() const {
        if (data == 0) return 0.0f;
        
        uchar sign = (data >> 7) & 0x1;
        uchar exponent = (data >> 2) & 0x1F;
        uchar mantissa = data & 0x3;
        
        if (exponent == 0x1F) {
            // Infinity or NaN
            return (mantissa == 0) ? 
                ((sign ? -1.0f : 1.0f) * INFINITY) : NAN;
        }
        
        float result;
        if (exponent == 0) {
            // Denormalized
            result = mantissa / 4.0f * pow(2.0f, -14.0f);
        } else {
            // Normalized
            result = (1.0f + mantissa / 4.0f) * pow(2.0f, float(exponent) - 15.0f);
        }
        
        return sign ? -result : result;
    }
    
    // Convert from float32
    static float8_e5m2 from_float(float f) {
        if (isnan(f)) return float8_e5m2(0x7C);
        if (isinf(f)) return float8_e5m2(0x7C);
        if (f == 0.0f) return float8_e5m2(0);
        
        uint sign_bit = f < 0.0f ? 1 : 0;
        float abs_f = fabs(f);
        
        // Find exponent
        int exponent = 0;
        float mantissa = abs_f;
        
        if (abs_f >= 1.0f) {
            while (mantissa >= 2.0f && exponent < 31) {
                mantissa /= 2.0f;
                exponent++;
            }
        } else {
            while (mantissa < 1.0f && exponent > -14) {
                mantissa *= 2.0f;
                exponent--;
            }
        }
        
        if (exponent > 31) {
            // Overflow to infinity
            return float8_e5m2((sign_bit << 7) | 0x7C);
        }
        
        if (exponent < -14) {
            // Underflow to zero
            return float8_e5m2(sign_bit << 7);
        }
        
        // Quantize mantissa
        uchar quantized_mant = uchar(round((mantissa - 1.0f) * 4.0f));
        if (quantized_mant >= 4) {
            quantized_mant = 0;
            exponent++;
        }
        
        uchar result = (sign_bit << 7) | ((exponent + 15) << 2) | quantized_mant;
        return float8_e5m2(result);
    }
};

// Kernel for converting float32 array to float8 E4M3
kernel void float32_to_float8_e4m3(
    const device float* input [[buffer(0)]],
    device uchar* output [[buffer(1)]],
    uint id [[thread_position_in_grid]])
{
    float val = input[id];
    float8_e4m3 f8 = float8_e4m3::from_float(val);
    output[id] = f8.data;
}

// Kernel for converting float8 E4M3 array to float32
kernel void float8_e4m3_to_float32(
    const device uchar* input [[buffer(0)]],
    device float* output [[buffer(1)]],
    uint id [[thread_position_in_grid]])
{
    float8_e4m3 f8(input[id]);
    output[id] = f8.to_float();
}

// Kernel for converting float32 array to float8 E5M2
kernel void float32_to_float8_e5m2(
    const device float* input [[buffer(0)]],
    device uchar* output [[buffer(1)]],
    uint id [[thread_position_in_grid]])
{
    float val = input[id];
    float8_e5m2 f8 = float8_e5m2::from_float(val);
    output[id] = f8.data;
}

// Kernel for converting float8 E5M2 array to float32
kernel void float8_e5m2_to_float32(
    const device uchar* input [[buffer(0)]],
    device float* output [[buffer(1)]],
    uint id [[thread_position_in_grid]])
{
    float8_e5m2 f8(input[id]);
    output[id] = f8.to_float();
}

// Optimized kernel for scenario generation with float8
kernel void generate_shuffle_scenarios_float8(
    const device uchar* base_prices [[buffer(0)]],
    device uchar* scenarios [[buffer(1)]],
    const device uint* random_indices [[buffer(2)]],
    constant uint& num_scenarios [[buffer(3)]],
    constant uint& time_steps [[buffer(4)]],
    uint id [[thread_position_in_grid]])
{
    uint scenario_idx = id / time_steps;
    uint time_idx = id % time_steps;
    
    if (scenario_idx >= num_scenarios || time_idx >= time_steps) return;
    
    if (time_idx == 0) {
        // First price is always the base price
        scenarios[id] = base_prices[0];
        return;
    }
    
    // Get random index for this time step
    uint random_idx = random_indices[(scenario_idx * (time_steps - 1)) + (time_idx - 1)];
    
    // Use the price from the random index
    float8_e4m3 base_price(base_prices[random_idx + 1]);
    scenarios[id] = base_price.data;
}

// Memory coalescing kernel for better performance
kernel void generate_shuffle_scenarios_coalesced(
    const device uchar* base_prices [[buffer(0)]],
    device uchar* scenarios [[buffer(1)]],
    const device uint* random_indices [[buffer(2)]],
    constant uint& num_scenarios [[buffer(3)]],
    constant uint& time_steps [[buffer(4)]],
    uint id [[thread_position_in_grid]])
{
    // Coalesced memory access pattern: adjacent threads access adjacent time steps
    // Output layout is (num_scenarios, time_steps)
    uint global_idx = id;
    uint total_elements = num_scenarios * time_steps;
    
    if (global_idx >= total_elements) return;
    
    uint scenario_idx = global_idx / time_steps;
    uint time_idx = global_idx % time_steps;
    
    uint output_idx = global_idx; // Since global_idx = scenario_idx * time_steps + time_idx
    
    if (time_idx == 0) {
        scenarios[output_idx] = base_prices[0];
        return;
    }
    
    uint random_idx = random_indices[scenario_idx * (time_steps - 1) + (time_idx - 1)];
    scenarios[output_idx] = base_prices[random_idx + 1];
}

// Tiled kernel for better cache utilization
kernel void generate_shuffle_scenarios_tiled(
    const device uchar* base_prices [[buffer(0)]],
    device uchar* scenarios [[buffer(1)]],
    const device uint* random_indices [[buffer(2)]],
    constant uint& num_scenarios [[buffer(3)]],
    constant uint& time_steps [[buffer(4)]],
    uint3 gid [[thread_position_in_grid]],
    uint3 tid [[thread_position_in_threadgroup]],
    uint3 tpg [[threads_per_threadgroup]])
{
    const uint TILE_SIZE = 16;
    
    // Shared memory for tile
    threadgroup uchar tile_prices[TILE_SIZE];
    threadgroup uint tile_indices[TILE_SIZE];
    
    uint scenario_idx = gid.x;
    uint time_idx = gid.y;
    uint local_idx = tid.x + tid.y * tpg.x;
    
    if (scenario_idx >= num_scenarios || time_idx >= time_steps) return;
    
    // Load tile data into shared memory
    if (local_idx < TILE_SIZE) {
        uint load_idx = (scenario_idx / TILE_SIZE) * TILE_SIZE + local_idx;
        if (load_idx < num_scenarios && time_idx < time_steps) {
            tile_prices[local_idx] = base_prices[time_idx];
            if (time_idx > 0 && local_idx < TILE_SIZE) {
                tile_indices[local_idx] = random_indices[load_idx * (time_steps - 1) + (time_idx - 1)];
            }
        }
    }
    
    threadgroup_barrier(mem_flags::mem_threadgroup);
    
    uint output_idx = scenario_idx * time_steps + time_idx;
    
    if (time_idx == 0) {
        scenarios[output_idx] = base_prices[0];
    } else {
        uint local_scenario = scenario_idx % TILE_SIZE;
        uint random_idx = tile_indices[local_scenario];
        scenarios[output_idx] = base_prices[random_idx + 1];
    }
}