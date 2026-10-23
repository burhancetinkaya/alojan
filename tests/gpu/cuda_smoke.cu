// U0-01: explicit hardware smoke test, not speech-model readiness or a benchmark.
#include <cuda_runtime.h>

#include <cstdio>
#include <cstdlib>

void check(cudaError_t status) {
    if (status != cudaSuccess) {
        std::fprintf(stderr, "CUDA error: %s\n", cudaGetErrorString(status));
        std::exit(1);
    }
}

__global__ void squares(int *output) {
    const int index = threadIdx.x;
    output[index] = index * index;
}

int main() {
    int *device = nullptr;
    int output[256] = {};
    check(cudaSetDevice(0));
    check(cudaMalloc(&device, sizeof(output)));
    squares<<<1, 256>>>(device);
    check(cudaGetLastError());
    check(cudaDeviceSynchronize());
    check(cudaMemcpy(output, device, sizeof(output), cudaMemcpyDeviceToHost));
    check(cudaFree(device));
    for (int index = 0; index < 256; ++index) {
        if (output[index] != index * index) {
            std::fprintf(stderr, "CUDA result mismatch at index %d\n", index);
            return 1;
        }
    }
    std::puts("CUDA kernel and device-to-host copy: 256/256 results passed");
}
