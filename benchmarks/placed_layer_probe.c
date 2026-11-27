/* Exercise the optional placed-memory layer with generated Vulkan device requests. */
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <vulkan/vulkan.h>

static void require(bool condition, const char *message)
{
    if (!condition) {
        fprintf(stderr, "%s\n", message);
        exit(EXIT_FAILURE);
    }
}

static VkPhysicalDevice find_radeon(VkInstance instance)
{
    uint32_t count = 0;
    require(vkEnumeratePhysicalDevices(instance, &count, NULL) == VK_SUCCESS && count > 0,
            "no physical Vulkan device");
    VkPhysicalDevice *devices = calloc(count, sizeof *devices);
    require(devices != NULL, "allocate device list");
    require(vkEnumeratePhysicalDevices(instance, &count, devices) == VK_SUCCESS,
            "enumerate physical devices");
    VkPhysicalDevice device = VK_NULL_HANDLE;
    for (uint32_t i = 0; i < count; ++i) {
        VkPhysicalDeviceProperties properties;
        vkGetPhysicalDeviceProperties(devices[i], &properties);
        if (properties.vendorID == 0x1002 && strstr(properties.deviceName, "RX 7900 XT")) {
            printf("physical device %s\n", properties.deviceName);
            device = devices[i];
            break;
        }
    }
    free(devices);
    require(device != VK_NULL_HANDLE, "RX 7900 XT was not enumerated");
    return device;
}

static uint32_t graphics_family(VkPhysicalDevice device)
{
    uint32_t count = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(device, &count, NULL);
    VkQueueFamilyProperties *properties = calloc(count, sizeof *properties);
    require(properties != NULL, "allocate queue list");
    vkGetPhysicalDeviceQueueFamilyProperties(device, &count, properties);
    uint32_t i = 0;
    while (i < count && !(properties[i].queueFlags & VK_QUEUE_GRAPHICS_BIT)) ++i;
    free(properties);
    require(i < count, "graphics queue unavailable");
    return i;
}

int main(void)
{
    const VkApplicationInfo app = {
        .sType = VK_STRUCTURE_TYPE_APPLICATION_INFO,
        .pApplicationName = "placed memory layer probe",
        .apiVersion = VK_API_VERSION_1_4,
    };
    const VkInstanceCreateInfo create_instance = {
        .sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO,
        .pApplicationInfo = &app,
    };
    VkInstance instance;
    require(vkCreateInstance(&create_instance, NULL, &instance) == VK_SUCCESS, "create Vulkan instance");
    VkPhysicalDevice physical = find_radeon(instance);
    VkPhysicalDeviceMapMemoryPlacedFeaturesEXT supported = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MAP_MEMORY_PLACED_FEATURES_EXT,
    };
    VkPhysicalDeviceFeatures2 features = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_FEATURES_2,
        .pNext = &supported,
    };
    vkGetPhysicalDeviceFeatures2(physical, &features);
    require(supported.memoryMapPlaced && supported.memoryUnmapReserve,
            "physical device lacks required placed-memory feature bits");
    printf("physical features map=%u unmap_reserve=%u\n", supported.memoryMapPlaced, supported.memoryUnmapReserve);

    const float priority = 1.0f;
    const VkDeviceQueueCreateInfo queue = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = graphics_family(physical),
        .queueCount = 1,
        .pQueuePriorities = &priority,
    };
    VkDeviceCreateInfo request = {
        .sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO,
        .queueCreateInfoCount = 1,
        .pQueueCreateInfos = &queue,
    };
    VkDevice device;
    require(vkCreateDevice(physical, &request, NULL, &device) == VK_SUCCESS, "create device with layer defaults");
    require(vkGetDeviceProcAddr(device, "vkMapMemory2KHR") != NULL, "map_memory2 did not reach the device");
    vkDestroyDevice(device, NULL);

    VkPhysicalDeviceMapMemoryPlacedFeaturesEXT requested = {
        .sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_MAP_MEMORY_PLACED_FEATURES_EXT,
    };
    const char *const extensions[] = { VK_KHR_MAP_MEMORY_2_EXTENSION_NAME, VK_EXT_MAP_MEMORY_PLACED_EXTENSION_NAME };
    request.pNext = &requested;
    request.enabledExtensionCount = 2;
    request.ppEnabledExtensionNames = extensions;
    require(vkCreateDevice(physical, &request, NULL, &device) == VK_SUCCESS, "create device with explicit disabled fields");
    require(!requested.memoryMapPlaced && !requested.memoryUnmapReserve, "layer changed the caller's structure");
    vkDestroyDevice(device, NULL);
    vkDestroyInstance(instance, NULL);
    puts("caller-supplied disabled features preserved");
    return EXIT_SUCCESS;
}
