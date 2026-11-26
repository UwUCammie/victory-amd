// Build in a Windows developer prompt: cl /EHsc empty_pipeline_library.cpp d3d12.lib
#include <windows.h>
#include <d3d12.h>
#include <wrl/client.h>

#include <cstdio>
#include <vector>

using Microsoft::WRL::ComPtr;

int main() {
    ComPtr<ID3D12Device1> device;
    HRESULT status = D3D12CreateDevice(nullptr, D3D_FEATURE_LEVEL_11_0, IID_PPV_ARGS(&device));
    if (FAILED(status)) {
        std::printf("D3D12CreateDevice = %08lx\n", status);
        return 1;
    }

    unsigned char unused = 0;
    ComPtr<ID3D12PipelineLibrary> previous;
    HRESULT nonnull = device->CreatePipelineLibrary(&unused, 0, IID_PPV_ARGS(&previous));
    ComPtr<ID3D12PipelineLibrary> empty;
    HRESULT null = device->CreatePipelineLibrary(nullptr, 0, IID_PPV_ARGS(&empty));
    std::printf("Non-null, zero bytes = %08lx\nNull, zero bytes = %08lx\n", nonnull, null);
    if (FAILED(null)) return 1;

    std::vector<unsigned char> blob(empty->GetSerializedSize());
    status = empty->Serialize(blob.data(), blob.size());
    std::printf("Serialize %zu bytes = %08lx\n", blob.size(), status);
    if (FAILED(status)) return 1;

    // The backing bytes must outlive the library that borrows them.
    ComPtr<ID3D12PipelineLibrary> reopened;
    status = device->CreatePipelineLibrary(blob.data(), blob.size(), IID_PPV_ARGS(&reopened));
    std::printf("Reopen = %08lx\n", status);
    return FAILED(status) ? 1 : 0;
}
