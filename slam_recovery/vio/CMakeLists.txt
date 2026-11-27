cmake_minimum_required(VERSION 3.16)
project(orb_vio_worker LANGUAGES CXX)

find_package(Eigen3 REQUIRED)
find_package(OpenCV 4 REQUIRED COMPONENTS core)
find_package(Pangolin REQUIRED)
add_executable(orb_worker orb_worker.cc)
target_compile_features(orb_worker PRIVATE cxx_std_14)
target_include_directories(orb_worker PRIVATE
    "${ORB_SOURCE}" "${ORB_SOURCE}/include" "${ORB_SOURCE}/include/CameraModels"
    "${ORB_SOURCE}/Thirdparty/Sophus")
set(ORB_LIBRARY "${ORB_SOURCE}/lib/libORB_SLAM3.so" CACHE FILEPATH "Native ORB-SLAM3 library")
target_link_libraries(orb_worker PRIVATE
    "${ORB_LIBRARY}" Eigen3::Eigen opencv_core ${Pangolin_LIBRARIES})
