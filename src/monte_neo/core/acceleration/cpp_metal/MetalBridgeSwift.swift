import Metal
import Foundation

// Mirror of the C++ structs
public struct Candle {
    let open: Float
    let high: Float
    let low: Float
    let close: Float
    let volume: Float
}

public struct BacktestResult {
    let total_return: Float
    let trade_count: Int32
    let win_rate: Float
    let max_drawdown: Float
}

@_cdecl("swift_init_metal")
public func swift_init_metal() -> UnsafeMutableRawPointer? {
    guard let device = MTLCreateSystemDefaultDevice() else { return nil }
    return Unmanaged.passRetained(device).toOpaque()
}

@_cdecl("swift_run_backtest")
public func swift_run_backtest(
    devicePtr: UnsafeRawPointer,
    dataPtr: UnsafeRawPointer,
    dataCount: Int,
    paramsPtr: UnsafeRawPointer,
    paramsCount: Int,
    nScenarios: Int,
    resultsPtr: UnsafeMutableRawPointer
) -> Bool {
    let device = Unmanaged<MTLDevice>.fromOpaque(devicePtr).takeUnretainedValue()
    guard let commandQueue = device.makeCommandQueue() else { return false }
    
    // Load shader
    let shaderPath = "src/monte_neo/core/acceleration/cpp_metal/shaders/backtest_kernels.metal"
    let libraryPath = "src/monte_neo/core/acceleration/cpp_metal/shaders/backtest_kernels.metallib"
    
    var library: MTLLibrary?
    
    // Try loading pre-compiled library first
    if FileManager.default.fileExists(atPath: libraryPath) {
        let libraryURL = URL(fileURLWithPath: libraryPath)
        library = try? device.makeLibrary(URL: libraryURL)
    }
    
    // Fallback to source compilation
    if library == nil {
        guard let shaderSource = try? String(contentsOfFile: shaderPath, encoding: .utf8) else { return false }
        library = try? device.makeLibrary(source: shaderSource, options: nil)
    }
    
    guard let lib = library else { return false }
    guard let function = lib.makeFunction(name: "backtest_kernel") else { return false }
    guard let pipelineState = try? device.makeComputePipelineState(function: function) else { return false }
    
    let dataBuffer = device.makeBuffer(bytes: dataPtr, length: dataCount * MemoryLayout<Candle>.size, options: .storageModeShared)
    let resultsBuffer = device.makeBuffer(length: nScenarios * MemoryLayout<BacktestResult>.size, options: .storageModeShared)
    let paramsBuffer = device.makeBuffer(bytes: paramsPtr, length: paramsCount * MemoryLayout<Float>.size, options: .storageModeShared)
    
    var totalCandles = UInt32(dataCount)
    let countBuffer = device.makeBuffer(bytes: &totalCandles, length: MemoryLayout<UInt32>.size, options: .storageModeShared)
    
    guard let commandBuffer = commandQueue.makeCommandBuffer(),
          let encoder = commandBuffer.makeComputeCommandEncoder() else { return false }
    
    encoder.setComputePipelineState(pipelineState)
    encoder.setBuffer(dataBuffer, offset: 0, index: 0)
    encoder.setBuffer(resultsBuffer, offset: 0, index: 1)
    encoder.setBuffer(paramsBuffer, offset: 0, index: 2)
    encoder.setBuffer(countBuffer, offset: 0, index: 3)
    
    let gridSize = MTLSize(width: nScenarios, height: 1, depth: 1)
    var threadGroupSizeVal = pipelineState.maxTotalThreadsPerThreadgroup
    if threadGroupSizeVal > nScenarios {
        threadGroupSizeVal = nScenarios
    }
    let threadGroupSize = MTLSize(width: threadGroupSizeVal, height: 1, depth: 1)
    
    encoder.dispatchThreads(gridSize, threadsPerThreadgroup: threadGroupSize)
    encoder.endEncoding()
    
    commandBuffer.commit()
    commandBuffer.waitUntilCompleted()
    
    if let results = resultsBuffer?.contents() {
        let typedResults = results.assumingMemoryBound(to: BacktestResult.self)
        let typedOutput = resultsPtr.assumingMemoryBound(to: BacktestResult.self)
        typedOutput.update(from: typedResults, count: nScenarios)
    }
    
    return true
}
