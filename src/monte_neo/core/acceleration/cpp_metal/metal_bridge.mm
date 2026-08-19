#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include "include/metal_bridge.hpp"
#include "metal_bridge_internal.hpp"
#include <iostream>
#include <vector>
#include <chrono>

extern "C" {
    void* swift_init_metal();
    bool swift_run_backtest(void* devicePtr, const void* dataPtr, int dataCount, const float* paramsPtr, int paramsCount, int nScenarios, void* resultsPtr);
}

namespace monte_neo {

bool MetalBacktestBridge::Impl::init() {
    if (driver == Driver::SWIFT) {
        void* dev = swift_init_metal();
        if (dev) { device = (__bridge id<MTLDevice>)dev; return true; }
        return false;
    }

    @autoreleasepool {
        device = MTLCreateSystemDefaultDevice();
        if (!device) return false;
        commandQueue = [device newCommandQueue];
        MTLCompileOptions* options = [MTLCompileOptions new];
        
        auto loadSourceWithIncludes = ^NSString*(NSString* path) {
            NSError* err = nil;
            NSString* source = [NSString stringWithContentsOfFile:path encoding:NSUTF8StringEncoding error:&err];
            if (!source) return (NSString*)nil;
            NSString* baseDir = @"src/monte_neo/core/acceleration/cpp_metal/shaders/";
            NSString* commonSource = [NSString stringWithContentsOfFile:[baseDir stringByAppendingString:@"common.metal"] encoding:NSUTF8StringEncoding error:nil];
            NSString* indicatorsSource = [NSString stringWithContentsOfFile:[baseDir stringByAppendingString:@"indicators.metal"] encoding:NSUTF8StringEncoding error:nil];
            NSMutableString* fullSource = [NSMutableString string];
            if (commonSource) [fullSource appendString:commonSource];
            if (indicatorsSource) [fullSource appendString:[indicatorsSource stringByReplacingOccurrencesOfString:@"#include \"common.metal\"" withString:@"// Removed include"]];
            NSString* filteredSource = [[source stringByReplacingOccurrencesOfString:@"#include \"common.metal\"" withString:@"// Removed include"] stringByReplacingOccurrencesOfString:@"#include \"indicators.metal\"" withString:@"// Removed include"];
            [fullSource appendString:filteredSource];
            return fullSource;
        };
        
        NSString* backtestSource = loadSourceWithIncludes(@"src/monte_neo/core/acceleration/cpp_metal/shaders/backtest_kernels.metal");
        if (!backtestSource) return false;
        id<MTLLibrary> backtestLibrary = [device newLibraryWithSource:backtestSource options:options error:nil];
        if (!backtestLibrary) return false;
        backtestPipeline = [device newComputePipelineStateWithFunction:[backtestLibrary newFunctionWithName:@"backtest_kernel"] error:nil];
        
        NSString* metricsSource = loadSourceWithIncludes(@"src/monte_neo/core/acceleration/cpp_metal/shaders/metrics_kernel.metal");
        if (metricsSource) {
            id<MTLLibrary> metricsLibrary = [device newLibraryWithSource:metricsSource options:options error:nil];
            if (metricsLibrary) metricsPipeline = [device newComputePipelineStateWithFunction:[metricsLibrary newFunctionWithName:@"calculate_metrics_kernel"] error:nil];
        }
        return true;
    }
}

MetalBacktestBridge::MetalBacktestBridge(Driver driver) : pimpl(std::make_unique<Impl>(driver)), driver_(driver) {}
MetalBacktestBridge::~MetalBacktestBridge() = default;
bool MetalBacktestBridge::init() { return pimpl->init(); }

std::vector<BacktestResult> MetalBacktestBridge::run_backtest(const std::vector<Candle>& data, const std::vector<float>& params, int n_scenarios) {
    std::vector<BacktestResult> results(n_scenarios);
    if (driver_ == Driver::SWIFT) {
        if (!swift_run_backtest((__bridge void*)pimpl->device, data.data(), (int)data.size(), params.data(), (int)params.size(), n_scenarios, results.data()))
            std::cerr << "Swift driver execution failed" << std::endl;
    } else {
        @autoreleasepool {
            id<MTLBuffer> dataBuffer, resultsBuffer, paramsBuffer;
            if (driver_ == Driver::CPP && pimpl->cachedScenarios == n_scenarios && pimpl->cachedDataCount == (int)data.size()) {
                dataBuffer = pimpl->cachedDataBuffer; resultsBuffer = pimpl->cachedResultsBuffer; paramsBuffer = pimpl->cachedParamsBuffer;
                std::memcpy([dataBuffer contents], data.data(), data.size() * sizeof(Candle));
                std::memcpy([paramsBuffer contents], params.data(), params.size() * sizeof(float));
            } else {
                dataBuffer = [pimpl->device newBufferWithBytes:data.data() length:data.size() * sizeof(Candle) options:MTLResourceStorageModeShared];
                resultsBuffer = [pimpl->device newBufferWithLength:n_scenarios * sizeof(BacktestResult) options:MTLResourceStorageModeShared];
                paramsBuffer = [pimpl->device newBufferWithBytes:params.data() length:params.size() * sizeof(float) options:MTLResourceStorageModeShared];
                if (driver_ == Driver::CPP) { pimpl->cachedDataBuffer = dataBuffer; pimpl->cachedResultsBuffer = resultsBuffer; pimpl->cachedParamsBuffer = paramsBuffer; pimpl->cachedScenarios = n_scenarios; pimpl->cachedDataCount = (int)data.size(); }
            }
            uint32_t total_candles_val = (uint32_t)data.size();
            id<MTLCommandBuffer> commandBuffer = [pimpl->commandQueue commandBuffer];
            id<MTLComputeCommandEncoder> encoder = [commandBuffer computeCommandEncoder];
            [encoder setComputePipelineState:pimpl->backtestPipeline];
            [encoder setBuffer:dataBuffer offset:0 atIndex:0]; [encoder setBuffer:resultsBuffer offset:0 atIndex:1];
            [encoder setBuffer:paramsBuffer offset:0 atIndex:2]; [encoder setBytes:&total_candles_val length:sizeof(uint32_t) atIndex:3];
            [encoder dispatchThreads:MTLSizeMake(n_scenarios, 1, 1) threadsPerThreadgroup:MTLSizeMake(std::min((NSUInteger)n_scenarios, pimpl->backtestPipeline.maxTotalThreadsPerThreadgroup), 1, 1)];
            [encoder endEncoding]; [commandBuffer commit]; [commandBuffer waitUntilCompleted];
            std::memcpy(results.data(), [resultsBuffer contents], n_scenarios * sizeof(BacktestResult));
        }
    }
    return results;
}

} // namespace monte_neo
