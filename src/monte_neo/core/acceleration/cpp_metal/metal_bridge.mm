#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include "include/metal_bridge.hpp"
#include <iostream>
#include <vector>

namespace monte_neo {

class MetalBacktestBridge::Impl {
public:
    id<MTLDevice> device;
    id<MTLCommandQueue> commandQueue;
    id<MTLComputePipelineState> pipelineState;

    Impl() : device(nil), commandQueue(nil), pipelineState(nil) {}
    
    bool init() {
        @autoreleasepool {
            device = MTLCreateSystemDefaultDevice();
            if (!device) return false;

            commandQueue = [device newCommandQueue];
            
            NSError* error = nil;
            NSString* path = @"src/monte_neo/core/acceleration/cpp_metal/shaders/backtest_kernels.metal";
            NSString* source = [NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:&error];
            
            if (!source) {
                std::cerr << "Failed to load shaders: " << [[error localizedDescription] UTF8String] << std::endl;
                return false;
            }

            id<MTLLibrary> library = [device newLibraryWithSource:source options:nil error:&error];
            if (!library) {
                std::cerr << "Failed to create library: " << [[error localizedDescription] UTF8String] << std::endl;
                return false;
            }

            id<MTLFunction> function = [library newFunctionWithName:@"backtest_kernel"];
            pipelineState = [device newComputePipelineStateWithFunction:function error:&error];
            
            if (!pipelineState) {
                std::cerr << "Failed to create pipeline state: " << [[error localizedDescription] UTF8String] << std::endl;
                return false;
            }
            
            return true;
        }
    }
};

MetalBacktestBridge::MetalBacktestBridge() : pimpl(std::make_unique<Impl>()) {}
MetalBacktestBridge::~MetalBacktestBridge() = default;

bool MetalBacktestBridge::init() {
    return pimpl->init();
}

std::vector<BacktestResult> MetalBacktestBridge::run_backtest(
    const std::vector<Candle>& data,
    const std::vector<float>& params,
    int n_scenarios
) {
    std::vector<BacktestResult> results(n_scenarios);
    
    @autoreleasepool {
        id<MTLBuffer> dataBuffer = [pimpl->device newBufferWithBytes:data.data() 
                                                            length:data.size() * sizeof(Candle) 
                                                           options:MTLResourceStorageModeShared];
        
        id<MTLBuffer> resultsBuffer = [pimpl->device newBufferWithLength:n_scenarios * sizeof(BacktestResult) 
                                                               options:MTLResourceStorageModeShared];
        
        id<MTLBuffer> paramsBuffer = [pimpl->device newBufferWithBytes:params.data() 
                                                              length:params.size() * sizeof(float) 
                                                             options:MTLResourceStorageModeShared];
        
        uint32_t total_candles_val = (uint32_t)data.size();
        id<MTLBuffer> countBuffer = [pimpl->device newBufferWithBytes:&total_candles_val 
                                                              length:sizeof(uint32_t) 
                                                             options:MTLResourceStorageModeShared];

        id<MTLCommandBuffer> commandBuffer = [pimpl->commandQueue commandBuffer];
        id<MTLComputeCommandEncoder> encoder = [commandBuffer computeCommandEncoder];

        [encoder setComputePipelineState:pimpl->pipelineState];
        [encoder setBuffer:dataBuffer offset:0 atIndex:0];
        [encoder setBuffer:resultsBuffer offset:0 atIndex:1];
        [encoder setBuffer:paramsBuffer offset:0 atIndex:2];
        [encoder setBuffer:countBuffer offset:0 atIndex:3];

        NSUInteger w = pimpl->pipelineState.threadExecutionWidth;
        NSUInteger h = pimpl->pipelineState.maxTotalThreadsPerThreadgroup / w;
        MTLSize threadsPerThreadgroup = MTLSizeMake(w, 1, 1);
        MTLSize threadsPerGrid = MTLSizeMake(n_scenarios, 1, 1);

        [encoder dispatchThreads:threadsPerGrid threadsPerThreadgroup:threadsPerThreadgroup];
        [encoder endEncoding];
        
        [commandBuffer commit];
        [commandBuffer waitUntilCompleted];

        std::memcpy(results.data(), [resultsBuffer contents], n_scenarios * sizeof(BacktestResult));
    }
    
    return results;
}

} // namespace monte_neo
