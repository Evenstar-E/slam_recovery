#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <string.h>
#include <unistd.h>
extern char **environ;
static FILE* L;
char* getenv(const char* n) {
  static char* (*real)(const char*);
  if (!real) real = dlsym(RTLD_NEXT, "getenv");
  char* v = real(n);
  if (!L) L = fopen("/tmp/rp_probe/allenv.log", "a");
  if (L && n) {
    if (!v) fprintf(L, "NULL %s env0=%p\n", n, (void*)environ[0]);
    else if (strncmp(n, "ROS", 3) == 0) fprintf(L, "ok %s=%s\n", n, v);
    fflush(L);
  }
  return v;
}
