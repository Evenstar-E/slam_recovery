#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <dlfcn.h>
static FILE* (*real_popen)(const char*, const char*);
FILE* popen(const char* cmd, const char* mode) {
  if (!real_popen) real_popen = dlsym(RTLD_NEXT, "popen");
  FILE* f = fopen("/tmp/rp_probe/popen.log", "a");
  if (f) {
    fprintf(f, "CMD=[%s] RPP=[%s] ROS_HOME=[%s] PWD=%s\n", cmd,
            getenv("ROS_PACKAGE_PATH") ? getenv("ROS_PACKAGE_PATH") : "<null>",
            getenv("ROS_HOME") ? getenv("ROS_HOME") : "<null>",
            getenv("PWD") ? getenv("PWD") : "<null>");
    fclose(f);
  }
  return real_popen(cmd, mode);
}
