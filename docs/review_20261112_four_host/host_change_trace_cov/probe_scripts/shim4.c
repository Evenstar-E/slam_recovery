#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <string.h>
#include <unistd.h>
#include <time.h>
extern char **environ;
static FILE* L;
static void note(const char* what, const char* name, const char* val) {
  if (!L) L = fopen("/tmp/rp_probe/env2.log", "a");
  if (!L) return;
  struct timespec ts; clock_gettime(CLOCK_MONOTONIC, &ts);
  fprintf(L, "%.3f pid=%d envp=%p %s %s=%s PATH=%s\n", ts.tv_sec + ts.tv_nsec/1e9,
          (int)getpid(), (void*)environ, what, name, val ? val : "<null>",
          getenv("PATH") ? "set" : "<null>");
  fflush(L);
}
char* getenv(const char* n) {
  static char* (*real)(const char*);
  if (!real) real = dlsym(RTLD_NEXT, "getenv");
  char* v = real(n);
  if (n && strcmp(n, "ROS_PACKAGE_PATH") == 0) note("GETENV", n, v);
  return v;
}
