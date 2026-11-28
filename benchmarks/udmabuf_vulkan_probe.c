/* Verify RADV reads and writes an imported, generated memfd slice. */
#define _GNU_SOURCE
#include <errno.h>
#include <fcntl.h>
#include <linux/dma-buf.h>
#include <linux/udmabuf.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <vulkan/vulkan.h>

#define REQUIRE(test) do { if (!(test)) { fprintf(stderr, "%s failed\n", #test); exit(EXIT_FAILURE); } } while (0)
#define VK(call) do { VkResult result = (call); if (result != VK_SUCCESS) { \
    fprintf(stderr, "%s: VkResult %d\n", #call, result); exit(EXIT_FAILURE); } } while (0)

static const VkExternalMemoryHandleTypeFlagBits dma = VK_EXTERNAL_MEMORY_HANDLE_TYPE_DMA_BUF_BIT_EXT;
static const VkBufferUsageFlags usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT | VK_BUFFER_USAGE_TRANSFER_DST_BIT;

static void synchronize(int fd, uint64_t flags)
{
    struct dma_buf_sync sync = {.flags = flags};
    int result;
    do {
        result = ioctl(fd, DMA_BUF_IOCTL_SYNC, &sync);
    } while (result == -1 && (errno == EAGAIN || errno == EINTR));
    if (result == -1) {
        perror("DMA_BUF_IOCTL_SYNC");
        exit(EXIT_FAILURE);
    }
}

static uint32_t memory_type(VkPhysicalDevice physical, uint32_t candidates, VkMemoryPropertyFlags wanted)
{
    VkPhysicalDeviceMemoryProperties props;
    vkGetPhysicalDeviceMemoryProperties(physical, &props);
    for (uint32_t index = 0; index < props.memoryTypeCount; ++index) {
        if ((candidates & (UINT32_C(1) << index)) && (props.memoryTypes[index].propertyFlags & wanted) == wanted)
            return index;
    }
    fprintf(stderr, "No compatible Vulkan memory type\n");
    exit(EXIT_FAILURE);
}

static VkPhysicalDevice pick_radv(VkInstance instance)
{
    uint32_t count = 0;
    VK(vkEnumeratePhysicalDevices(instance, &count, NULL));
    REQUIRE(count > 0);
    VkPhysicalDevice *list = calloc(count, sizeof(*list));
    REQUIRE(list);
    VK(vkEnumeratePhysicalDevices(instance, &count, list));
    VkPhysicalDevice selected = VK_NULL_HANDLE;
    for (uint32_t i = 0; i < count; ++i) {
        VkPhysicalDeviceDriverProperties driver = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_DRIVER_PROPERTIES};
        VkPhysicalDeviceProperties2 props = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_PROPERTIES_2, .pNext = &driver};
        vkGetPhysicalDeviceProperties2(list[i], &props);
        if (driver.driverID == VK_DRIVER_ID_MESA_RADV && props.properties.deviceType == VK_PHYSICAL_DEVICE_TYPE_DISCRETE_GPU) {
            REQUIRE(!selected);
            selected = list[i];
            printf("device=%s driver=%s\n", props.properties.deviceName, driver.driverInfo);
        }
    }
    free(list);
    REQUIRE(selected);
    return selected;
}

static uint32_t transfer_family(VkPhysicalDevice physical)
{
    uint32_t count = 0;
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, NULL);
    REQUIRE(count);
    VkQueueFamilyProperties *list = calloc(count, sizeof(*list));
    REQUIRE(list);
    vkGetPhysicalDeviceQueueFamilyProperties(physical, &count, list);
    uint32_t family = 0;
    while (family < count && !(list[family].queueCount && (list[family].queueFlags & VK_QUEUE_TRANSFER_BIT)))
        ++family;
    free(list);
    REQUIRE(family < count);
    return family;
}

static void barrier(VkCommandBuffer cmd, VkBuffer buffer, uint32_t source_family, uint32_t destination_family,
                    VkAccessFlags source, VkAccessFlags destination, VkPipelineStageFlags before, VkPipelineStageFlags after)
{
    VkBufferMemoryBarrier info = {.sType = VK_STRUCTURE_TYPE_BUFFER_MEMORY_BARRIER, .srcAccessMask = source,
        .dstAccessMask = destination, .srcQueueFamilyIndex = source_family, .dstQueueFamilyIndex = destination_family,
        .buffer = buffer, .size = VK_WHOLE_SIZE};
    vkCmdPipelineBarrier(cmd, before, after, 0, 0, NULL, 1, &info, 0, NULL);
}

int main(void)
{
    VkApplicationInfo app = {.sType = VK_STRUCTURE_TYPE_APPLICATION_INFO, .apiVersion = VK_API_VERSION_1_2};
    VkInstanceCreateInfo instance_info = {.sType = VK_STRUCTURE_TYPE_INSTANCE_CREATE_INFO, .pApplicationInfo = &app};
    VkInstance instance;
    VK(vkCreateInstance(&instance_info, NULL, &instance));
    VkPhysicalDevice physical = pick_radv(instance);
    VkPhysicalDeviceExternalBufferInfo capability = {.sType = VK_STRUCTURE_TYPE_PHYSICAL_DEVICE_EXTERNAL_BUFFER_INFO,
        .usage = usage, .handleType = dma};
    VkExternalBufferProperties external = {.sType = VK_STRUCTURE_TYPE_EXTERNAL_BUFFER_PROPERTIES};
    vkGetPhysicalDeviceExternalBufferProperties(physical, &capability, &external);
    REQUIRE(external.externalMemoryProperties.externalMemoryFeatures & VK_EXTERNAL_MEMORY_FEATURE_IMPORTABLE_BIT);

    uint32_t family = transfer_family(physical);
    float priority = 1.0f;
    VkDeviceQueueCreateInfo queue_info = {.sType = VK_STRUCTURE_TYPE_DEVICE_QUEUE_CREATE_INFO,
        .queueFamilyIndex = family, .queueCount = 1, .pQueuePriorities = &priority};
    const char *extensions[] = {VK_KHR_EXTERNAL_MEMORY_FD_EXTENSION_NAME, VK_EXT_EXTERNAL_MEMORY_DMA_BUF_EXTENSION_NAME};
    VkDeviceCreateInfo device_info = {.sType = VK_STRUCTURE_TYPE_DEVICE_CREATE_INFO, .queueCreateInfoCount = 1,
        .pQueueCreateInfos = &queue_info, .enabledExtensionCount = 2, .ppEnabledExtensionNames = extensions};
    VkDevice device;
    VK(vkCreateDevice(physical, &device_info, NULL, &device));
    VkQueue queue;
    vkGetDeviceQueue(device, family, 0, &queue);

    long page_size = sysconf(_SC_PAGESIZE);
    REQUIRE(page_size > 0);
    size_t page = (size_t)page_size;
    size_t size = 16 * page;
    int control = open("/dev/udmabuf", O_RDWR | O_CLOEXEC);
    REQUIRE(control >= 0);
    int memory = memfd_create("victory-vulkan-dma-probe", MFD_ALLOW_SEALING | MFD_CLOEXEC);
    REQUIRE(memory >= 0);
    REQUIRE(ftruncate(memory, size + 2 * page) == 0);
    REQUIRE(fcntl(memory, F_ADD_SEALS, F_SEAL_SHRINK) == 0);
    volatile uint32_t *source = mmap(NULL, size + 2 * page, PROT_READ | PROT_WRITE, MAP_SHARED, memory, 0);
    REQUIRE(source != MAP_FAILED);
    struct udmabuf_create request = {.memfd = (uint32_t)memory, .flags = UDMABUF_FLAGS_CLOEXEC, .offset = page, .size = size};
    int buffer_fd = ioctl(control, UDMABUF_CREATE, &request);
    REQUIRE(buffer_fd >= 0);
    int import_fd = fcntl(buffer_fd, F_DUPFD_CLOEXEC, 0);
    REQUIRE(import_fd >= 0);

    VkExternalMemoryBufferCreateInfo external_info = {.sType = VK_STRUCTURE_TYPE_EXTERNAL_MEMORY_BUFFER_CREATE_INFO,
        .handleTypes = dma};
    VkBufferCreateInfo buffer_info = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .pNext = &external_info,
        .size = size, .usage = usage, .sharingMode = VK_SHARING_MODE_EXCLUSIVE};
    VkBuffer imported, readback;
    VK(vkCreateBuffer(device, &buffer_info, NULL, &imported));
    buffer_info.pNext = NULL;
    VK(vkCreateBuffer(device, &buffer_info, NULL, &readback));

    VkMemoryRequirements requirements;
    vkGetBufferMemoryRequirements(device, imported, &requirements);
    REQUIRE(requirements.size <= size);
    int dedicated = (external.externalMemoryProperties.externalMemoryFeatures & VK_EXTERNAL_MEMORY_FEATURE_DEDICATED_ONLY_BIT) != 0;
    REQUIRE(!dedicated || requirements.size == size);
    PFN_vkGetMemoryFdPropertiesKHR get_fd = (PFN_vkGetMemoryFdPropertiesKHR)vkGetDeviceProcAddr(device, "vkGetMemoryFdPropertiesKHR");
    REQUIRE(get_fd);
    VkMemoryFdPropertiesKHR fd_properties = {.sType = VK_STRUCTURE_TYPE_MEMORY_FD_PROPERTIES_KHR};
    VK(get_fd(device, dma, import_fd, &fd_properties));
    VkMemoryDedicatedAllocateInfo resource = {.sType = VK_STRUCTURE_TYPE_MEMORY_DEDICATED_ALLOCATE_INFO, .buffer = imported};
    VkImportMemoryFdInfoKHR import = {.sType = VK_STRUCTURE_TYPE_IMPORT_MEMORY_FD_INFO_KHR,
        .pNext = dedicated ? &resource : NULL, .handleType = dma, .fd = import_fd};
    VkMemoryAllocateInfo allocation = {.sType = VK_STRUCTURE_TYPE_MEMORY_ALLOCATE_INFO, .pNext = &import,
        .allocationSize = size, .memoryTypeIndex = memory_type(physical, requirements.memoryTypeBits & fd_properties.memoryTypeBits, 0)};
    VkDeviceMemory imported_memory, readback_memory;
    VK(vkAllocateMemory(device, &allocation, NULL, &imported_memory));
    VK(vkBindBufferMemory(device, imported, imported_memory, 0));
    vkGetBufferMemoryRequirements(device, readback, &requirements);
    allocation.pNext = NULL;
    allocation.allocationSize = requirements.size;
    allocation.memoryTypeIndex = memory_type(physical, requirements.memoryTypeBits,
                                             VK_MEMORY_PROPERTY_HOST_VISIBLE_BIT | VK_MEMORY_PROPERTY_HOST_COHERENT_BIT);
    VK(vkAllocateMemory(device, &allocation, NULL, &readback_memory));
    VK(vkBindBufferMemory(device, readback, readback_memory, 0));

    const size_t first = page / sizeof(uint32_t);
    const size_t words = size / sizeof(uint32_t);
    const uint32_t cpu_pattern = UINT32_C(0x45ac728e), gpu_pattern = UINT32_C(0x9345d263);
    source[first - 1] = 91;
    source[first + words] = 113;
    synchronize(buffer_fd, DMA_BUF_SYNC_START | DMA_BUF_SYNC_WRITE);
    for (size_t i = 0; i < words; ++i)
        source[first + i] = cpu_pattern;
    synchronize(buffer_fd, DMA_BUF_SYNC_END | DMA_BUF_SYNC_WRITE);

    VkCommandPoolCreateInfo pool_info = {.sType = VK_STRUCTURE_TYPE_COMMAND_POOL_CREATE_INFO, .queueFamilyIndex = family};
    VkCommandPool pool;
    VK(vkCreateCommandPool(device, &pool_info, NULL, &pool));
    VkCommandBufferAllocateInfo cmd_info = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_ALLOCATE_INFO,
        .commandPool = pool, .level = VK_COMMAND_BUFFER_LEVEL_PRIMARY, .commandBufferCount = 1};
    VkCommandBuffer cmd;
    VK(vkAllocateCommandBuffers(device, &cmd_info, &cmd));
    VkCommandBufferBeginInfo begin = {.sType = VK_STRUCTURE_TYPE_COMMAND_BUFFER_BEGIN_INFO,
        .flags = VK_COMMAND_BUFFER_USAGE_ONE_TIME_SUBMIT_BIT};
    VK(vkBeginCommandBuffer(cmd, &begin));
    barrier(cmd, imported, VK_QUEUE_FAMILY_EXTERNAL, family, 0, VK_ACCESS_TRANSFER_READ_BIT,
            VK_PIPELINE_STAGE_TOP_OF_PIPE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT);
    VkBufferCopy copy = {.size = size};
    vkCmdCopyBuffer(cmd, imported, readback, 1, &copy);
    barrier(cmd, imported, VK_QUEUE_FAMILY_IGNORED, VK_QUEUE_FAMILY_IGNORED, VK_ACCESS_TRANSFER_READ_BIT,
            VK_ACCESS_TRANSFER_WRITE_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT);
    vkCmdFillBuffer(cmd, imported, 0, size, gpu_pattern);
    barrier(cmd, imported, family, VK_QUEUE_FAMILY_EXTERNAL, VK_ACCESS_TRANSFER_WRITE_BIT, 0,
            VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_BOTTOM_OF_PIPE_BIT);
    barrier(cmd, readback, VK_QUEUE_FAMILY_IGNORED, VK_QUEUE_FAMILY_IGNORED, VK_ACCESS_TRANSFER_WRITE_BIT,
            VK_ACCESS_HOST_READ_BIT, VK_PIPELINE_STAGE_TRANSFER_BIT, VK_PIPELINE_STAGE_HOST_BIT);
    VK(vkEndCommandBuffer(cmd));
    VkSubmitInfo submit = {.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO, .commandBufferCount = 1, .pCommandBuffers = &cmd};
    VK(vkQueueSubmit(queue, 1, &submit, VK_NULL_HANDLE));
    VK(vkQueueWaitIdle(queue));

    void *mapped;
    VK(vkMapMemory(device, readback_memory, 0, size, 0, &mapped));
    const uint32_t *result = mapped;
    size_t cpu_to_gpu = 0, gpu_to_cpu = 0;
    synchronize(buffer_fd, DMA_BUF_SYNC_START | DMA_BUF_SYNC_READ);
    for (size_t i = 0; i < words; ++i) {
        cpu_to_gpu += result[i] == cpu_pattern;
        gpu_to_cpu += source[first + i] == gpu_pattern;
    }
    synchronize(buffer_fd, DMA_BUF_SYNC_END | DMA_BUF_SYNC_READ);
    int neighbors = source[first - 1] == 91 && source[first + words] == 113;
    printf("bytes=%zu words=%zu cpu_to_gpu=%zu gpu_to_cpu=%zu neighbors=%d\n", size, words, cpu_to_gpu, gpu_to_cpu, neighbors);

    vkUnmapMemory(device, readback_memory);
    vkDestroyCommandPool(device, pool, NULL);
    vkDestroyBuffer(device, imported, NULL);
    vkDestroyBuffer(device, readback, NULL);
    vkFreeMemory(device, imported_memory, NULL);
    vkFreeMemory(device, readback_memory, NULL);
    vkDestroyDevice(device, NULL);
    vkDestroyInstance(instance, NULL);
    munmap((void *)source, size + 2 * page);
    close(buffer_fd);
    close(memory);
    close(control);
    return cpu_to_gpu == words && gpu_to_cpu == words && neighbors ? EXIT_SUCCESS : EXIT_FAILURE;
}
