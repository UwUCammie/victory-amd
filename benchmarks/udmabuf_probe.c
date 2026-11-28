/* Check Linux memfd-backed dma-buf aliasing without opening a GPU. */
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

static void checked(int ok, const char *operation)
{
    if (!ok) {
        perror(operation);
        exit(EXIT_FAILURE);
    }
}

static void sync_buffer(int fd, uint64_t flags)
{
    struct dma_buf_sync sync = {.flags = flags};
    int result;
    do {
        result = ioctl(fd, DMA_BUF_IOCTL_SYNC, &sync);
    } while (result == -1 && (errno == EAGAIN || errno == EINTR));
    checked(result == 0, "DMA_BUF_IOCTL_SYNC");
}

int main(void)
{
    long page_size = sysconf(_SC_PAGESIZE);
    checked(page_size > 0, "sysconf");
    size_t page = (size_t)page_size;
    int control = open("/dev/udmabuf", O_RDWR | O_CLOEXEC);
    checked(control >= 0, "open /dev/udmabuf");
    int memory = memfd_create("victory-udmabuf-probe", MFD_ALLOW_SEALING | MFD_CLOEXEC);
    checked(memory >= 0, "memfd_create");
    checked(ftruncate(memory, 3 * page) == 0, "ftruncate memfd");
    checked(fcntl(memory, F_ADD_SEALS, F_SEAL_SHRINK) == 0, "seal memfd");
    volatile unsigned char *source = mmap(NULL, 3 * page, PROT_READ | PROT_WRITE, MAP_SHARED, memory, 0);
    checked(source != MAP_FAILED, "mmap memfd");

    struct udmabuf_create request = {
        .memfd = (uint32_t)memory, .flags = UDMABUF_FLAGS_CLOEXEC, .offset = page, .size = page,
    };
    int buffer = ioctl(control, UDMABUF_CREATE, &request);
    checked(buffer >= 0, "UDMABUF_CREATE");
    volatile unsigned char *alias = mmap(NULL, page, PROT_READ | PROT_WRITE, MAP_SHARED, buffer, 0);
    checked(alias != MAP_FAILED, "mmap dma-buf");

    source[0] = 47;
    source[page] = 19;
    source[2 * page - 1] = 29;
    source[2 * page] = 53;
    sync_buffer(buffer, DMA_BUF_SYNC_START | DMA_BUF_SYNC_RW);
    int reads_match = alias[0] == 19 && alias[page - 1] == 29;
    alias[0] = 31;
    alias[page - 1] = 41;
    sync_buffer(buffer, DMA_BUF_SYNC_END | DMA_BUF_SYNC_RW);
    int writes_match = source[page] == 31 && source[2 * page - 1] == 41;
    int neighbors_match = source[0] == 47 && source[2 * page] == 53;

    checked(munmap((void *)source, 3 * page) == 0, "munmap memfd");
    checked(close(memory) == 0, "close memfd");
    sync_buffer(buffer, DMA_BUF_SYNC_START | DMA_BUF_SYNC_READ);
    int lifetime_matches = alias[0] == 31 && alias[page - 1] == 41;
    sync_buffer(buffer, DMA_BUF_SYNC_END | DMA_BUF_SYNC_READ);
    checked(munmap((void *)alias, page) == 0, "munmap dma-buf");
    checked(close(buffer) == 0, "close dma-buf");
    checked(close(control) == 0, "close udmabuf");

    printf("page_bytes=%zu reads=%d writes=%d neighbors=%d lifetime=%d\n",
           page, reads_match, writes_match, neighbors_match, lifetime_matches);
    return reads_match && writes_match && neighbors_match && lifetime_matches ? EXIT_SUCCESS : EXIT_FAILURE;
}
