#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <string.h>
#include <unistd.h>
extern char **environ;
static FILE* L;
static void logline(const char* fmt, const char* a, const char* b) {
  if (!L) L = fopen("/tmp/rp_probe/env.log", "a");
  if (L) { fprintf(L, "pid=%d ", (int)getpid()); fprintf(L, fmt, a, b); fflush(L); }
}
char* getenv(const char* n) {
  static char* (*real)(const char*);
  if (!real) real = dlsym(RTLD_NEXT, "getenv");
  char* v = real(n);
  if (n && (strcmp(n,"ROS_PACKAGE_PATH")==0 || strcmp(n,"ROS_HOME")==0 || strcmp(n,"HOME")==0))
    logline("GETENV %s=%s\n", n, v?v:"<null>");
  return v;
}
int setenv(const char* n, const char* v, int o) {
  static int (*real)(const char*, const char*, int);
  if (!real) real = dlsym(RTLD_NEXT, "setenv");
  if (n && strcmp(n,"ROS_PACKAGE_PATH")==0) logline("SETENV %s=%s\n", n, v?v:"<null>");
  return real(n, v, o);
}
int unsetenv(const char* n) {
  static int (*real)(const char*);
  if (!real) real = dlsym(RTLD_NEXT, "unsetenv");
  if (n && strcmp(n,"ROS_PACKAGE_PATH")==0) logline("UNSETENV %s=%s\n", n, "");
  return real(n);
}
