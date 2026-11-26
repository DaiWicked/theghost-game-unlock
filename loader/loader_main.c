/*
 * loader_main.c —— libmain.so 转发型 loader
 *
 * 用途：官方版 APK（dex 里没有 System.loadLibrary("Tool")）也想用 kill shot 外挂时，
 *      把 libmain.so 换成这个 loader：
 *        1) 先把 JNI_OnLoad 原样转发给 libmain_orig.so（原版 Unity libmain）
 *        2) 再手动加载加固壳 libToolShell.so（已 patch，跳过服务器认证）
 *        3) 壳解密出的 payload 会 dlopen 进本进程，随后在此处 patch 内层卡密判定
 *
 * 编译（NDK r27c）：
 *   aarch64-linux-android21-clang -shared -fPIC -O2 -o libmain.so loader_main.c -ldl -llog
 */
#include <jni.h>
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <stdint.h>
#include <link.h>
#include <sys/mman.h>
#include <android/log.h>

#define TAG "MainLoader"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, TAG, __VA_ARGS__)

/* payload 内层卡密判定: base+0x51d49c  b.ne -> b */
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

/* 取本模块所在目录，拼上 name */
static int sibling_path(const char *name, char *out, size_t cap) {
    Dl_info info;
    if (!dladdr((void *)JNI_OnLoad, &info) || !info.dli_fname) return 0;
    strncpy(out, info.dli_fname, cap - 1);
    out[cap - 1] = 0;
    char *slash = strrchr(out, '/');
    if (!slash) return 0;
    strncpy(slash + 1, name, cap - (size_t)(slash + 1 - out) - 1);
    out[cap - 1] = 0;
    return 1;
}

JNIEXPORT jint JNI_OnLoad(JavaVM *vm, void *reserved) {
    char path[512];
    jint rc = JNI_VERSION_1_6;

    /* 1) 转发原 libmain 的 JNI_OnLoad（Unity 必需） */
    if (sibling_path("libmain_orig.so", path, sizeof(path))) {
        LOGI("forwarding to %s", path);
        void *h0 = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
        if (h0) {
            jint (*real_onload)(JavaVM *, void *) =
                (jint (*)(JavaVM *, void *))dlsym(h0, "JNI_OnLoad");
            if (real_onload) {
                rc = real_onload(vm, reserved);
                LOGI("libmain_orig JNI_OnLoad -> 0x%x", rc);
            }
        } else {
            LOGI("dlopen libmain_orig failed: %s", dlerror());
        }
    }

    /* 2) 加载加固壳（patch 版：跳过 sabi.cc 认证，解密 payload 并加载） */
    if (sibling_path("libToolShell.so", path, sizeof(path))) {
        LOGI("loading shell: %s", path);
        void *h1 = dlopen(path, RTLD_NOW | RTLD_GLOBAL);
        if (h1) {
            jint (*shell_onload)(JavaVM *, void *) =
                (jint (*)(JavaVM *, void *))dlsym(h1, "JNI_OnLoad");
            if (shell_onload) LOGI("shell JNI_OnLoad -> 0x%x", shell_onload(vm, NULL));
        } else {
            LOGI("dlopen shell failed: %s", dlerror());
        }
    }

    /* 3) 打掉内层卡密判定 */
    patch_inner_auth();
    return rc;
}
