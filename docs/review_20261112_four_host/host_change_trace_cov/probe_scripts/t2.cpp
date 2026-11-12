#include <ros/ros.h>
#include <image_transport/image_transport.h>
#include <cstdio>
int main(int argc, char** argv) {
  ros::init(argc, argv, "it_probe");
  ros::NodeHandle nh;
  image_transport::ImageTransport it(nh);
  printf("ImageTransport ok\n");
  image_transport::Publisher p = it.advertise("/it_probe_img", 1);
  printf("advertise ok\n");
  return 0;
}
