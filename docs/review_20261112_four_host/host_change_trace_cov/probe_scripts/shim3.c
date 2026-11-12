#define _GNU_SOURCE
#include <execinfo.h>
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
#include <unistd.h>
int clearenv(void) {
  void* bt[32]; int n = backtrace(bt, 32);
  FILE* f = fopen("/tmp/rp_probe/clearenv.log", "a");
  if (f) { fprintf(f, "pid=%d clearenv called\n", (int)getpid()); backtrace_symbols_fd(bt, n, fileno(f)); fclose(f); }
  environ = NULL;
  return 0;
}
