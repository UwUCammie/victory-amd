/* Explicit Vulkan layer for measuring compute pipeline compilation. */
#include <pthread.h>
#include <stdatomic.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vk_layer.h>

typedef struct Instance {
    struct Instance *next;
    VkInstance handle;
    void *key;
    PFN_vkGetInstanceProcAddr get;
    PFN_GetPhysicalDeviceProcAddr get_physical;
} Instance;

typedef struct Device {
    struct Device *next;
    VkDevice handle;
    PFN_vkGetDeviceProcAddr get;
    PFN_vkCreateComputePipelines compute;
    atomic_uint compute_calls;
    atomic_uint flagged;
    atomic_uint bypassed;
    bool enabled;
} Device;

static pthread_mutex_t state_lock = PTHREAD_MUTEX_INITIALIZER;
static Instance *instances;
static Device *devices;

static void *dispatch_key(const void *handle)
{
    /* Dispatchable objects belonging to an instance share its dispatch table. */
    return *(void *const *)handle;
}

static Instance *find_instance(void *key)
{
    pthread_mutex_lock(&state_lock);
    Instance *instance = instances;
    while (instance && instance->key != key)
        instance = instance->next;
    pthread_mutex_unlock(&state_lock);
    return instance;
}

static Device *find_device(VkDevice handle)
{
    pthread_mutex_lock(&state_lock);
    Device *device = devices;
    while (device && device->handle != handle)
        device = device->next;
    pthread_mutex_unlock(&state_lock);
    return device;
}

static VKAPI_ATTR VkResult VKAPI_CALL create_instance(const VkInstanceCreateInfo *info,
        const VkAllocationCallbacks *allocator, VkInstance *handle)
{
    VkLayerInstanceCreateInfo *chain = (VkLayerInstanceCreateInfo *)info->pNext;
    while (chain && (chain->sType != VK_STRUCTURE_TYPE_LOADER_INSTANCE_CREATE_INFO ||
            chain->function != VK_LAYER_LINK_INFO))
        chain = (VkLayerInstanceCreateInfo *)chain->pNext;
    if (!chain || !chain->u.pLayerInfo)
        return VK_ERROR_INITIALIZATION_FAILED;
    const VkLayerInstanceLink *link = chain->u.pLayerInfo;
    PFN_vkCreateInstance create = (PFN_vkCreateInstance)link->pfnNextGetInstanceProcAddr(NULL, "vkCreateInstance");
    if (!create)
        return VK_ERROR_INITIALIZATION_FAILED;

    Instance *instance = calloc(1, sizeof(*instance));
    if (!instance)
        return VK_ERROR_OUT_OF_HOST_MEMORY;
    instance->get = link->pfnNextGetInstanceProcAddr;
    instance->get_physical = link->pfnNextGetPhysicalDeviceProcAddr;
    chain->u.pLayerInfo = link->pNext;
    VkResult result = create(info, allocator, handle);
    if (result != VK_SUCCESS) {
        free(instance);
        return result;
    }

    instance->handle = *handle;
    instance->key = dispatch_key(*handle);
    pthread_mutex_lock(&state_lock);
    instance->next = instances;
    instances = instance;
    pthread_mutex_unlock(&state_lock);
    return VK_SUCCESS;
}

static VKAPI_ATTR void VKAPI_CALL destroy_instance(VkInstance handle, const VkAllocationCallbacks *allocator)
{
    if (!handle)
        return;
    void *key = dispatch_key(handle);
    pthread_mutex_lock(&state_lock);
    Instance **at = &instances;
    while (*at && (*at)->key != key)
        at = &(*at)->next;
    Instance *instance = *at;
    if (instance)
        *at = instance->next;
    pthread_mutex_unlock(&state_lock);
    if (!instance)
        return;
    PFN_vkDestroyInstance destroy = (PFN_vkDestroyInstance)instance->get(handle, "vkDestroyInstance");
    destroy(handle, allocator);
    free(instance);
}

static VKAPI_ATTR VkResult VKAPI_CALL create_device(VkPhysicalDevice physical, const VkDeviceCreateInfo *info,
        const VkAllocationCallbacks *allocator, VkDevice *handle)
{
    Instance *instance = find_instance(dispatch_key(physical));
    VkLayerDeviceCreateInfo *chain = (VkLayerDeviceCreateInfo *)info->pNext;
    while (chain && (chain->sType != VK_STRUCTURE_TYPE_LOADER_DEVICE_CREATE_INFO ||
            chain->function != VK_LAYER_LINK_INFO))
        chain = (VkLayerDeviceCreateInfo *)chain->pNext;
    if (!instance || !chain || !chain->u.pLayerInfo)
        return VK_ERROR_INITIALIZATION_FAILED;
    const VkLayerDeviceLink *link = chain->u.pLayerInfo;
    PFN_vkCreateDevice create = (PFN_vkCreateDevice)link->pfnNextGetInstanceProcAddr(instance->handle, "vkCreateDevice");
    if (!create)
        return VK_ERROR_INITIALIZATION_FAILED;

    Device *device = calloc(1, sizeof(*device));
    if (!device)
        return VK_ERROR_OUT_OF_HOST_MEMORY;
    device->get = link->pfnNextGetDeviceProcAddr;
    const char *setting = getenv("VICTORY_BENCH_FAST_COMPUTE");
    device->enabled = setting && strcmp(setting, "1") == 0;
    atomic_init(&device->compute_calls, 0);
    atomic_init(&device->flagged, 0);
    atomic_init(&device->bypassed, 0);
    chain->u.pLayerInfo = link->pNext;
    VkResult result = create(physical, info, allocator, handle);
    if (result != VK_SUCCESS) {
        free(device);
        return result;
    }

    device->handle = *handle;
    device->compute = (PFN_vkCreateComputePipelines)device->get(*handle, "vkCreateComputePipelines");
    pthread_mutex_lock(&state_lock);
    device->next = devices;
    devices = device;
    pthread_mutex_unlock(&state_lock);
    return VK_SUCCESS;
}

static VKAPI_ATTR void VKAPI_CALL destroy_device(VkDevice handle, const VkAllocationCallbacks *allocator)
{
    pthread_mutex_lock(&state_lock);
    Device **at = &devices;
    while (*at && (*at)->handle != handle)
        at = &(*at)->next;
    Device *device = *at;
    if (device)
        *at = device->next;
    pthread_mutex_unlock(&state_lock);
    if (!device)
        return;
    PFN_vkDestroyDevice destroy = (PFN_vkDestroyDevice)device->get(handle, "vkDestroyDevice");
    destroy(handle, allocator);
    fprintf(stderr, "compute compile layer enabled=%u calls=%u flagged=%u bypassed=%u\n",
            (unsigned)device->enabled, atomic_load(&device->compute_calls), atomic_load(&device->flagged),
            atomic_load(&device->bypassed));
    free(device);
}

/* vkd3d creates one compute pipeline at a time and prepends the flags2 node. */
static bool request_fast_compile(VkComputePipelineCreateInfo *info, VkPipelineCreateFlags2CreateInfo *flags2)
{
    const VkBaseInStructure *head = info->pNext;
    if (head && head->sType == VK_STRUCTURE_TYPE_PIPELINE_CREATE_FLAGS_2_CREATE_INFO) {
        *flags2 = *(const VkPipelineCreateFlags2CreateInfo *)head;
        flags2->flags |= VK_PIPELINE_CREATE_2_DISABLE_OPTIMIZATION_BIT;
        info->pNext = flags2;
        return true;
    }
    for (const VkBaseInStructure *entry = head; entry; entry = entry->pNext) {
        if (entry->sType == VK_STRUCTURE_TYPE_PIPELINE_CREATE_FLAGS_2_CREATE_INFO)
            return false;
    }
    info->flags |= VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT;
    return true;
}

static VKAPI_ATTR VkResult VKAPI_CALL create_compute_pipelines(VkDevice handle, VkPipelineCache cache,
        uint32_t count, const VkComputePipelineCreateInfo *infos, const VkAllocationCallbacks *allocator,
        VkPipeline *pipelines)
{
    Device *device = find_device(handle);
    if (!device || !device->compute)
        return VK_ERROR_INITIALIZATION_FAILED;
    atomic_fetch_add_explicit(&device->compute_calls, 1, memory_order_relaxed);
    if (!device->enabled)
        return device->compute(handle, cache, count, infos, allocator, pipelines);

    if (count == 1) {
        VkComputePipelineCreateInfo info = infos[0];
        VkPipelineCreateFlags2CreateInfo flags2;
        if (request_fast_compile(&info, &flags2)) {
            atomic_fetch_add_explicit(&device->flagged, 1, memory_order_relaxed);
            return device->compute(handle, cache, 1, &info, allocator, pipelines);
        }
    }
    atomic_fetch_add_explicit(&device->bypassed, 1, memory_order_relaxed);
    return device->compute(handle, cache, count, infos, allocator, pipelines);
}

static VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL get_device(VkDevice handle, const char *name)
{
    if (strcmp(name, "vkGetDeviceProcAddr") == 0)
        return (PFN_vkVoidFunction)get_device;
    if (strcmp(name, "vkDestroyDevice") == 0)
        return (PFN_vkVoidFunction)destroy_device;
    if (strcmp(name, "vkCreateComputePipelines") == 0)
        return (PFN_vkVoidFunction)create_compute_pipelines;
    Device *device = handle ? find_device(handle) : NULL;
    return device ? device->get(handle, name) : NULL;
}

static VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL get_instance(VkInstance handle, const char *name)
{
    if (strcmp(name, "vkGetInstanceProcAddr") == 0)
        return (PFN_vkVoidFunction)get_instance;
    if (strcmp(name, "vkCreateInstance") == 0)
        return (PFN_vkVoidFunction)create_instance;
    if (!handle)
        return NULL;
    if (strcmp(name, "vkDestroyInstance") == 0)
        return (PFN_vkVoidFunction)destroy_instance;
    if (strcmp(name, "vkCreateDevice") == 0)
        return (PFN_vkVoidFunction)create_device;
    PFN_vkVoidFunction proc = get_device(VK_NULL_HANDLE, name);
    if (proc)
        return proc;
    Instance *instance = find_instance(dispatch_key(handle));
    return instance ? instance->get(handle, name) : NULL;
}

static VKAPI_ATTR PFN_vkVoidFunction VKAPI_CALL get_physical(VkInstance handle, const char *name)
{
    Instance *instance = handle ? find_instance(dispatch_key(handle)) : NULL;
    return instance && instance->get_physical ? instance->get_physical(handle, name) : NULL;
}

__attribute__((visibility("default")))
VKAPI_ATTR VkResult VKAPI_CALL vkNegotiateLoaderLayerInterfaceVersion(VkNegotiateLayerInterface *interface)
{
    if (!interface || interface->sType != LAYER_NEGOTIATE_INTERFACE_STRUCT ||
            interface->loaderLayerInterfaceVersion < 2)
        return VK_ERROR_INITIALIZATION_FAILED;
    interface->loaderLayerInterfaceVersion = 2;
    interface->pfnGetInstanceProcAddr = get_instance;
    interface->pfnGetDeviceProcAddr = get_device;
    interface->pfnGetPhysicalDeviceProcAddr = get_physical;
    return VK_SUCCESS;
}
