# NDK 路径三选一：环境变量 / 命令行 / 默认
NDK ?= $(ANDROID_NDK_HOME)
ifeq ($(NDK),)
NDK := /path/to/android-ndk-r27c
endif

# NDK 的 host 目录名，按平台改：windows-x86_64 / linux-x86_64 / darwin-x86_64
NDK_HOST ?= windows-x86_64
TOOLBIN  := $(NDK)/toolchains/llvm/prebuilt/$(NDK_HOST)/bin

CC      := $(TOOLBIN)/aarch64-linux-android21-clang
READELF := $(TOOLBIN)/llvm-readelf

CFLAGS  := -shared -fPIC -O2 -Wall -Wextra
LDFLAGS := -ldl -llog

OUTDIR  := ../prebuilt

all: $(OUTDIR)/libmain.so $(OUTDIR)/libTool.so

$(OUTDIR)/libmain.so: loader_main.c | $(OUTDIR)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

$(OUTDIR)/libTool.so: loader.c | $(OUTDIR)
	$(CC) $(CFLAGS) -o $@ $< $(LDFLAGS)

$(OUTDIR):
	mkdir -p $(OUTDIR)

clean:
	rm -f $(OUTDIR)/libmain.so $(OUTDIR)/libTool.so

check:
	@echo "--- libmain.so ---"
	@$(READELF) -d --dyn-syms $(OUTDIR)/libmain.so | grep -E "NEEDED|JNI_OnLoad"
	@echo "--- libTool.so ---"
	@$(READELF) -d --dyn-syms $(OUTDIR)/libTool.so | grep -E "NEEDED|JNI_OnLoad"

.PHONY: all clean check
