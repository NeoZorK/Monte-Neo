#import <Metal/Metal.h>
#import <Foundation/Foundation.h>
#include "include/metal_bridge.hpp"

namespace monte_neo {

class MetalBacktestBridge::Impl {
public:
    id<MTLDevice> device;
    id<MTLCommandQueue> commandQueue;
    id<MTLComputePipelineState> backtestPipeline;
    id<MTLComputePipelineState> metricsPipeline;
    Driver driver;
    
    // Buffer cache for C++ driver optimization
    id<MTLBuffer> cachedDataBuffer;
    id<MTLBuffer> cachedParamsBuffer;
    id<MTLBuffer> cachedResultsBuffer;
    int cachedScenarios = 0;
    int cachedDataCount = 0;

    Impl(Driver d) : device(nil), commandQueue(nil), backtestPipeline(nil), metricsPipeline(nil), driver(d), 
                    cachedDataBuffer(nil), cachedParamsBuffer(nil), cachedResultsBuffer(nil) {}
    
    bool init();
};

} // namespace monte_neo
