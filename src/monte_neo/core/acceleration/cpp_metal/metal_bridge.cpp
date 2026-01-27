#include "include/metal_bridge.hpp"
#include <iostream>

// We will use Metal-cpp which is a header-only C++ interface for Metal
// No Objective-C allowed per user rules.
#define NS_PRIVATE_IMPLEMENTATION
#define CA_PRIVATE_IMPLEMENTATION
#define MTL_PRIVATE_IMPLEMENTATION
#include <Metal/Metal.hpp>
#include <Foundation/Foundation.hpp>
#include <QuartzCore/QuartzCore.hpp>

namespace monte_neo {

class MetalBacktestBridge::Impl {
public:
    MTL::Device* device;
    MTL::CommandQueue* commandQueue;
    MTL::ComputePipelineState* pipelineState;

    Impl() : device(nullptr), commandQueue(nullptr), pipelineState(nullptr) {}
    
    ~Impl() {
        if (pipelineState) pipelineState->release();
        if (commandQueue) commandQueue->release();
        if (device) device->release();
    }

    bool init() {
        device = MTL::CreateSystemDefaultDevice();
        if (!device) return false;

        commandQueue = device->newCommandQueue();
        
        // Load shader from file
        NS::Error* error = nullptr;
        auto path = NS::String::string("src/monte_neo/core/acceleration/cpp_metal/shaders/backtest_kernels.metal", NS::UTF8StringEncoding);
        auto source = NS::String::stringWithContentsOfFile(path, NS::UTF8StringEncoding, &error);
        
        if (!source) {
            std::cerr << "Failed to load shaders" << std::endl;
            return false;
        }

        auto library = device->newLibrary(source, nullptr, &error);
        if (!library) {
            std::cerr << "Failed to create library" << std::endl;
            return false;
        }

        auto functionName = NS::String::string("backtest_kernel", NS::UTF8StringEncoding);
        auto function = library->newFunction(functionName);
        pipelineState = device->newComputePipelineState(function, &error);
        
        function->release();
        library->release();
        
        return pipelineState != nullptr;
    }
};

MetalBacktestBridge::MetalBacktestBridge() : pimpl(std::make_unique<Impl>()) {}
MetalBacktestBridge::~MetalBacktestBridge() = default;

bool MetalBacktestBridge::init() {
    return pimpl->init();
}

std::vector<BacktestResult> MetalBacktestBridge::run_backtest(
    const std::vector<float>& close_prices,
    const std::vector<float>& params,
    int n_scenarios
) {
    std::vector<BacktestResult> results(n_scenarios);
    
    NS::AutoreleasePool* pool = NS::AutoreleasePool::alloc()->init();

    auto dataBuffer = pimpl->device->newBuffer(close_prices.data(), close_prices.size() * sizeof(float), MTL::ResourceStorageModeShared);
    auto resultsBuffer = pimpl->device->newBuffer(n_scenarios * sizeof(BacktestResult), MTL::ResourceStorageModeShared);
    auto paramsBuffer = pimpl->device->newBuffer(params.data(), params.size() * sizeof(float), MTL::ResourceStorageModeShared);

    auto commandBuffer = pimpl->commandQueue->commandBuffer();
    auto encoder = commandBuffer->computeCommandEncoder();

    encoder->setComputePipelineState(pimpl->pipelineState);
    encoder->setBuffer(dataBuffer, 0, 0);
    encoder->setBuffer(resultsBuffer, 0, 1);
    encoder->setBuffer(paramsBuffer, 0, 2);
    
    uint32_t total_candles = (uint32_t)close_prices.size();
    encoder->setBytes(&total_candles, sizeof(uint32_t), 3);

    MTL::Size gridSize = MTL::Size(n_scenarios, 1, 1);
    MTL::Size threadGroupSize = MTL::Size(std::min((int)pimpl->pipelineState->maxTotalThreadsPerThreadgroup(), n_scenarios), 1, 1);
    
    encoder->dispatchThreads(gridSize, threadGroupSize);
    encoder->endEncoding();
    
    commandBuffer->commit();
    commandBuffer->waitUntilCompleted();

    std::memcpy(results.data(), resultsBuffer->contents(), n_scenarios * sizeof(BacktestResult));

    dataBuffer->release();
    resultsBuffer->release();
    paramsBuffer->release();
    
    pool->release();
    
    return results;
}

} // namespace monte_neo
