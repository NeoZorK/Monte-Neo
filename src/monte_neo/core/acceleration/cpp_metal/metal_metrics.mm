#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include "include/metal_bridge.hpp"
#include "metal_bridge_internal.hpp"
#include <vector>
#include <iostream>

namespace monte_neo {

std::vector<BacktestResult> MetalBacktestBridge::calculate_metrics(
    const float* close_prices,
    const float* high_prices,
    const float* low_prices,
    const int* signals,
    const float* params,
    int n_pop,
    int n_scenarios,
    int n_time,
    size_t close_size,
    size_t signals_size,
    size_t params_size
) {
    int total_results = n_pop * n_scenarios;
    std::vector<BacktestResult> results(total_results);
    
    if (!pimpl->metricsPipeline) return results;

    @autoreleasepool {
        id<MTLBuffer> closeBuffer;
        if (pimpl->cachedDataCount == n_time && pimpl->cachedDataBuffer) {
            closeBuffer = pimpl->cachedDataBuffer;
        } else {
            closeBuffer = [pimpl->device newBufferWithBytes:close_prices 
                                                   length:close_size * sizeof(float) 
                                                  options:MTLResourceStorageModeShared];
        }

        id<MTLBuffer> signalBuffer = [pimpl->device newBufferWithBytes:signals 
                                                               length:signals_size * sizeof(int) 
                                                              options:MTLResourceStorageModeShared];
        id<MTLBuffer> paramsBuffer = [pimpl->device newBufferWithBytes:params 
                                                               length:params_size * sizeof(float) 
                                                              options:MTLResourceStorageModeShared];
        id<MTLBuffer> resultsBuffer = [pimpl->device newBufferWithLength:total_results * sizeof(BacktestResult) 
                                                               options:MTLResourceStorageModeShared];
        
        uint32_t n_time_val = (uint32_t)n_time;
        
        id<MTLCommandBuffer> commandBuffer = [pimpl->commandQueue commandBuffer];
        id<MTLComputeCommandEncoder> encoder = [commandBuffer computeCommandEncoder];
        
        [encoder setComputePipelineState:pimpl->metricsPipeline];
        [encoder setBuffer:closeBuffer offset:0 atIndex:0];
        [encoder setBuffer:signalBuffer offset:0 atIndex:1];
        [encoder setBuffer:resultsBuffer offset:0 atIndex:2];
        [encoder setBytes:&n_time_val length:sizeof(uint32_t) atIndex:3];
        [encoder setBuffer:paramsBuffer offset:0 atIndex:4];

        MTLSize gridSize = MTLSizeMake(n_pop, n_scenarios, 1);
        NSUInteger maxThreads = pimpl->metricsPipeline.maxTotalThreadsPerThreadgroup;
        MTLSize threadGroupSize = (maxThreads >= 256) ? MTLSizeMake(16, 16, 1) : MTLSizeMake(8, 8, 1);

        [encoder dispatchThreads:gridSize threadsPerThreadgroup:threadGroupSize];
        [encoder endEncoding];
        [commandBuffer commit];
        [commandBuffer waitUntilCompleted];

        std::memcpy(results.data(), [resultsBuffer contents], total_results * sizeof(BacktestResult));
    }
    return results;
}

} // namespace monte_neo
