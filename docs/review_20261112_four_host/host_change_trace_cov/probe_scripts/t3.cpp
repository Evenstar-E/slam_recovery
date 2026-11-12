#include <ros/ros.h>
#include <image_transport/image_transport.h>
#include <dlfcn.h>
#include <cstdio>
int main(int argc, char** argv) {
  ros::init(argc, argv, "it_probe3");
  const char* lib = getenv("PROBE_LIB");
  if (lib && lib[0]) {
    void* h = dlopen(lib, RTLD_NOW | RTLD_GLOBAL);
    printf("dlopen %s -> %p %s\n", lib, h, h ? "" : dlerror());
  }
  printf("RPP=%s\n", getenv("ROS_PACKAGE_PATH") ? getenv("ROS_PACKAGE_PATH") : "<null>");
  ros::NodeHandle nh;
  image_transport::ImageTransport it(nh);
  image_transport::Publisher p = it.advertise("/it_probe3_img", 1);
  printf("advertise ok\n");
  return 0;
}
