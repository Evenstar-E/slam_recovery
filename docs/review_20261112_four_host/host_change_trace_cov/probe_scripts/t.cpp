#include <ros/package.h>
#include <cstdio>
#include <cstdlib>
int main() {
  const char* rpp = getenv("ROS_PACKAGE_PATH");
  const char* rh = getenv("ROS_HOME");
  printf("RPP=%s\nROS_HOME=%s\n", rpp?rpp:"<null>", rh?rh:"<null>");
  std::vector<std::string> v;
  ros::package::getPlugins("image_transport", "plugin", v);
  printf("n_plugins=%zu\n", v.size());
  for (size_t i = 0; i < v.size(); ++i) printf("  %s\n", v[i].c_str());
  return 0;
}
