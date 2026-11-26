#include <jni.h>
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <link.h>
#include <sys/mman.h>
#include <unistd.h>
#include <android/log.h>

#define TAG "ToolLoader"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

/* 内层卡密判定 patch: 0x51d49c  b.ne -> b (无条件跳成功分支 0x51da58) */
#define PATCH_OFF   0x51d49cUL
#define PATCH_INSN  0x1400016FUL

static uintptr_t g_payload_base = 0;

static int find_payload(struct dl_phdr_info *info, size_t size, void *data) {
    (void)size; (void)data;
    if (info->dlpi_name && strstr(info->dlpi_name, "memfd") && info->dlpi_addr) {
        g_payload_base = (uintptr_t)info->dlpi_addr;
        LOGI("payload module: %s base=0x%lx", info->dlpi_name, (unsigned long)g_payload_base);
        return 1;
    }
    return 0;
}

static void patch_inner_auth(void) {
    g_payload_base = 0;
    dl_iterate_phdr(find_payload, NULL);
    if (!g_payload_base) { LOGI("payload not found, skip patch"); return; }
    uint8_t *p = (uint8_t *)(g_payload_base + PATCH_OFF);
    void *page = (void *)((uintptr_t)p & ~0xFFFUL);
    if (mprotect(page, 0x2000, PROT_READ | PROT_WRITE | PROT_EXEC) != 0) {
        LOGI("mprotect failed"); return;
    }
    uint32_t before; memcpy(&before, p, 4);
    uint32_t insn = (uint32_t)PATCH_INSN;
    memcpy(p, &insn, 4);
    __builtin___clear_cache((char *)p, (char *)p + 4);
    LOGI("patched %p: 0x%08x -> 0x%08x", p, before, insn);
}

__attribute__((constructor)) static void on_load(void) {
    LOGI("loader constructed");
}

JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *reserved) {
    (void)reserved;
    Dl_info info;
    char path[512];
    if (!dladdr((void *)JNI_OnLoad, &info) || !info.dli_fname) return -1;
    strncpy(path, info.dli_fname, sizeof(path) - 1);
    path[sizeof(path) - 1] = 0;
    char *slash = strrchr(path, '/');
    if (!slash) return -1;
    strcpy(slash + 1, "libToolShell.so");
    LOGI("loading real shell: %s", path);
    void *h = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
    if (!h) { LOGI("dlopen shell failed: %s", dlerror()); return -1; }
    jint (*real_onload)(JavaVM *, void *) = (jint (*)(JavaVM *, void *))dlsym(h, "JNI_OnLoad");
    jint rc = 0x10006;
    if (real_onload) {
        rc = real_onload(vm, NULL);
        LOGI("shell JNI_OnLoad -> 0x%x", rc);
    }
    patch_inner_auth();
    return rc;
}
