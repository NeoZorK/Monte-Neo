#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include "include/metal_bridge.hpp"
#include <iostream>
#include <vector>
#include <chrono>

// Swift function declarations
extern "C" {
    void* swift_init_metal();
    bool swift_run_backtest(
        void* devicePtr,
        const void* dataPtr,
        int dataCount,
        const float* paramsPtr,
        int paramsCount,
        int nScenarios,
        void* resultsPtr
    );
}

namespace monte_neo {

class MetalBacktestBridge::Impl {
public:
    id<MTLDevice> device;
    id<MTLCommandQueue> commandQueue;
    id<MTLComputePipelineState> pipelineState;
    Driver driver;
    
    // Buffer cache for C++ driver optimization
    id<MTLBuffer> cachedDataBuffer;
    id<MTLBuffer> cachedParamsBuffer;
    id<MTLBuffer> cachedResultsBuffer;
    int cachedScenarios = 0;
    int cachedDataCount = 0;

    Impl(Driver d) : device(nil), commandQueue(nil), pipelineState(nil), driver(d), 
                    cachedDataBuffer(nil), cachedParamsBuffer(nil), cachedResultsBuffer(nil) {}
    
    bool init() {
        if (driver == Driver::SWIFT) {
            void* dev = swift_init_metal();
            if (dev) {
                device = (__bridge id<MTLDevice>)dev;
                return true;
            }
            return false;
        }

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

MetalBacktestBridge::MetalBacktestBridge(Driver driver) 
    : pimpl(std::make_unique<Impl>(driver)), driver_(driver) {}
MetalBacktestBridge::~MetalBacktestBridge() = default;

bool MetalBacktestBridge::init() {
    auto start = std::chrono::high_resolution_clock::now();
    bool success = pimpl->init();
    auto end = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> diff = end - start;
    
    std::string driver_name = (driver_ == Driver::CPP) ? "Clang C++" : 
                             (driver_ == Driver::OBJC) ? "Objective-C++" : "Apple Swift";
                             
    std::cout << "MetalBridge: " << driver_name << " initialized in " << diff.count() << "s" << std::endl;
    return success;
}

std::vector<BacktestResult> MetalBacktestBridge::run_backtest(
    const std::vector<Candle>& data,
    const std::vector<float>& params,
    int n_scenarios
) {
    auto start_total = std::chrono::high_resolution_clock::now();
    std::vector<BacktestResult> results(n_scenarios);
    
    double transfer_time = 0;
    double kernel_time = 0;

    if (driver_ == Driver::SWIFT) {
        bool success = swift_run_backtest(
            (__bridge void*)pimpl->device,
            data.data(),
            (int)data.size(),
            params.data(),
            (int)params.size(),
            n_scenarios,
            results.data()
        );
        
        if (!success) {
            std::cerr << "Swift driver execution failed" << std::endl;
        }
    } else {
        @autoreleasepool {
            auto start_transfer = std::chrono::high_resolution_clock::now();
            
            id<MTLBuffer> dataBuffer;
            id<MTLBuffer> resultsBuffer;
            id<MTLBuffer> paramsBuffer;
            
            // Optimization for C++ driver: Reuse buffers if size matches
            if (driver_ == Driver::CPP && pimpl->cachedScenarios == n_scenarios && pimpl->cachedDataCount == (int)data.size()) {
                dataBuffer = pimpl->cachedDataBuffer;
                resultsBuffer = pimpl->cachedResultsBuffer;
                paramsBuffer = pimpl->cachedParamsBuffer;
                
                std::memcpy([dataBuffer contents], data.data(), data.size() * sizeof(Candle));
                std::memcpy([paramsBuffer contents], params.data(), params.size() * sizeof(float));
            } else {
                dataBuffer = [pimpl->device newBufferWithBytes:data.data() 
                                                       length:data.size() * sizeof(Candle) 
                                                      options:MTLResourceStorageModeShared];
                
                resultsBuffer = [pimpl->device newBufferWithLength:n_scenarios * sizeof(BacktestResult) 
                                                       options:MTLResourceStorageModeShared];
                
                paramsBuffer = [pimpl->device newBufferWithBytes:params.data() 
                                                      length:params.size() * sizeof(float) 
                                                     options:MTLResourceStorageModeShared];
                
                if (driver_ == Driver::CPP) {
                    pimpl->cachedDataBuffer = dataBuffer;
                    pimpl->cachedResultsBuffer = resultsBuffer;
                    pimpl->cachedParamsBuffer = paramsBuffer;
                    pimpl->cachedScenarios = n_scenarios;
                    pimpl->cachedDataCount = (int)data.size();
                }
            }
            
            uint32_t total_candles_val = (uint32_t)data.size();
            id<MTLBuffer> countBuffer = [pimpl->device newBufferWithBytes:&total_candles_val 
                                                                  length:sizeof(uint32_t) 
                                                                 options:MTLResourceStorageModeShared];

            auto end_transfer = std::chrono::high_resolution_clock::now();
            transfer_time = std::chrono::duration<double>(end_transfer - start_transfer).count();

            auto start_kernel = std::chrono::high_resolution_clock::now();
            
            id<MTLCommandBuffer> commandBuffer = [pimpl->commandQueue commandBuffer];
            id<MTLComputeCommandEncoder> encoder = [commandBuffer computeCommandEncoder];
            
            [encoder setComputePipelineState:pimpl->pipelineState];
            [encoder setBuffer:dataBuffer offset:0 atIndex:0];
            [encoder setBuffer:resultsBuffer offset:0 atIndex:1];
            [encoder setBuffer:paramsBuffer offset:0 atIndex:2];
            [encoder setBuffer:countBuffer offset:0 atIndex:3];

            MTLSize gridSize = MTLSizeMake(n_scenarios, 1, 1);
            NSUInteger threadGroupSizeVal = pimpl->pipelineState.maxTotalThreadsPerThreadgroup;
            if (threadGroupSizeVal > (NSUInteger)n_scenarios) {
                threadGroupSizeVal = (NSUInteger)n_scenarios;
            }
            MTLSize threadGroupSize = MTLSizeMake(threadGroupSizeVal, 1, 1);

            [encoder dispatchThreads:gridSize threadsPerThreadgroup:threadGroupSize];
            [encoder endEncoding];

            [commandBuffer commit];
            [commandBuffer waitUntilCompleted];
            
            auto end_kernel = std::chrono::high_resolution_clock::now();
            kernel_time = std::chrono::duration<double>(end_kernel - start_kernel).count();

            std::memcpy(results.data(), [resultsBuffer contents], n_scenarios * sizeof(BacktestResult));
        }
    }
    
    auto end_total = std::chrono::high_resolution_clock::now();
    std::chrono::duration<double> diff_total = end_total - start_total;
    
    std::string driver_name = (driver_ == Driver::CPP) ? "Clang C++" : 
                             (driver_ == Driver::OBJC) ? "Objective-C++" : "Apple Swift";
                             
    std::cout << "MetalBridge [" << driver_name << "]:" << std::endl;
    if (driver_ != Driver::SWIFT) {
        std::cout << "  Transfer: " << transfer_time << "s" << std::endl;
        std::cout << "  Kernel:   " << kernel_time << "s" << std::endl;
    }
    std::cout << "  Total:    " << diff_total.count() << "s (" 
              << n_scenarios / (diff_total.count() + 1e-9) << " scenarios/sec)" << std::endl;
              
    return results;
}

} // namespace monte_neo
