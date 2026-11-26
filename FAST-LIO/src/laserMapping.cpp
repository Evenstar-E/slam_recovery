#include <omp.h>
#include <mutex>
#include <math.h>
#include <thread>
#include <fstream>
#include <iomanip>
#include <memory>
#include <csignal>
#include <unistd.h>
#include <Python.h>
#include <so3_math.h>
#include <ros/ros.h>
#include <Eigen/Core>
#include "IMU_Processing.hpp"
#include <nav_msgs/Odometry.h>
#include <nav_msgs/Path.h>
#include <visualization_msgs/Marker.h>
#include <pcl_conversions/pcl_conversions.h>
#include <pcl/point_cloud.h>
#include <pcl/point_types.h>
#include <pcl/filters/voxel_grid.h>
#include <pcl/io/pcd_io.h>
#include <sensor_msgs/PointCloud2.h>
#include <tf/transform_datatypes.h>
#include <tf/transform_broadcaster.h>
#include <geometry_msgs/Vector3.h>
#include <livox_ros_driver/CustomMsg.h>
#include "preprocess.h"
#include <ikd-Tree/ikd_Tree.h>
#include <common_lib.h>
#include <std_msgs/Bool.h>


#define INIT_TIME (0.1)
#define LASER_POINT_COV (0.001)
#define MAXN (720000)
#define PUBFRAME_PERIOD (20)


double kdtree_incremental_time = 0.0, kdtree_search_time = 0.0, kdtree_delete_time = 0.0;
double T1[MAXN], s_plot[MAXN], s_plot2[MAXN], s_plot3[MAXN], s_plot4[MAXN], s_plot5[MAXN], s_plot6[MAXN], s_plot7[MAXN], s_plot8[MAXN], s_plot9[MAXN], s_plot10[MAXN], s_plot11[MAXN];
double match_time = 0, solve_time = 0, solve_const_H_time = 0;
int kdtree_size_st = 0, kdtree_size_end = 0, add_point_size = 0, kdtree_delete_counter = 0;
bool runtime_pos_log = false, pcd_save_en = false, time_sync_en = false;
/**************************/


//NOTE:



float res_last[100000] = {0.0}; 
float DET_RANGE = 300.0f;         
const float MOV_THRESHOLD = 1.5f; 

mutex mtx_buffer;              
condition_variable sig_buffer; 

string root_dir = ROOT_DIR;                
string map_file_path, lid_topic, imu_topic; 
double res_mean_last = 0.05, total_residual = 0.0;
double last_timestamp_lidar = 0, last_timestamp_imu = -1.0;
double gyr_cov = 0.1, acc_cov = 0.1, b_gyr_cov = 0.0001, b_acc_cov = 0.0001;
double filter_size_corner_min = 0, filter_size_surf_min = 0, filter_size_map_min = 0, fov_deg = 0;
double cube_len = 0, HALF_FOV_COS = 0, FOV_DEG = 0, total_distance = 0, lidar_end_time = 0, first_lidar_time = 0.0;
int effct_feat_num = 0, time_log_counter = 0, scan_count = 0, publish_count = 0;
int iterCount = 0, feats_down_size = 0, NUM_MAX_ITERATIONS = 0, laserCloudValidNum = 0;
bool point_selected_surf[100000] = {0}; 
bool lidar_pushed, flg_reset, flg_exit = false, flg_EKF_inited;
bool scan_pub_en = false, dense_pub_en = false, scan_body_pub_en = false;

vector<vector<int>> pointSearchInd_surf;     
vector<BoxPointType> cub_needrm;              
vector<PointVector> Nearest_Points;         
vector<double> extrinT(3, 0.0);              
vector<double> extrinR(9, 0.0);             
deque<double> time_buffer;                    
deque<PointCloudXYZI::Ptr> lidar_buffer;      
deque<sensor_msgs::Imu::ConstPtr> imu_buffer;

PointCloudXYZI::Ptr featsFromMap(new PointCloudXYZI());          
PointCloudXYZI::Ptr feats_undistort(new PointCloudXYZI()); 
PointCloudXYZI::Ptr feats_down_body(new PointCloudXYZI());       
PointCloudXYZI::Ptr feats_down_world(new PointCloudXYZI());     
PointCloudXYZI::Ptr normvec(new PointCloudXYZI(100000, 1));       
PointCloudXYZI::Ptr laserCloudOri(new PointCloudXYZI(100000, 1)); 
PointCloudXYZI::Ptr corr_normvect(new PointCloudXYZI(100000, 1)); 
PointCloudXYZI::Ptr _featsArray;                                

pcl::VoxelGrid<PointType> downSizeFilterSurf; 
pcl::VoxelGrid<PointType> downSizeFilterMap;  

KD_TREE ikdtree; 

V3F XAxisPoint_body(LIDAR_SP_LEN, 0.0, 0.0);
V3F XAxisPoint_world(LIDAR_SP_LEN, 0.0, 0.0);
V3D euler_cur;                               
V3D position_last(Zero3d);                    
V3D Lidar_T_wrt_IMU(Zero3d);                  
M3D Lidar_R_wrt_IMU(Eye3d);                   

/*** EKF inputs and output ***/
MeasureGroup Measures;   
esekfom::esekf<state_ikfom, 12, input_ikfom> kf; 
state_ikfom state_point;                        
esekfom::esekf<state_ikfom, 12, input_ikfom> Degradationpre_point; 
extern const int kfQueLength = 10;
esekfom::esekf<state_ikfom, 12, input_ikfom> kfqueue[kfQueLength];
int kfindex;

vect3 pos_lid;                                   

nav_msgs::Path path;                      
nav_msgs::Odometry odomAftMapped;         
geometry_msgs::Quaternion geoQuat;        
geometry_msgs::PoseStamped msg_body_pose; 

shared_ptr<Preprocess> p_pre(new Preprocess()); 
shared_ptr<ImuProcess> p_imu(new ImuProcess()); 

// ===================== native recovery control channel (F1, FAST-LIO) =====================
// Single-host recovery interface: hold / snapshot / restore / reprocess over a file command
// channel, plus the input-fate record and the repaired-scan receipt. Capabilities are declared in
// capabilities.json; anything not declared there is NOT supported. `re_slam()` is a reset, this is
// a checkpoint/restore of the estimator state and the ikd-Tree point set.
#include <sys/stat.h>
#include <atomic>
#include <deque>
#include <map>
#include <sstream>
#include <iomanip>

BoxPointType LocalMap_Points;
bool Localmap_Initialized = false;

struct NrCheckpoint
{
    bool valid = false;
    state_ikfom x;
    Eigen::Matrix<double, 23, 23> P = Eigen::Matrix<double, 23, 23>::Zero();
    PointVector map_pts;
    double stamp = -1.0;
    long frame = -1;
    ImuProcess::RecoveryState imu;
    BoxPointType local_map;
    bool local_map_initialized = false;
    double first_lidar_stamp = 0.0;
    int queue_index = 0;
    esekfom::esekf<state_ikfom, 12, input_ikfom> queue[kfQueLength], degradation_pre;
    int degradation_count = 0, degradation_history = 0;
    bool dynamic_imu = false, is_publish = false, pub_sleep = false, pub_build = false;
};
struct NrGroup
{
    PointCloudXYZI::Ptr lidar;
    std::deque<sensor_msgs::Imu::ConstPtr> imu;
    double beg = 0.0, end = 0.0;
    bool repaired = false;
    bool imu_only = false;
};
static std::mutex g_nr_mtx;
static std::deque<std::pair<std::string, std::string>> g_nr_pending;   // cmd, payload
static std::deque<NrGroup> g_nr_replay_groups;
static std::deque<NrGroup> g_nr_groups;                                // consumed since snapshot
static std::atomic<bool> g_nr_hold{false};
static std::atomic<bool> g_nr_replay{false};
static NrCheckpoint g_nr_cp, g_nr_previous_cp;
static bool g_nr_online_refusal = false;
static bool g_nr_history_truncated = false;
static std::deque<NrGroup> g_nr_after_refusal;
static long long g_nr_refusal_target = 0;
static int g_nr_refusal_consumed = 0, g_nr_refusal_expected = 0;
static bool g_nr_compare_refusal = true;
static bool g_nr_native_arm_running = false;
static bool g_nr_refusal_comparison = false;
static std::deque<NrGroup> g_nr_intervention_groups;
static std::ofstream g_nr_comparison_trace;
static bool g_nr_imu_probe_enabled = false;
struct NrImuProbe
{
    esekfom::esekf<state_ikfom, 12, input_ikfom> filter;
    ImuProcess imu;
    PointCloudXYZI::Ptr deskewed{new PointCloudXYZI()};
    long long checkpoint_ns = 0;
    double end = 0.0;
};
static std::unique_ptr<NrImuProbe> g_nr_imu_probe;
static std::ofstream g_nr_imu_trace;
static long long nr_ns(double stamp) { return std::llround(stamp * 1e9); }
static long g_nr_frame = 0;
static double g_nr_lidar_end = -1.0;
static std::atomic<int> g_nr_repair_received{0}, g_nr_repair_applied{0};
static std::map<long long, PointCloudXYZI::Ptr> g_nr_repaired;          // keyed by header stamp (ns)
static int g_nr_within = 0, g_nr_suffix = 0, g_nr_repaired_fed = 0;
static std::string g_nr_dir;
static std::ofstream g_nr_fates;
static std::atomic<bool> g_nr_running{false};
struct NrDeferred
{
    std::string cmd, payload;
    long long stamp_ns = 0;
};
static std::deque<NrDeferred> g_nr_deferred;   // hold/snapshot armed with an apply stamp
static int g_nr_degradation_count = 0, g_nr_degradation_history = 0;
static bool g_nr_dynamic_imu = false, g_nr_is_publish = false;
bool hasPubsleep = false;
bool hasPubbuild = false;
static int g_nr_repaired_map_updates = 0;
static std::ofstream g_nr_updates;
static bool g_nr_cur_is_replay = false;
static bool g_nr_cur_repaired = false;
static int g_nr_replay_remaining = 0;
static int g_nr_repaired_in_update = 0;                // repaired clouds actually consumed by an update
static long long g_nr_last_repaired_update_ns = 0;
static bool g_nr_cp_invalidated_by_reslam = false;
static int g_nr_deferred_resets = 0;   // native re_slam suppressed because the driver holds the map
static bool g_nr_host_reset = false;   // re_slam ran; true until odometry is published again

static void nr_write_ack(const std::string& text)
{
    if (g_nr_dir.empty()) return;
    // The same boundary group can apply hold and snapshot back-to-back.
    if (text.rfind("OK hold applied ", 0) == 0 || text.rfind("OK hold valid=0 ", 0) == 0)
    {
        const std::string path = g_nr_dir + "/ack.hold";
        {
            std::ofstream hold(path + ".tmp", std::ios::trunc);
            hold << text << "\n";
        }
        std::rename((path + ".tmp").c_str(), path.c_str());
    }
    std::ofstream out(g_nr_dir + "/ack", std::ios::trunc);
    out << text << "\n";
}
// MM-LINS only: the pose-graph node (alaserPGO) is a second process with its own write state.
// It watches this marker so that a front-end hold also freezes keyframe insertion. The marker
// lives in the same directory as cmd/ack, so one writer (this node) owns its lifecycle.
static void nr_write_pgo_hold(bool held)
{
    if (g_nr_dir.empty()) return;
    const std::string path = g_nr_dir + "/pgo_hold";
    if (!held) { ::unlink(path.c_str()); return; }
    std::ofstream out(path, std::ios::trunc);
    out << "held frame=" << g_nr_frame;
    if (g_nr_lidar_end > 0.0)
        out << " stamp_ns=" << (long long)std::llround(g_nr_lidar_end * 1e9);
    out << "\n";
}
static void nr_write_caps()
{
    if (g_nr_dir.empty()) return;
    std::ofstream out(g_nr_dir + "/capabilities.json", std::ios::trunc);
    out << "{\n"
           "  \"snapshot\": \"YES\",\n"
           "  \"restore\": \"YES\",\n"
           "  \"hold\": \"YES\",\n"
           "  \"reprocess\": \"PARTIAL\",\n"
           "  \"reprocess_refusal\": \"" << (g_nr_online_refusal ? "YES" : "NO") << "\",\n"
           "  \"refusal_observation_topic\": \"/native_recovery/observation_odom\",\n"
           "  \"imu_recovery_observation\": \"" << (g_nr_imu_probe_enabled ? "YES" : "NO") << "\",\n"
           "  \"set_state\": \"NO\",\n"
           "  \"measurement_relay\": \"YES\",\n"
           "  \"checkpoint_contents\": [\"eskf_state\", \"eskf_cov\", \"ikdtree_points\", \"time_cursor\"],\n"
           "  \"checkpoint_excludes\": [\"imu_preintegration_cache\", \"deskew_cache\", \"external_poses_graph\"],\n"
           "  \"partial_notes\": {\"reprocess\": \"replays buffered lidar/imu groups through the "
           "normal loop; repaired clouds are substituted by header stamp within 1 ms of the group "
           "end; p_imu internal preintegration/deskew state is not checkpointed\"},\n"
           "  \"notes\": \"time cursors are part of the checkpoint; imu/deskew caches are not\",\n"
           "  \"checkpoint_invalidated_by\": \"re_slam (host-native reset); a new snapshot is required afterwards\",\n"
           "  \"snapshot_refused_after_host_reset\": \"until the host publishes odometry again\",\n"
           "  \"native_reset_under_hold\": \"deferred\",\n"
           "  \"hold_scope\": \"map_writes+native_reset\",\n"
           "  \"publish_while_held\": \"YES\",\n"
           "  \"semantics\": {\"apply_stamp\": \"YES\", \"ack_levels\": [\"deferred\", \"applied\"],\n"
           "                 \"checkpoint_validity\": \"until_re_slam\",\n"
           "                 \"native_reset_under_hold\": \"deferred\",\n"
           "                 \"publish_gating\": \"isPublish+held\",\n"
           "                 \"profile\": \"native_recovery\"}\n"
           "}\n";
}
static std::string nr_hex16(unsigned long long v)
{
    std::ostringstream s; s << std::hex << std::setw(16) << std::setfill('0') << v; return s.str();
}
static void nr_poll_thread()
{
    const std::string cmd_path = g_nr_dir + "/cmd";
    const std::string ack_recv = g_nr_dir + "/ack_received";
    while (g_nr_running.load())
    {
        struct stat st;
        if (!g_nr_dir.empty() && ::stat(cmd_path.c_str(), &st) == 0)
        {
            std::ifstream in(cmd_path);
            std::string cmd, payload;
            std::getline(in, cmd);
            std::getline(in, payload);
            in.close();
            if (!cmd.empty())
            {
                std::rename(cmd_path.c_str(), (g_nr_dir + "/cmd.done").c_str());
                { std::lock_guard<std::mutex> lk(g_nr_mtx); g_nr_pending.emplace_back(cmd, payload); }
                std::ofstream rec(ack_recv, std::ios::trunc);
                const ros::WallTime received = ros::WallTime::now();
                rec << "RECEIVED " << cmd << " wall=" << received.sec << '.'
                    << std::setw(9) << std::setfill('0') << received.nsec << "\n";
            }
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(5));
    }
}
// One row per consumed group: the trailing field is the group's fate.
static void nr_log_fate(double end_time, double beg_time, const char* fate)
{
    if (!g_nr_fates.is_open() || g_nr_native_arm_running) return;
    g_nr_fates << "{\"frame\":" << g_nr_frame << ",\"stamp_ns\":" << (long long)std::llround(end_time * 1e9)
               << ",\"beg_s\":" << std::fixed << std::setprecision(6) << beg_time
               << ",\"end_s\":" << end_time << ",\"fate\":\"" << fate << "\"}\n";
}
// Caller must hold g_nr_mtx.
static bool nr_take_repair(double beg, double end, PointCloudXYZI::Ptr& out)
{
    if (g_nr_repaired.empty()) return false;
    auto best = g_nr_repaired.end();
    long long best_dt = 0;
    for (auto it = g_nr_repaired.begin(); it != g_nr_repaired.end(); ++it)
    {
        const double t = (double)it->first * 1e-9;
        if (t < beg - 1e-3 || t > end + 1e-3) continue;
        const long long dt = std::llabs(it->first - (long long)std::llround(end * 1e9));
        if (best == g_nr_repaired.end() || dt < best_dt) { best = it; best_dt = dt; }
    }
    if (best == g_nr_repaired.end()) return false;
    out = best->second;
    g_nr_repaired.erase(best);
    g_nr_repair_applied.fetch_add(1);
    return true;
}
static void nr_capture_group()
{
    if (g_nr_cur_is_replay || !g_nr_cp.valid) return;
    std::lock_guard<std::mutex> lk(g_nr_mtx);
    NrGroup g;
    g.lidar = Measures.lidar;
    g.imu = Measures.imu;
    g.beg = Measures.lidar_beg_time;
    g.end = lidar_end_time;
    g_nr_groups.push_back(g);
    if (g_nr_groups.size() > 4000)
    {
        g_nr_groups.pop_front();
        g_nr_history_truncated = true;
    }
}
static bool nr_restore_locked(std::string& why)
{
    if (!g_nr_cp.valid)
    {
        why = g_nr_cp_invalidated_by_reslam ? "checkpoint_invalidated_by_re_slam" : "no_checkpoint";
        return false;
    }
    kf.change_x(g_nr_cp.x);
    Eigen::Matrix<double, 23, 23> P = g_nr_cp.P;
    kf.change_P(P);
    ikdtree.clear();
    if (!g_nr_cp.map_pts.empty()) ikdtree.Build(g_nr_cp.map_pts);
    flg_EKF_inited = true;
    p_imu->restore_recovery_state(g_nr_cp.imu);
    LocalMap_Points = g_nr_cp.local_map;
    Localmap_Initialized = g_nr_cp.local_map_initialized;
    first_lidar_time = g_nr_cp.first_lidar_stamp;
    kfindex = g_nr_cp.queue_index;
    for (int i = 0; i < kfQueLength; ++i) kfqueue[i] = g_nr_cp.queue[i];
    Degradationpre_point = g_nr_cp.degradation_pre;
    g_nr_degradation_count = g_nr_cp.degradation_count;
    g_nr_degradation_history = g_nr_cp.degradation_history;
    g_nr_dynamic_imu = g_nr_cp.dynamic_imu;
    g_nr_is_publish = g_nr_cp.is_publish;
    hasPubsleep = g_nr_cp.pub_sleep;
    hasPubbuild = g_nr_cp.pub_build;
    g_nr_lidar_end = g_nr_cp.stamp;
    g_nr_frame = g_nr_cp.frame;
    return true;
}
static bool nr_advance_imu_probe(NrImuProbe& probe, const MeasureGroup& group, double end)
{
    if (end <= probe.end || group.imu.empty() || !group.lidar || group.lidar->empty())
        return false;
    probe.imu.Process(group, probe.filter, probe.deskewed, probe.filter);
    probe.end = end;
    return probe.deskewed->size() == group.lidar->size();
}

static bool nr_start_imu_probe(long long boundary)
{
    if (!g_nr_imu_trace.is_open() || g_nr_history_truncated || boundary <= 0) return false;
    const bool use_latest = g_nr_cp.valid && nr_ns(g_nr_cp.stamp) <= boundary;
    const auto& checkpoint = use_latest ? g_nr_cp : g_nr_previous_cp;
    if (!checkpoint.valid || nr_ns(checkpoint.stamp) > boundary ||
        checkpoint.imu.need_init || !checkpoint.imu.last_imu) return false;
    auto trial = std::unique_ptr<NrImuProbe>(new NrImuProbe());
    trial->filter = kf;
    auto state = checkpoint.x;
    trial->filter.change_x(state);
    Eigen::Matrix<double, 23, 23> cov = checkpoint.P;
    trial->filter.change_P(cov);
    trial->imu.restore_recovery_state(checkpoint.imu);
    trial->imu.cov_bias_acc = p_imu->cov_bias_acc;
    trial->imu.cov_bias_gyr = p_imu->cov_bias_gyr;
    trial->checkpoint_ns = nr_ns(checkpoint.stamp);
    trial->end = checkpoint.stamp;
    for (const auto& group : g_nr_groups)
    {
        if (group.end <= checkpoint.stamp) continue;
        MeasureGroup measurement;
        measurement.lidar = group.lidar;
        measurement.imu = group.imu;
        measurement.lidar_beg_time = group.beg;
        if (!nr_advance_imu_probe(*trial, measurement, group.end)) return false;
    }
    if (trial->end != g_nr_lidar_end) return false;
    g_nr_imu_probe = std::move(trial);
    return true;
}

static void nr_write_imu_observation(const state_ikfom& fused)
{
    if (!g_nr_imu_probe || !g_nr_hold.load() || g_nr_cur_is_replay) return;
    const auto predicted = g_nr_imu_probe->filter.get_x();
    const auto cov = g_nr_imu_probe->filter.get_P();
    const double sigma_pos = std::sqrt(cov.template block<3, 3>(0, 0).trace());
    if (!std::isfinite(sigma_pos) || !predicted.pos.allFinite() ||
        !predicted.rot.coeffs().allFinite() || !fused.pos.allFinite() ||
        !fused.rot.coeffs().allFinite()) return;
    // Native deskew sorts a copy of this array by point time and preserves its ordering.
    PointVector raw = Measures.lidar->points;
    std::sort(raw.begin(), raw.end(), time_list);
    const auto& deskewed = g_nr_imu_probe->deskewed->points;
    const size_t step = std::max<size_t>(1, raw.size() / 300);
    std::ostringstream out;
    out << std::setprecision(10)
        << "{\"scan_ns\":" << nr_ns(Measures.lidar_beg_time)
        << ",\"end_ns\":" << nr_ns(lidar_end_time)
        << ",\"checkpoint_ns\":" << g_nr_imu_probe->checkpoint_ns
        << ",\"position_sigma_m\":" << sigma_pos << ",\"points\":[";
    for (size_t j = 0, i = 0; i < raw.size() && j < 300; ++j, i += step)
    {
        const V3D p(raw[i].x, raw[i].y, raw[i].z);
        const V3D d(deskewed[i].x, deskewed[i].y, deskewed[i].z);
        const V3D a = fused.rot * (fused.offset_R_L_I * p + fused.offset_T_L_I) + fused.pos;
        const V3D b = predicted.rot * (predicted.offset_R_L_I * p + predicted.offset_T_L_I) + predicted.pos;
        const V3D c = predicted.rot * (predicted.offset_R_L_I * d + predicted.offset_T_L_I) + predicted.pos;
        if (!a.allFinite() || !b.allFinite() || !c.allFinite()) return;
        if (j) out << ',';
        out << '[' << a(0) << ',' << a(1) << ',' << a(2) << ','
            << b(0) << ',' << b(1) << ',' << b(2) << ','
            << c(0) << ',' << c(1) << ',' << c(2) << ']';
    }
    g_nr_imu_trace << out.str() << "]}" << std::endl;
}

static void nr_record_comparison_frame(const char* result)
{
    if (!g_nr_refusal_comparison || !g_nr_refusal_target || !g_nr_cur_is_replay ||
        !g_nr_comparison_trace.is_open()) return;
    g_nr_comparison_trace << "{\"checkpoint_ns\":" << nr_ns(g_nr_cp.stamp)
        << ",\"target_ns\":" << g_nr_refusal_target
        << ",\"branch\":\"" << (g_nr_native_arm_running ? "native" : "refusal")
        << "\",\"scan_ns\":" << nr_ns(Measures.lidar_beg_time)
        << ",\"end_ns\":" << nr_ns(lidar_end_time)
        << ",\"result\":\"" << result << "\"}\n";
}

static void nr_start_refusal_after_native_arm()
{
    if (!g_nr_native_arm_running || !g_nr_replay_groups.empty()) return;
    g_nr_native_arm_running = false;
    std::string why;
    if (!nr_restore_locked(why))
    {
        ROS_ERROR("Cannot restore refusal comparison checkpoint: %s", why.c_str());
        return;
    }
    g_nr_replay_groups.swap(g_nr_intervention_groups);
    g_nr_replay_remaining = static_cast<int>(g_nr_replay_groups.size());
    g_nr_replay.store(!g_nr_replay_groups.empty());
}

static void nr_execute(const std::string& cmd, const std::string& payload)
{
        if (cmd == "status")
        {
            if (g_nr_replay_groups.empty())
            {
                if (g_nr_fates.is_open()) g_nr_fates.flush();
                if (g_nr_comparison_trace.is_open()) g_nr_comparison_trace.flush();
            }
            std::ostringstream s;
            s << "OK status valid=" << (g_nr_cp.valid ? 1 : 0)
              << " repair_received=" << g_nr_repair_received.load()
              << " repair_applied=" << g_nr_repair_applied.load()
              << " repaired_in_update=" << g_nr_repaired_in_update
              << " last_repaired_update_ns=" << g_nr_last_repaired_update_ns
              << " repaired_map_updates=" << g_nr_repaired_map_updates
              << " replay_remaining=" << g_nr_replay_remaining
              << " refusal_target_ns=" << g_nr_refusal_target
              << " refusal_consumed=" << g_nr_refusal_consumed
              << " refusal_expected=" << g_nr_refusal_expected
              << " map_points=" << ikdtree.validnum()
              << " deferred_resets=" << g_nr_deferred_resets
              << " frame=" << g_nr_frame;
            if (g_nr_lidar_end > 0.0)
                s << " stamp_ns=" << (long long)std::llround(g_nr_lidar_end * 1e9);
            else
                s << " stamp_ns=NA no_timebase=1";
            s << " map_writes=" << (g_nr_hold.load() ? "held" : "released");
            nr_write_ack(s.str());
        }
        else if (cmd == "hold")
        {
            if (g_nr_lidar_end <= 0.0) { nr_write_ack("OK hold valid=0 reason=no_timebase"); return; }
            g_nr_hold.store(true);
            nr_write_pgo_hold(true);
            const std::string prefix = "imu_before_ns=";
            const bool imu_requested = g_nr_imu_probe_enabled && payload.rfind(prefix, 0) == 0;
            bool imu_started = false;
            if (imu_requested)
            {
                g_nr_imu_probe.reset();
                try { imu_started = nr_start_imu_probe(std::stoll(payload.substr(prefix.size()))); }
                catch (const std::invalid_argument&) {}
                catch (const std::out_of_range&) {}
            }
            std::ostringstream s;
            s << "OK hold applied valid=1 stamp_ns=" << (long long)std::llround(g_nr_lidar_end * 1e9)
              << " frame=" << g_nr_frame << " map_writes=held";
            if (imu_requested)
                s << " imu_probe=" << (imu_started ? "started" : "unavailable");
            nr_write_ack(s.str());
        }
        else if (cmd == "release" || cmd == "resume")
        {
            if (g_nr_refusal_target &&
                (!g_nr_replay_groups.empty() || g_nr_refusal_consumed != g_nr_refusal_expected ||
                 nr_ns(g_nr_lidar_end) != g_nr_refusal_target))
            {
                nr_write_ack("OK resume valid=0 reason=refusal_not_consumed");
                return;
            }
            if (g_nr_refusal_target)
            {
                g_nr_refusal_target = 0;
                g_nr_refusal_comparison = false;
                g_nr_cp.valid = g_nr_previous_cp.valid = false;
            }
            g_nr_imu_probe.reset();
            g_nr_hold.store(false);
            nr_write_pgo_hold(false);
            std::ostringstream s;
            s << "OK resume valid=1";
            if (g_nr_lidar_end > 0.0) s << " stamp_ns=" << (long long)std::llround(g_nr_lidar_end * 1e9);
            s << " frame=" << g_nr_frame << " map_writes=released";
            nr_write_ack(s.str());
        }
        else if (cmd == "snapshot")
        {
            if (g_nr_lidar_end <= 0.0) { nr_write_ack("OK snapshot valid=0 reason=no_timebase"); return; }
            if (g_nr_host_reset) { nr_write_ack("OK snapshot valid=0 reason=host_reset_no_map"); return; }
            std::lock_guard<std::mutex> lk(g_nr_mtx);
            if (g_nr_online_refusal && g_nr_hold.load())
            {
                nr_write_ack("OK snapshot valid=0 reason=recovery_held");
                return;
            }
            if (g_nr_online_refusal)
            {
                g_nr_previous_cp = std::move(g_nr_cp);
                while (!g_nr_groups.empty() && g_nr_groups.front().end <= g_nr_previous_cp.stamp)
                    g_nr_groups.pop_front();
                // The first snapshot after a reset starts a new capture.
                if (!g_nr_previous_cp.valid) g_nr_groups.clear();
            }
            else g_nr_groups.clear();
            g_nr_cp.x = kf.get_x();
            g_nr_cp.P = kf.get_P();
            g_nr_cp.map_pts.clear();
            if (ikdtree.Root_Node != nullptr)
            {
                PointVector pts;
                ikdtree.flatten(ikdtree.Root_Node, pts, NOT_RECORD);
                g_nr_cp.map_pts = pts;
            }
            g_nr_cp.stamp = g_nr_lidar_end;
            g_nr_cp.frame = g_nr_frame;
            g_nr_cp.imu = p_imu->recovery_state();
            g_nr_cp.local_map = LocalMap_Points;
            g_nr_cp.local_map_initialized = Localmap_Initialized;
            g_nr_cp.first_lidar_stamp = first_lidar_time;
            g_nr_cp.queue_index = kfindex;
            for (int i = 0; i < kfQueLength; ++i) g_nr_cp.queue[i] = kfqueue[i];
            g_nr_cp.degradation_pre = Degradationpre_point;
            g_nr_cp.degradation_count = g_nr_degradation_count;
            g_nr_cp.degradation_history = g_nr_degradation_history;
            g_nr_cp.dynamic_imu = g_nr_dynamic_imu;
            g_nr_cp.is_publish = g_nr_is_publish;
            g_nr_cp.pub_sleep = hasPubsleep;
            g_nr_cp.pub_build = hasPubbuild;
            g_nr_cp.valid = true;
            g_nr_cp_invalidated_by_reslam = false;
            if (!g_nr_previous_cp.valid) g_nr_history_truncated = false;
            std::ostringstream s;
            s << "OK snapshot applied valid=1 stamp_ns=" << (long long)std::llround(g_nr_cp.stamp * 1e9)
              << " frame=" << g_nr_cp.frame << " map_points=" << g_nr_cp.map_pts.size();
            nr_write_ack(s.str());
        }
        else if (cmd == "restore")
        {
            std::lock_guard<std::mutex> lk(g_nr_mtx);
            std::string why;
            const bool ok = nr_restore_locked(why);
            std::ostringstream s;
            if (ok)
                s << "OK restore valid=1 stamp_ns=" << (long long)std::llround(g_nr_lidar_end * 1e9)
                  << " frame=" << g_nr_frame;
            else
                s << "OK restore valid=0 reason=" << why;
            nr_write_ack(s.str());
        }
        else if (cmd == "reprocess_refusal" && g_nr_online_refusal)
        {
            std::lock_guard<std::mutex> lk(g_nr_mtx);
            std::istringstream request(payload);
            long long boundary = 0, scan = 0;
            std::vector<long long> confirmed;
            request >> boundary;
            while (request >> scan) confirmed.push_back(scan);
            if (!g_nr_hold.load() || g_nr_refusal_target || !g_nr_replay_groups.empty() ||
                boundary <= 0 || confirmed.empty() ||
                !std::is_sorted(confirmed.begin(), confirmed.end()) || boundary >= confirmed.front())
            {
                nr_write_ack("OK reprocess_refusal valid=0 reason=invalid_request");
                return;
            }

            const bool use_latest = g_nr_cp.valid && nr_ns(g_nr_cp.stamp) <= boundary;
            const NrCheckpoint& checkpoint = use_latest ? g_nr_cp : g_nr_previous_cp;
            if (!checkpoint.valid || nr_ns(checkpoint.stamp) > boundary || g_nr_history_truncated)
            {
                nr_write_ack("OK reprocess_refusal valid=0 reason=no_preboundary_checkpoint_or_history");
                return;
            }

            // ROS stamps and the host's floating point time cursor can differ by sub-microseconds.
            constexpr long long match_ns = 1024;
            std::deque<NrGroup> replay, later;
            size_t verified = 0;
            for (const auto& captured : g_nr_groups)
            {
                if (captured.end <= checkpoint.stamp) continue;
                NrGroup group = captured;
                const long long begin = nr_ns(group.beg);
                if (begin > confirmed.back() + match_ns)
                {
                    later.push_back(std::move(group));
                    continue;
                }
                if (group.imu.empty())
                {
                    nr_write_ack("OK reprocess_refusal valid=0 reason=missing_imu");
                    return;
                }
                group.imu_only = nr_ns(group.end) >= boundary && begin < confirmed.front() - match_ns;
                if (!group.imu_only && begin >= confirmed.front() - match_ns)
                {
                    if (verified >= confirmed.size() || std::llabs(begin - confirmed[verified]) > match_ns)
                    {
                        nr_write_ack("OK reprocess_refusal valid=0 reason=unverified_suffix_group");
                        return;
                    }
                    ++verified;
                }
                replay.push_back(std::move(group));
            }
            if (verified != confirmed.size() || replay.empty() ||
                nr_ns(replay.back().end) < confirmed.back())
            {
                nr_write_ack("OK reprocess_refusal valid=0 reason=confirmed_suffix_not_captured");
                return;
            }

            if (!use_latest) g_nr_cp = std::move(g_nr_previous_cp);
            std::string why;
            if (!nr_restore_locked(why))
            {
                nr_write_ack("OK reprocess_refusal valid=0 reason=" + why);
                return;
            }
            g_nr_imu_probe.reset();
            g_nr_refusal_expected = int(replay.size());
            g_nr_refusal_consumed = 0;
            g_nr_refusal_target = nr_ns(replay.back().end);
            const auto last_scan = nr_ns(replay.back().beg);
            g_nr_refusal_comparison = g_nr_compare_refusal && g_nr_comparison_trace.is_open();
            if (g_nr_refusal_comparison)
            {
                g_nr_intervention_groups.swap(replay);
                g_nr_replay_groups = g_nr_intervention_groups;
                for (auto& group : g_nr_replay_groups) group.imu_only = false;
                g_nr_native_arm_running = true;
            }
            else g_nr_replay_groups.swap(replay);
            g_nr_after_refusal.swap(later);
            g_nr_groups.clear();
            // sync_packages may have peeked the next live scan without popping it while waiting
            // for IMU. Replay reuses Measures. Restage that same unpopped scan on return.
            lidar_pushed = false;
            g_nr_replay_remaining = g_nr_refusal_expected;
            g_nr_replay.store(true);
            std::ostringstream ack;
            ack << "OK reprocess_refusal valid=1 checkpoint_stamp_ns=" << nr_ns(g_nr_cp.stamp)
                << " target_ns=" << g_nr_refusal_target << " target_scan_ns=" << last_scan
                << " queued=" << g_nr_refusal_expected << " pending_live=" << g_nr_after_refusal.size()
                << " comparison=" << (g_nr_refusal_comparison ? 1 : 0);
            nr_write_ack(ack.str());
        }
        else if (cmd == "reprocess")
        {
            std::lock_guard<std::mutex> lk(g_nr_mtx);
            std::string why;
            if (!nr_restore_locked(why))
            {
                nr_write_ack("OK reprocess valid=0 reason=" + why);
                return;
            }
            long long end_ns = 0;
            try { if (!payload.empty()) end_ns = std::stoll(payload); } catch (...) { end_ns = 0; }
            g_nr_within = 0; g_nr_suffix = 0; g_nr_repaired_fed = 0;
            for (const auto& captured : g_nr_groups)
            {
                if (captured.end <= g_nr_cp.stamp) continue;
                NrGroup group = captured;
                PointCloudXYZI::Ptr rep;
                if (nr_take_repair(group.beg, group.end, rep))
                {
                    group.lidar = rep;
                    group.repaired = true;
                    ++g_nr_repaired_fed;
                }
                const long long stamp = (long long)std::llround(group.end * 1e9);
                if (end_ns > 0 && stamp > end_ns) ++g_nr_suffix; else ++g_nr_within;
                g_nr_replay_groups.push_back(std::move(group));
            }
            g_nr_replay.store(true);
            g_nr_replay_remaining = g_nr_within + g_nr_suffix;
            // The replay writes the map even while the driver holds it: a held map would keep the
            // repaired frames out. The hold itself is NOT cleared -- it is the driver's, and the
            // driver releases it with `resume` once its recovery is finished. Clearing it here is
            // what let v7's replay hand the map back mid-recovery.
            std::ostringstream s;
            s << "OK reprocess valid=1 checkpoint_stamp_ns="
              << (long long)std::llround(g_nr_cp.stamp * 1e9)
              << " checkpoint_frame=" << g_nr_cp.frame
              << " replay_suffix=" << g_nr_suffix << " replay_within_end=" << g_nr_within
              << " repaired_fed=" << g_nr_repaired_fed << " source=buffer";
            nr_write_ack(s.str());
            g_nr_groups.clear();
        }
        else if (cmd == "capabilities")
        {
            nr_write_caps();
            nr_write_ack("OK capabilities written");
        }
        else
        {
            nr_write_ack("OK " + cmd + " UNSUPPORTED");
        }
}
// Collects commands from the control thread; holds/snapshots that carry an apply stamp are ARMED
// and executed later, at the frame boundary that reaches their stamp.
static void nr_apply_pending()
{
    std::deque<std::pair<std::string, std::string>> due;
    { std::lock_guard<std::mutex> lk(g_nr_mtx); due.swap(g_nr_pending); }
    for (auto& c : due)
    {
        const std::string& cmd = c.first;
        if ((cmd == "hold" || cmd == "snapshot") && !c.second.empty())
        {
            long long stamp_ns = 0;
            try { stamp_ns = std::stoll(c.second); } catch (...) { stamp_ns = 0; }
            if (stamp_ns > 0)
            {
                {
                    std::lock_guard<std::mutex> lk(g_nr_mtx);
                    NrDeferred d; d.cmd = cmd; d.payload = c.second; d.stamp_ns = stamp_ns;
                    g_nr_deferred.push_back(std::move(d));
                }
                std::ostringstream s2;
                s2 << "OK " << cmd << " deferred stamp=" << stamp_ns;
                nr_write_ack(s2.str());
                continue;
            }
        }
        nr_execute(cmd, c.second);
    }
}
// Applies armed hold/snapshot before the group whose end reaches their stamp is processed. The
// snapshot therefore describes the PREVIOUS completed frame (kf still holds it) and its stamp is
// that frame's end, which is strictly before the target -- a restore can never land after the
// boundary it was armed for.
static void nr_apply_deferred(double this_group_end)
{
    std::deque<NrDeferred> due;
    {
        std::lock_guard<std::mutex> lk(g_nr_mtx);
        const long long now_ns = (this_group_end > 0.0) ? (long long)std::llround(this_group_end * 1e9) : 0;
        if (now_ns <= 0) return;
        while (!g_nr_deferred.empty() && g_nr_deferred.front().stamp_ns <= now_ns)
        {
            due.push_back(std::move(g_nr_deferred.front()));
            g_nr_deferred.pop_front();
        }
    }
    for (auto& d : due) nr_execute(d.cmd, d.payload);
}
static void nr_repaired_cbk(const sensor_msgs::PointCloud2::ConstPtr& msg)
{
    PointCloudXYZI::Ptr cloud(new PointCloudXYZI());
    // The measurement topic carries raw Velodyne fields, including per-return time.
    p_pre->process(msg, cloud);
    if (cloud->size() <= 1) return;
    const long long key = (long long)std::llround(msg->header.stamp.toSec() * 1e9);
    { std::lock_guard<std::mutex> lk(g_nr_mtx); g_nr_repaired[key] = cloud; }
    g_nr_repair_received.fetch_add(1);
}
// =================== end native recovery control channel ===================

void SigHandle(int sig)
{
    flg_exit = true;
    ROS_WARN("catch sig %d", sig);
    sig_buffer.notify_all(); 
}
inline void dump_lio_state_to_log(FILE *fp)
{
    V3D rot_ang(Log(state_point.rot.toRotationMatrix()));
    fprintf(fp, "%lf ", Measures.lidar_beg_time - first_lidar_time);
    fprintf(fp, "%lf %lf %lf ", rot_ang(0), rot_ang(1), rot_ang(2));                            // Angle
    fprintf(fp, "%lf %lf %lf ", state_point.pos(0), state_point.pos(1), state_point.pos(2));    // Pos
    fprintf(fp, "%lf %lf %lf ", 0.0, 0.0, 0.0);                                                 // omega
    fprintf(fp, "%lf %lf %lf ", state_point.vel(0), state_point.vel(1), state_point.vel(2));    // Vel
    fprintf(fp, "%lf %lf %lf ", 0.0, 0.0, 0.0);                                                 // Acc
    fprintf(fp, "%lf %lf %lf ", state_point.bg(0), state_point.bg(1), state_point.bg(2));       // Bias_g
    fprintf(fp, "%lf %lf %lf ", state_point.ba(0), state_point.ba(1), state_point.ba(2));       // Bias_a
    fprintf(fp, "%lf %lf %lf ", state_point.grav[0], state_point.grav[1], state_point.grav[2]); // Bias_a
    fprintf(fp, "\r\n");
    fflush(fp);
}

void pointBodyToWorld_ikfom(PointType const *const pi, PointType *const po, state_ikfom &s)
{
    V3D p_body(pi->x, pi->y, pi->z);
    V3D p_global(s.rot * (s.offset_R_L_I * p_body + s.offset_T_L_I) + s.pos);

    po->x = p_global(0);
    po->y = p_global(1);
    po->z = p_global(2);
    po->intensity = pi->intensity;
}

void pointBodyToWorld(PointType const *const pi, PointType *const po)
{
    V3D p_body(pi->x, pi->y, pi->z);
    V3D p_global(state_point.rot * (state_point.offset_R_L_I * p_body + state_point.offset_T_L_I) + state_point.pos);

    po->x = p_global(0);
    po->y = p_global(1);
    po->z = p_global(2);
    po->intensity = pi->intensity;
}
template <typename T>
void pointBodyToWorld(const Matrix<T, 3, 1> &pi, Matrix<T, 3, 1> &po)
{
    V3D p_body(pi[0], pi[1], pi[2]);
    V3D p_global(state_point.rot * (state_point.offset_R_L_I * p_body + state_point.offset_T_L_I) + state_point.pos);

    po[0] = p_global(0);
    po[1] = p_global(1);
    po[2] = p_global(2);
}
void RGBpointBodyToWorld(PointType const *const pi, PointType *const po)
{
    V3D p_body(pi->x, pi->y, pi->z);
    V3D p_global(state_point.rot * (state_point.offset_R_L_I * p_body + state_point.offset_T_L_I) + state_point.pos);

    po->x = p_global(0);
    po->y = p_global(1);
    po->z = p_global(2);
    po->intensity = pi->intensity;
}
void RGBpointBodyLidarToIMU(PointType const *const pi, PointType *const po)
{
    V3D p_body_lidar(pi->x, pi->y, pi->z);
    V3D p_body_imu(state_point.offset_R_L_I * p_body_lidar + state_point.offset_T_L_I);

    po->x = p_body_imu(0);
    po->y = p_body_imu(1);
    po->z = p_body_imu(2);
    po->intensity = pi->intensity;
}
void points_cache_collect()
{
    PointVector points_history;
    ikdtree.acquire_removed_points(points_history); 
    // for (int i = 0; i < points_history.size(); i++)
        // _featsArray->push_back(points_history[i]); 
}
void lasermap_fov_segment()
{
    cub_needrm.clear();
    kdtree_delete_counter = 0;
    kdtree_delete_time = 0.0;
    pointBodyToWorld(XAxisPoint_body, XAxisPoint_world);
    V3D pos_LiD = pos_lid;
    if (!Localmap_Initialized)
    {
        for (int i = 0; i < 3; i++)
        {
            LocalMap_Points.vertex_min[i] = pos_LiD(i) - cube_len / 2.0;
            LocalMap_Points.vertex_max[i] = pos_LiD(i) + cube_len / 2.0;
        }
        Localmap_Initialized = true;
        return;
    }
    float dist_to_map_edge[3][2];
    bool need_move = false;
    for (int i = 0; i < 3; i++)
    {
        dist_to_map_edge[i][0] = fabs(pos_LiD(i) - LocalMap_Points.vertex_min[i]);
        dist_to_map_edge[i][1] = fabs(pos_LiD(i) - LocalMap_Points.vertex_max[i]);
        if (dist_to_map_edge[i][0] <= MOV_THRESHOLD * DET_RANGE || dist_to_map_edge[i][1] <= MOV_THRESHOLD * DET_RANGE)
            need_move = true;
    }
    if (!need_move)
        return;
    BoxPointType New_LocalMap_Points, tmp_boxpoints;
    New_LocalMap_Points = LocalMap_Points;
    float mov_dist = max((cube_len - 2.0 * MOV_THRESHOLD * DET_RANGE) * 0.5 * 0.9, double(DET_RANGE * (MOV_THRESHOLD - 1)));
    for (int i = 0; i < 3; i++)
    {
        tmp_boxpoints = LocalMap_Points;
        if (dist_to_map_edge[i][0] <= MOV_THRESHOLD * DET_RANGE)
        {
            New_LocalMap_Points.vertex_max[i] -= mov_dist;
            New_LocalMap_Points.vertex_min[i] -= mov_dist;
            tmp_boxpoints.vertex_min[i] = LocalMap_Points.vertex_max[i] - mov_dist;
            cub_needrm.push_back(tmp_boxpoints);
        }
        else if (dist_to_map_edge[i][1] <= MOV_THRESHOLD * DET_RANGE)
        {
            New_LocalMap_Points.vertex_max[i] += mov_dist;
            New_LocalMap_Points.vertex_min[i] += mov_dist;
            tmp_boxpoints.vertex_max[i] = LocalMap_Points.vertex_min[i] + mov_dist;
            cub_needrm.push_back(tmp_boxpoints);
        }
    }
    LocalMap_Points = New_LocalMap_Points;

    points_cache_collect();
    double delete_begin = omp_get_wtime();
    if (cub_needrm.size() > 0)
        kdtree_delete_counter = ikdtree.Delete_Point_Boxes(cub_needrm);
    kdtree_delete_time = omp_get_wtime() - delete_begin;
}
void standard_pcl_cbk(const sensor_msgs::PointCloud2::ConstPtr &msg)
{
    mtx_buffer.lock(); 
    scan_count++;
    double preprocess_start_time = omp_get_wtime(); 
    if (msg->header.stamp.toSec() < last_timestamp_lidar)
    {
        ROS_ERROR("lidar loop back, clear buffer");
        lidar_buffer.clear();
    }

    PointCloudXYZI::Ptr ptr(new PointCloudXYZI());
    p_pre->process(msg, ptr);                                     
    lidar_buffer.push_back(ptr);                                   
    time_buffer.push_back(msg->header.stamp.toSec());              
    last_timestamp_lidar = msg->header.stamp.toSec();               
    s_plot11[scan_count] = omp_get_wtime() - preprocess_start_time;
    mtx_buffer.unlock();
    sig_buffer.notify_all();
}

double timediff_lidar_wrt_imu = 0.0;
bool timediff_set_flg = false; 
void livox_pcl_cbk(const livox_ros_driver::CustomMsg::ConstPtr &msg)
{
    mtx_buffer.lock();
    double preprocess_start_time = omp_get_wtime();
    scan_count++;
    if (msg->header.stamp.toSec() < last_timestamp_lidar) 
    {
        ROS_ERROR("lidar loop back, clear buffer");
        lidar_buffer.clear();
    }
    last_timestamp_lidar = msg->header.stamp.toSec();
    if (!time_sync_en && abs(last_timestamp_imu - lidar_end_time) > 10.0)
    {
        printf("IMU and LiDAR not Synced, IMU time: %lf, lidar scan end time: %lf", last_timestamp_imu, lidar_end_time);
    }
    if (time_sync_en && !timediff_set_flg && abs(last_timestamp_lidar - last_timestamp_imu) > 1 && !imu_buffer.empty())
    {
        timediff_set_flg = true; 
        timediff_lidar_wrt_imu = last_timestamp_lidar + 0.1 - last_timestamp_imu;
        printf("Self sync IMU and LiDAR, time diff is %.10lf \n", timediff_lidar_wrt_imu);
    }
    PointCloudXYZI::Ptr ptr(new PointCloudXYZI());
    p_pre->process(msg, ptr);   
    lidar_buffer.push_back(ptr);
    time_buffer.push_back(last_timestamp_lidar);
    s_plot11[scan_count] = omp_get_wtime() - preprocess_start_time;
    mtx_buffer.unlock();
    sig_buffer.notify_all();
}
void imu_cbk(const sensor_msgs::Imu::ConstPtr &msg_in)
{
    publish_count++;
    // cout<<"IMU got at: "<<msg_in->header.stamp.toSec()<<endl;
    sensor_msgs::Imu::Ptr msg(new sensor_msgs::Imu(*msg_in));
    if (abs(timediff_lidar_wrt_imu) > 0.1 && time_sync_en)
    {
        msg->header.stamp =
            ros::Time().fromSec(timediff_lidar_wrt_imu + msg_in->header.stamp.toSec());
    }

    double timestamp = msg->header.stamp.toSec(); 

    mtx_buffer.lock();
    if (timestamp < last_timestamp_imu)
    {
        ROS_WARN("imu loop back, clear buffer");
        imu_buffer.clear();
    }
    last_timestamp_imu = timestamp;

    imu_buffer.push_back(msg);
    mtx_buffer.unlock();    
    sig_buffer.notify_all(); 
}
bool sync_packages(MeasureGroup &meas)
{
    if (lidar_buffer.empty() || imu_buffer.empty())
    {
        return false;
    }
    if (!lidar_pushed)
    {
        meas.lidar = lidar_buffer.front();
        if (meas.lidar->points.size() <= 1)
        {
            lidar_buffer.pop_front();
            return false;
        }
        meas.lidar_beg_time = time_buffer.front();
        lidar_end_time = meas.lidar_beg_time + meas.lidar->points.back().curvature / double(1000); 
        lidar_pushed = true;                                                                      
    }
    if (last_timestamp_imu < lidar_end_time)
    {
        return false;
    }
    double imu_time = imu_buffer.front()->header.stamp.toSec();
    meas.imu.clear();
    while ((!imu_buffer.empty()) && (imu_time < lidar_end_time)) 
    {
        imu_time = imu_buffer.front()->header.stamp.toSec(); 
        if (imu_time > lidar_end_time)
            break;
        meas.imu.push_back(imu_buffer.front()); 
        imu_buffer.pop_front();
    }

    lidar_buffer.pop_front(); 
    time_buffer.pop_front();  
    lidar_pushed = false;     
    return true;
}

int process_increments = 0;
void map_incremental()
{
    if (g_nr_hold.load() && !g_nr_cur_is_replay) return;   // native recovery: hold = stop map writes
    PointVector PointToAdd;
    PointVector PointNoNeedDownsample;
    PointToAdd.reserve(feats_down_size);
    PointNoNeedDownsample.reserve(feats_down_size);
    for (int i = 0; i < feats_down_size; i++)
    {
        /* transform to world frame */
        pointBodyToWorld(&(feats_down_body->points[i]), &(feats_down_world->points[i]));
        /* decide if need add to map */
        if (!Nearest_Points[i].empty() && flg_EKF_inited)
        {
            const PointVector &points_near = Nearest_Points[i];
            bool need_add = true;
            BoxPointType Box_of_Point;
            PointType downsample_result, mid_point;
            mid_point.x = floor(feats_down_world->points[i].x / filter_size_map_min) * filter_size_map_min + 0.5 * filter_size_map_min;
            mid_point.y = floor(feats_down_world->points[i].y / filter_size_map_min) * filter_size_map_min + 0.5 * filter_size_map_min;
            mid_point.z = floor(feats_down_world->points[i].z / filter_size_map_min) * filter_size_map_min + 0.5 * filter_size_map_min;
            float dist = calc_dist(feats_down_world->points[i], mid_point);
            if (fabs(points_near[0].x - mid_point.x) > 0.5 * filter_size_map_min && fabs(points_near[0].y - mid_point.y) > 0.5 * filter_size_map_min && fabs(points_near[0].z - mid_point.z) > 0.5 * filter_size_map_min)
            {
                PointNoNeedDownsample.push_back(feats_down_world->points[i]);
                continue;
            }
            for (int readd_i = 0; readd_i < NUM_MATCH_POINTS; readd_i++)
            {
                if (points_near.size() < NUM_MATCH_POINTS)
                    break;
                if (calc_dist(points_near[readd_i], mid_point) < dist)
                {
                    need_add = false;
                    break;
                }
            }
            if (need_add)
                PointToAdd.push_back(feats_down_world->points[i]);
        }
        else
        {
            PointToAdd.push_back(feats_down_world->points[i]);
        }
    }

    double st_time = omp_get_wtime();
    add_point_size = ikdtree.Add_Points(PointToAdd, true);
    ikdtree.Add_Points(PointNoNeedDownsample, false);
    add_point_size = PointToAdd.size() + PointNoNeedDownsample.size();
    kdtree_incremental_time = omp_get_wtime() - st_time;
}
PointCloudXYZI::Ptr pcl_wait_pub(new PointCloudXYZI(500000, 1)); 
PointCloudXYZI::Ptr pcl_wait_save(new PointCloudXYZI());         
void publish_frame_world(const ros::Publisher &pubLaserCloudFull)
{
    if (scan_pub_en) 
    {
        PointCloudXYZI::Ptr laserCloudFullRes(dense_pub_en ? feats_undistort : feats_down_body);
        int size = laserCloudFullRes->points.size();                                             
        PointCloudXYZI::Ptr laserCloudWorld(  
                        new PointCloudXYZI(size, 1));                                            

        for (int i = 0; i < size; i++)
        {
            RGBpointBodyToWorld(&laserCloudFullRes->points[i],
                                &laserCloudWorld->points[i]);
        }

        sensor_msgs::PointCloud2 laserCloudmsg;
        pcl::toROSMsg(*laserCloudWorld, laserCloudmsg);
        laserCloudmsg.header.stamp = ros::Time().fromSec(lidar_end_time);
        laserCloudmsg.header.frame_id = "camera_init";
        pubLaserCloudFull.publish(laserCloudmsg);
        publish_count -= PUBFRAME_PERIOD;
    }
    if (pcd_save_en)
    {
        int size = feats_undistort->points.size();
        PointCloudXYZI::Ptr laserCloudWorld(
            new PointCloudXYZI(size, 1));

        for (int i = 0; i < size; i++)
        {
            RGBpointBodyToWorld(&feats_undistort->points[i],
                                &laserCloudWorld->points[i]); 
        }
        *pcl_wait_save += *laserCloudWorld; 
    }
}
void publish_frame_body(const ros::Publisher &pubLaserCloudFull_body)
{
    int size = feats_undistort->points.size();
    PointCloudXYZI::Ptr laserCloudIMUBody(new PointCloudXYZI(size, 1)); 

    for (int i = 0; i < size; i++)
    {
        RGBpointBodyLidarToIMU(&feats_undistort->points[i],
                               &laserCloudIMUBody->points[i]);
    }

    sensor_msgs::PointCloud2 laserCloudmsg;
    pcl::toROSMsg(*laserCloudIMUBody, laserCloudmsg);
    laserCloudmsg.header.stamp = ros::Time().fromSec(lidar_end_time);
    laserCloudmsg.header.frame_id = "body";
    pubLaserCloudFull_body.publish(laserCloudmsg);
    publish_count -= PUBFRAME_PERIOD;
}
void publish_frame_lidar(const ros::Publisher &pubLaserCloudFull_lidar)
{
    sensor_msgs::PointCloud2 laserCloudmsg;
    pcl::toROSMsg(*feats_undistort, laserCloudmsg); 
    laserCloudmsg.header.stamp = ros::Time().fromSec(lidar_end_time);
    laserCloudmsg.header.frame_id = "lidar";
    pubLaserCloudFull_lidar.publish(laserCloudmsg);
    publish_count -= PUBFRAME_PERIOD;
}
void publish_effect_world(const ros::Publisher &pubLaserCloudEffect)
{
    PointCloudXYZI::Ptr laserCloudWorld(
        new PointCloudXYZI(effct_feat_num, 1)); 
    for (int i = 0; i < effct_feat_num; i++)
    {
        RGBpointBodyToWorld(&laserCloudOri->points[i],
                            &laserCloudWorld->points[i]);
    }
    sensor_msgs::PointCloud2 laserCloudFullRes3;
    pcl::toROSMsg(*laserCloudWorld, laserCloudFullRes3);
    laserCloudFullRes3.header.stamp = ros::Time().fromSec(lidar_end_time);
    laserCloudFullRes3.header.frame_id = "camera_init";
    pubLaserCloudEffect.publish(laserCloudFullRes3);
}
void publish_map(const ros::Publisher &pubLaserCloudMap)
{
    sensor_msgs::PointCloud2 laserCloudMap;
    pcl::toROSMsg(*featsFromMap, laserCloudMap);
    laserCloudMap.header.stamp = ros::Time().fromSec(lidar_end_time);
    laserCloudMap.header.frame_id = "camera_init";
    pubLaserCloudMap.publish(laserCloudMap);
}
template <typename T>
void set_posestamp(T &out)
{
    out.pose.position.x = state_point.pos(0);
    out.pose.position.y = state_point.pos(1);
    out.pose.position.z = state_point.pos(2);
    out.pose.orientation.x = geoQuat.x;
    out.pose.orientation.y = geoQuat.y;
    out.pose.orientation.z = geoQuat.z;
    out.pose.orientation.w = geoQuat.w;
}
void publish_odometry(const ros::Publisher &pubOdomAftMapped)
{
    // A published odometry is the first sign that the host is building again after re_slam().
    g_nr_host_reset = false;
    odomAftMapped.header.frame_id = "camera_init";
    odomAftMapped.child_frame_id = "body";
    odomAftMapped.header.stamp = ros::Time().fromSec(lidar_end_time); // ros::Time().fromSec(lidar_end_time);
    set_posestamp(odomAftMapped.pose);
    pubOdomAftMapped.publish(odomAftMapped);
    auto P = kf.get_P();
    for (int i = 0; i < 6; i++)
    {
        int k = i < 3 ? i + 3 : i - 3;
        odomAftMapped.pose.covariance[i * 6 + 0] = P(k, 3);
        odomAftMapped.pose.covariance[i * 6 + 1] = P(k, 4);
        odomAftMapped.pose.covariance[i * 6 + 2] = P(k, 5);
        odomAftMapped.pose.covariance[i * 6 + 3] = P(k, 0);
        odomAftMapped.pose.covariance[i * 6 + 4] = P(k, 1);
        odomAftMapped.pose.covariance[i * 6 + 5] = P(k, 2);
    }

    static tf::TransformBroadcaster br;
    tf::Transform transform;
    tf::Quaternion q;
    transform.setOrigin(tf::Vector3(odomAftMapped.pose.pose.position.x,
                                    odomAftMapped.pose.pose.position.y,
                                    odomAftMapped.pose.pose.position.z));
    q.setW(odomAftMapped.pose.pose.orientation.w);
    q.setX(odomAftMapped.pose.pose.orientation.x);
    q.setY(odomAftMapped.pose.pose.orientation.y);
    q.setZ(odomAftMapped.pose.pose.orientation.z);
    transform.setRotation(q);
    br.sendTransform(tf::StampedTransform(transform, odomAftMapped.header.stamp, "camera_init", "body"));
}
void publish_path(const ros::Publisher pubPath)
{
    set_posestamp(msg_body_pose);
    msg_body_pose.header.stamp = ros::Time().fromSec(lidar_end_time);
    msg_body_pose.header.frame_id = "camera_init";

    /*** if path is too large, the rvis will crash ***/
    static int jjj = 0;
    jjj++;
    if (jjj % 10 == 0)
    {
        path.poses.push_back(msg_body_pose);
        pubPath.publish(path);
    }
}
void h_share_model(state_ikfom &s, esekfom::dyn_share_datastruct<double> &ekfom_data)
{
    double match_start = omp_get_wtime();  
    laserCloudOri->clear();                 
    corr_normvect->clear();                   
    total_residual = 0.0;

#ifdef MP_EN
    omp_set_num_threads(MP_PROC_NUM);
#pragma omp parallel for
#endif
    for (int i = 0; i < feats_down_size; i++)
    {
        PointType &point_body = feats_down_body->points[i]; 
        PointType &point_world = feats_down_world->points[i]; 
        V3D p_body(point_body.x, point_body.y, point_body.z);
        V3D p_global(s.rot * (s.offset_R_L_I * p_body + s.offset_T_L_I) + s.pos);  
        point_world.x = p_global(0);
        point_world.y = p_global(1);
        point_world.z = p_global(2);
        point_world.intensity = point_body.intensity;

        vector<float> pointSearchSqDis(NUM_MATCH_POINTS);  //NUM_MATCH_POINTS = 5

        auto &points_near = Nearest_Points[i];

        if (ekfom_data.converge)
        {
            /** Find the closest surfaces in the map **/
            ikdtree.Nearest_Search(point_world, NUM_MATCH_POINTS, points_near, pointSearchSqDis);
            point_selected_surf[i] = points_near.size() < NUM_MATCH_POINTS ? false : pointSearchSqDis[NUM_MATCH_POINTS - 1] > 5 ? false
                                                                                                                                : true;
        }

        if (!point_selected_surf[i])
            continue;

        VF(4)
        pabcd; 
        point_selected_surf[i] = false; 
        if (esti_plane(pabcd, points_near, 0.1f)) 
        {
            float pd2 = pabcd(0) * point_world.x + pabcd(1) * point_world.y + pabcd(2) * point_world.z + pabcd(3);
            float s = 1 - 0.9 * fabs(pd2) / sqrt(p_body.norm());

            if (s > 0.9) 
            {
                point_selected_surf[i] = true; 
                normvec->points[i].x = pabcd(0); 
                normvec->points[i].y = pabcd(1);
                normvec->points[i].z = pabcd(2);
                normvec->points[i].intensity = pd2; 
                res_last[i] = abs(pd2); 
            }
        }
    }

    effct_feat_num = 0; 

    for (int i = 0; i < feats_down_size; i++)
    {
        if (point_selected_surf[i])
        {
            laserCloudOri->points[effct_feat_num] = feats_down_body->points[i];
            corr_normvect->points[effct_feat_num] = normvec->points[i]; 
            total_residual += res_last[i]; 
            effct_feat_num++;
        }
    }
    res_mean_last = total_residual / effct_feat_num; 
    match_time += omp_get_wtime() - match_start;
    double solve_start_ = omp_get_wtime();        
    /*** Computation of Measuremnt Jacobian matrix H and measurents vector ***/
    ekfom_data.h_x = MatrixXd::Zero(effct_feat_num, 12);
    ekfom_data.h.resize(effct_feat_num); 
    for (int i = 0; i < effct_feat_num; i++)
    {
        const PointType &laser_p = laserCloudOri->points[i];
        V3D point_this_be(laser_p.x, laser_p.y, laser_p.z);
        M3D point_be_crossmat; 
        point_be_crossmat << SKEW_SYM_MATRX(point_this_be);
        V3D point_this = s.offset_R_L_I * point_this_be + s.offset_T_L_I;
        M3D point_crossmat;
        point_crossmat << SKEW_SYM_MATRX(point_this); 

        /*** get the normal vector of closest surface/corner ***/
        const PointType &norm_p = corr_normvect->points[i];
        V3D norm_vec(norm_p.x, norm_p.y, norm_p.z);

        /*** calculate the Measuremnt Jacobian matrix H ***/
        V3D C(s.rot.conjugate() * norm_vec); 
        V3D A(point_crossmat * C);
        V3D B(point_be_crossmat * s.offset_R_L_I.conjugate() * C); 
        ekfom_data.h_x.block<1, 12>(i, 0) << norm_p.x, norm_p.y, norm_p.z, VEC_FROM_ARRAY(A), VEC_FROM_ARRAY(B), VEC_FROM_ARRAY(C);
    
        /*** Measuremnt: distance to the closest surface/corner ***/
        ekfom_data.h(i) = -norm_p.intensity; 
    }
    solve_time += omp_get_wtime() - solve_start_;
}

void re_slam()
{
    // A reset is not a restore: the map tree is cleared and the state goes back to the IMU
    // initialisation point, so any checkpoint taken before it no longer describes this host.
    // Refusing the restore here is the third layer after the driver's own sleep/build handling.
    { std::lock_guard<std::mutex> lk(g_nr_mtx);
      g_nr_cp.valid = g_nr_previous_cp.valid = false; g_nr_cp_invalidated_by_reslam = true; }
    g_nr_host_reset = true;
    // flg_reset = true;
    state_ikfom t;                    
    state_point = t;
    esekfom::esekf<state_ikfom, 12, input_ikfom> k;
    kf = k;
    double epsi[23] = {0.001};
    fill(epsi, epsi + 23, 0.001);  
    kf.init_dyn_share(get_f, df_dx, df_dw, h_share_model, NUM_MAX_ITERATIONS, epsi); 
    shared_ptr<ImuProcess> p_imu_new(new ImuProcess());
    p_imu = p_imu_new;
    p_imu->Reset();
    memset(point_selected_surf, true, sizeof(point_selected_surf));
    memset(res_last, -1000.0f, sizeof(res_last));
    p_imu->set_extrinsic(Lidar_T_wrt_IMU, Lidar_R_wrt_IMU);
    p_imu->set_gyr_cov(V3D(gyr_cov, gyr_cov, gyr_cov));
    p_imu->set_acc_cov(V3D(acc_cov, acc_cov, acc_cov));
    p_imu->set_gyr_bias_cov(V3D(b_gyr_cov, b_gyr_cov, b_gyr_cov));
    p_imu->set_acc_bias_cov(V3D(b_acc_cov, b_acc_cov, b_acc_cov));
    ikdtree.clear();
}

int main(int argc, char **argv)
{
    ros::init(argc, argv, "laserMapping");
    ros::NodeHandle nh;
    nh.param<bool>("publish/scan_publish_en", scan_pub_en, 1);  
    nh.param<bool>("publish/dense_publish_en", dense_pub_en, 1);  
    nh.param<bool>("publish/scan_bodyframe_pub_en", scan_body_pub_en, 1);  
    nh.param<int>("max_iteration", NUM_MAX_ITERATIONS, 4); 
    nh.param<string>("map_file_path", map_file_path, ""); 
    nh.param<string>("common/lid_topic", lid_topic, "/livox/lidar"); 
    nh.param<string>("common/imu_topic", imu_topic, "/livox/imu"); 
    nh.param<bool>("common/time_sync_en", time_sync_en, false); 
    nh.param<double>("filter_size_corner", filter_size_corner_min, 0.1);  
    nh.param<double>("filter_size_surf", filter_size_surf_min, 0.1);
    nh.param<double>("filter_size_map", filter_size_map_min, 0.1);
    nh.param<double>("cube_side_length", cube_len, 200); 
    nh.param<float>("mapping/det_range", DET_RANGE, 300.f); 
    nh.param<double>("mapping/fov_degree", fov_deg, 180);  
    nh.param<double>("mapping/gyr_cov", gyr_cov, 0.1);  
    nh.param<double>("mapping/acc_cov", acc_cov, 0.1); 
    nh.param<double>("mapping/b_gyr_cov", b_gyr_cov, 0.0001); 
    nh.param<double>("mapping/b_acc_cov", b_acc_cov, 0.0001);
    nh.param<double>("preprocess/blind", p_pre->blind, 0.01); 
    nh.param<int>("preprocess/lidar_type", p_pre->lidar_type, AVIA); 
    nh.param<int>("preprocess/scan_line", p_pre->N_SCANS, 16);
    nh.param<int>("point_filter_num", p_pre->point_filter_num, 2); 
    nh.param<bool>("feature_extract_enable", p_pre->feature_enabled, 1); 
    nh.param<bool>("runtime_pos_log_enable", runtime_pos_log, 1); 
    nh.param<bool>("pcd_save_enable", pcd_save_en, 0);   
    nh.param<vector<double>>("mapping/extrinsic_T", extrinT, vector<double>()); 
    nh.param<vector<double>>("mapping/extrinsic_R", extrinR, vector<double>()); 
    cout << "p_pre->lidar_type " << p_pre->lidar_type << endl;
    path.header.stamp = ros::Time::now();
    path.header.frame_id = "camera_init";
    int  frame_num = 0;
    double  aver_time_consu = 0, aver_time_icp = 0, aver_time_match = 0, aver_time_incre = 0, aver_time_solve = 0, aver_time_const_H_time = 0;

    memset(point_selected_surf, true, sizeof(point_selected_surf));
    memset(res_last, -1000.0f, sizeof(res_last));
    downSizeFilterSurf.setLeafSize(filter_size_surf_min, filter_size_surf_min, filter_size_surf_min);
    downSizeFilterMap.setLeafSize(filter_size_map_min, filter_size_map_min, filter_size_map_min);
    memset(point_selected_surf, true, sizeof(point_selected_surf));
    memset(res_last, -1000.0f, sizeof(res_last));
    Lidar_T_wrt_IMU << VEC_FROM_ARRAY(extrinT);
    Lidar_R_wrt_IMU << MAT_FROM_ARRAY(extrinR);
    p_imu->set_extrinsic(Lidar_T_wrt_IMU, Lidar_R_wrt_IMU);
    p_imu->set_gyr_cov(V3D(gyr_cov, gyr_cov, gyr_cov));
    p_imu->set_acc_cov(V3D(acc_cov, acc_cov, acc_cov));
    p_imu->set_gyr_bias_cov(V3D(b_gyr_cov, b_gyr_cov, b_gyr_cov));
    p_imu->set_acc_bias_cov(V3D(b_acc_cov, b_acc_cov, b_acc_cov));

    double epsi[23] = {0.001};
    fill(epsi, epsi + 23, 0.001);
    kf.init_dyn_share(get_f, df_dx, df_dw, h_share_model, NUM_MAX_ITERATIONS, epsi);  
    kfindex = -1;
    FILE *fp;
    string pos_log_dir = root_dir + "/Log/pos_log.txt";
    fp = fopen(pos_log_dir.c_str(), "w");

    ofstream H_OUT;
    H_OUT.open(DEBUG_FILE_DIR("H_OUT.txt"), ios::out);

    ros::Subscriber sub_pcl = p_pre->lidar_type == AVIA ? nh.subscribe(lid_topic, 200000, livox_pcl_cbk) : nh.subscribe(lid_topic, 200000, standard_pcl_cbk); //fastlio2中只有面特征
    ros::Subscriber sub_imu = nh.subscribe(imu_topic, 200000, imu_cbk);
    ros::Subscriber sub_repaired;   // native recovery: repaired measurements
    ros::Publisher pubLaserCloudFull = nh.advertise<sensor_msgs::PointCloud2>("/cloud_registered", 100000);
    ros::Publisher pubLaserCloudFull_body = nh.advertise<sensor_msgs::PointCloud2>("/cloud_registered_body", 100000);
    ros::Publisher pubLaserCloudFull_lidar = nh.advertise<sensor_msgs::PointCloud2>("/cloud_registered_lidar", 100000);
    ros::Publisher pubLaserCloudEffect = nh.advertise<sensor_msgs::PointCloud2>("/cloud_effected", 100000);
    ros::Publisher pubLaserCloudMap = nh.advertise<sensor_msgs::PointCloud2>("/Laser_map", 100000);
    ros::Publisher pubOdomAftMapped = nh.advertise<nav_msgs::Odometry>("/Odometry", 100000);
    ros::Publisher pubPath = nh.advertise<nav_msgs::Path>("/path", 100000);
    ros::Publisher pubissleeping = nh.advertise<std_msgs::Bool>("Issleeping", 10);
    ros::Publisher pubisbuilding = nh.advertise<std_msgs::Bool>("Isbuilding", 10);
    // Native recovery channel (F1). Off unless native_recovery_dir is set.
    nh.param<std::string>("native_recovery_dir", g_nr_dir, "");
    nh.param<bool>("native_recovery_online_refusal", g_nr_online_refusal, false);
    nh.param<bool>("native_recovery_compare_refusal", g_nr_compare_refusal, true);
    nh.param<bool>("native_recovery_imu_probe", g_nr_imu_probe_enabled, false);
    g_nr_imu_probe_enabled = g_nr_online_refusal && g_nr_imu_probe_enabled;
    ros::Publisher private_odom;
    if (g_nr_online_refusal)
        private_odom = nh.advertise<nav_msgs::Odometry>("/native_recovery/observation_odom", 1000);
    if (!g_nr_dir.empty())
    {
        ::mkdir(g_nr_dir.c_str(), 0755);
        nr_write_caps();
        g_nr_fates.open(g_nr_dir + "/input_fates.jsonl", std::ios::out);
        g_nr_updates.open(g_nr_dir + "/repair_updates.jsonl", std::ios::out);
        if (g_nr_online_refusal && g_nr_compare_refusal)
            g_nr_comparison_trace.open(g_nr_dir + "/refusal_comparison.jsonl", std::ios::out);
        if (g_nr_imu_probe_enabled)
            g_nr_imu_trace.open(g_nr_dir + "/imu_recovery_observations.jsonl", std::ios::out);
        g_nr_running.store(true);
        std::thread(nr_poll_thread).detach();
        sub_repaired = nh.subscribe("/native_recovery/repaired_scan", 50, nr_repaired_cbk);
        ROS_INFO("[NATIVE_RECOVERY] channel on %s", g_nr_dir.c_str());
    }

    signal(SIGINT, SigHandle);
    ros::Rate rate(5000);
    bool status = ros::ok();

    int key = 0;
    auto& degradation_count = g_nr_degradation_count;
    auto& getDegradationpre_point = g_nr_degradation_history;
    auto& isIMU_init_dynamic = g_nr_dynamic_imu;
    auto& isPublish = g_nr_is_publish;
    while (status)
    {
        if (flg_exit)
            break;
        // Finish the private arm before answering status, so a drained native arm is never
        // mistaken for completed refusal replay by the controller.
        nr_start_refusal_after_native_arm();
        nr_apply_pending();
        ros::spinOnce();
        g_nr_cur_is_replay = !g_nr_replay_groups.empty();
        g_nr_cur_repaired = false;
        bool replay_imu_only = false;
        const bool draining_live = !g_nr_hold.load() && !g_nr_after_refusal.empty();
        if (g_nr_cur_is_replay || draining_live || (!g_nr_refusal_target && sync_packages(Measures)))
        {
            if (g_nr_cur_is_replay || draining_live)
            {
                auto& queue = g_nr_cur_is_replay ? g_nr_replay_groups : g_nr_after_refusal;
                NrGroup group = std::move(queue.front());
                queue.pop_front();
                Measures.lidar = group.lidar;
                Measures.imu = std::move(group.imu);
                Measures.lidar_beg_time = group.beg;
                lidar_end_time = group.end;
                g_nr_cur_repaired = group.repaired;
                replay_imu_only = group.imu_only;
                g_nr_replay_remaining = (int)g_nr_replay_groups.size();
                g_nr_replay.store(g_nr_replay_remaining > 0);
            }
            else
                nr_apply_deferred(lidar_end_time);
            if (flg_reset)
            {
                ROS_WARN("reset when rosbag play back");
                p_imu->Reset();
                flg_reset = false;
                Measures.imu.clear();
                continue;
            }
            nr_capture_group();
            if (g_nr_imu_probe && g_nr_hold.load() && !g_nr_cur_is_replay &&
                !nr_advance_imu_probe(*g_nr_imu_probe, Measures, lidar_end_time))
                g_nr_imu_probe.reset();
            double t0, t1, t2, t3, t4, t5, match_start, solve_start, svd_time;
            
            match_time = 0;
            kdtree_search_time = 0.0;
            solve_time = 0;
            solve_const_H_time = 0;
            svd_time = 0;
            t0 = omp_get_wtime();
            p_imu->imu_init_dynamic = isIMU_init_dynamic;
            p_imu->Process(Measures, kf, feats_undistort, Degradationpre_point);
            state_point = kf.get_x();
            pos_lid = state_point.pos + state_point.rot * state_point.offset_T_L_I;

            if (replay_imu_only)
            {
                g_nr_lidar_end = lidar_end_time;
                ++g_nr_frame;
                ++g_nr_refusal_consumed;
                nr_record_comparison_frame("imu_only");
                nr_log_fate(lidar_end_time, Measures.lidar_beg_time, "replayed_imu_only");
                continue;
            }

            if (feats_undistort->empty() || (feats_undistort == NULL))
            {
                first_lidar_time = Measures.lidar_beg_time;
                p_imu->first_lidar_time = first_lidar_time;
                nr_record_comparison_frame("no_scan_update");
                // cout<<"FAST-LIO not ready"<<endl;
                continue;
            }

            flg_EKF_inited = (Measures.lidar_beg_time - first_lidar_time) < INIT_TIME ? false : true;
            if (!g_nr_online_refusal || !g_nr_hold.load() || g_nr_cur_is_replay)
                lasermap_fov_segment();

            /*** downsample the feature points in a scan ***/
            downSizeFilterSurf.setInputCloud(feats_undistort);
            downSizeFilterSurf.filter(*feats_down_body);
            t1 = omp_get_wtime();
            feats_down_size = feats_down_body->points.size();
            /*** initialize the map kdtree ***/
            if (ikdtree.Root_Node == nullptr)
            {
                if (feats_down_size > 5)
                {
                    ikdtree.set_downsample_param(filter_size_map_min);
                    feats_down_world->resize(feats_down_size);
                    for (int i = 0; i < feats_down_size; i++)
                    {
                        pointBodyToWorld(&(feats_down_body->points[i]), &(feats_down_world->points[i]));
                    }
                    ikdtree.Build(feats_down_world->points);
                }
                continue;
            }
            int featsFromMapNum = ikdtree.validnum();
            kdtree_size_st = ikdtree.size();

            // cout<<"[ mapping ]: In num: "<<feats_undistort->points.size()<<" downsamp "<<feats_down_size<<" Map num: "<<featsFromMapNum<<"effect num:"<<effct_feat_num<<endl;

            /*** ICP and iterated Kalman filter update ***/
            normvec->resize(feats_down_size);
            feats_down_world->resize(feats_down_size);

            V3D ext_euler = SO3ToEuler(state_point.offset_R_L_I);
            Matrix<double, 23, 23> P_pre_; 
            P_pre_ = kf.get_P();

            if (0)
            {
                PointVector().swap(ikdtree.PCL_Storage);
                ikdtree.flatten(ikdtree.Root_Node, ikdtree.PCL_Storage, NOT_RECORD);
                featsFromMap->clear();
                featsFromMap->points = ikdtree.PCL_Storage;
            }

            pointSearchInd_surf.resize(feats_down_size);
            Nearest_Points.resize(feats_down_size);
            int rematch_num = 0;
            bool nearest_search_en = true; //

            t2 = omp_get_wtime();

            /*** iterated state estimation ***/
            double t_update_start = omp_get_wtime();
            double solve_H_time = 0;
            kf.update_iterated_dyn_share_modified(LASER_POINT_COV, solve_H_time, H_OUT);
            kfindex = (kfindex + 1) % kfQueLength;
            kfqueue[kfindex] = kf;
            state_point = kf.get_x();
            euler_cur = SO3ToEuler(state_point.rot);
            pos_lid = state_point.pos + state_point.rot * state_point.offset_T_L_I;
            geoQuat.x = state_point.rot.coeffs()[0];
            geoQuat.y = state_point.rot.coeffs()[1];
            geoQuat.z = state_point.rot.coeffs()[2];
            geoQuat.w = state_point.rot.coeffs()[3];

            double t_update_end = omp_get_wtime();


            /*** Debug variables ***/
            Matrix<double, 23, 23> P_out_; 
            P_out_ = kf.get_P();
            key++;
			auto h_out_ = (P_out_.template block<3,3>(0, 0)).eigenvalues().real();
            H_OUT <<key<< " ";
            for( int i=0; i<3; i++ ){
                H_OUT<<h_out_(i)<< " ";         
            }
            H_OUT<<endl;
            if(P_out_(0,0)>0.0006 || P_out_(1,1)>0.0006 || P_out_(2,2)>0.0005 ) 
            {
                isPublish = false;
                isIMU_init_dynamic = true;
                if(getDegradationpre_point == 1)
                {
                    Degradationpre_point = kfqueue[0];
                    for(int i = 1; i<kfQueLength; ++i){
                        if(kfqueue[i].get_P()(22, 22) < Degradationpre_point.get_P()(22, 22)){Degradationpre_point = kfqueue[i];}
                    }
                }
                ++degradation_count;
                ++getDegradationpre_point;
                cout<<"Degeneracy has happened "<<degradation_count<<" times"<<endl;
                // bool hasPubbuild = false;
                if( degradation_count > 1)
                {
                    
                    if(hasPubbuild)
                    {
                        hasPubbuild = false;
                    }
                    if (!hasPubsleep)
                    {
                        // 发布消息
                        std_msgs::Bool issleeping;
                        issleeping.data = true;
                        if (!g_nr_native_arm_running) pubissleeping.publish(issleeping);
                        cout<<"Over-degeneracy has happened, publish hibernating map operation!!!!!!!!!!!!!"<<endl;
                        hasPubsleep = true;
                    }
                    degradation_count = 0;
                    if (g_nr_native_arm_running)
                    {
                        nr_record_comparison_frame("native_reset_due");
                        g_nr_replay_groups.clear();
                        continue;
                    }
                    nr_record_comparison_frame("refusal_reset_due");
                    if (g_nr_hold.load())
                    {
                        // The driver holds the map, so the driver owns the recovery. re_slam()
                        // here would clear the map and invalidate the checkpoint the driver is
                        // about to replay from; that is the interference the contract rules out.
                        // The degeneracy is still counted and still observable (Issleeping is
                        // published), only the reset is deferred. `resume` restores the policy, so
                        // a host that is still degenerate after the driver releases it resets on
                        // its own two frames later, exactly as it would have.
                        ++g_nr_deferred_resets;
                        cout<<"Degeneracy during external hold: native re_slam deferred ("
                            <<g_nr_deferred_resets<<")"<<endl;
                    }
                    else
                    {
                        re_slam();
                    }
                    continue;
                }
            }else{
                isPublish = true;
                if(hasPubsleep){
                    if (!hasPubbuild)
                    {
                        cout<<"Over-degeneracy has disappear, construct a new map....................."<<endl;
                        getDegradationpre_point = 0;
                        isIMU_init_dynamic = false;
                        isPublish = true;
                        std_msgs::Bool isbuilding;
                        isbuilding.data = true;
                        if (!g_nr_native_arm_running) pubisbuilding.publish(isbuilding);
                        hasPubbuild = true; 
                    }
                    hasPubsleep = false;
                }
            }

            /******* Publish odometry *******/
            // While the driver holds the map it is the consumer that asked for this stream, and
            // it needs the frames that span the degeneracy to judge the segment at all. Without
            // this, the host stops publishing exactly at its own onset and the driver's
            // quarantine window can only ever contain the healthy frames before it (v8 run:
            // 20/20 frames improved by nothing, gate refused). Map writes stay governed by the
            // hold inside map_incremental(); only the publication gate is widened here, and the
            // capability declares it as publish_gating=isPublish+held.
            if(isPublish || (g_nr_hold.load() && !g_nr_native_arm_running)){
                const bool public_output = !g_nr_online_refusal || !g_nr_hold.load();
                if (g_nr_online_refusal && !g_nr_cur_is_replay)
                {
                    nav_msgs::Odometry observation;
                    // Pair with the original LiDAR scan start, rather than its end.
                    observation.header.stamp = ros::Time().fromSec(Measures.lidar_beg_time);
                    observation.header.frame_id = "camera_init";
                    observation.child_frame_id = "lidar";
                    const Eigen::Quaterniond lidar_rotation(state_point.rot * state_point.offset_R_L_I);
                    observation.pose.pose.position.x = pos_lid.x();
                    observation.pose.pose.position.y = pos_lid.y();
                    observation.pose.pose.position.z = pos_lid.z();
                    observation.pose.pose.orientation.x = lidar_rotation.x();
                    observation.pose.pose.orientation.y = lidar_rotation.y();
                    observation.pose.pose.orientation.z = lidar_rotation.z();
                    observation.pose.pose.orientation.w = lidar_rotation.w();
                    nr_write_imu_observation(state_point);
                    private_odom.publish(observation);
                }
                if (public_output) publish_odometry(pubOdomAftMapped);
                /*** add the feature points to map kdtree ***/
                t3 = omp_get_wtime();
                map_incremental();
                if (g_nr_cur_repaired) ++g_nr_repaired_map_updates;
                t5 = omp_get_wtime();

                /******* Publish points *******/
                if (public_output) publish_path(pubPath);
                if (public_output && (scan_pub_en || pcd_save_en))
                    publish_frame_world(pubLaserCloudFull);
                if (public_output && scan_pub_en && scan_body_pub_en && isPublish)
                {
                    publish_frame_body(pubLaserCloudFull_body);
                    publish_frame_lidar(pubLaserCloudFull_lidar);
                }
            }
            if (0)
            {
                frame_num++;
                kdtree_size_end = ikdtree.size();
                aver_time_consu = aver_time_consu * (frame_num - 1) / frame_num + (t5 - t0) / frame_num;
                aver_time_icp = aver_time_icp * (frame_num - 1) / frame_num + (t_update_end - t_update_start) / frame_num;
                aver_time_match = aver_time_match * (frame_num - 1) / frame_num + (match_time) / frame_num;
                aver_time_incre = aver_time_incre * (frame_num - 1) / frame_num + (kdtree_incremental_time) / frame_num;
                aver_time_solve = aver_time_solve * (frame_num - 1) / frame_num + (solve_time + solve_H_time) / frame_num;
                aver_time_const_H_time = aver_time_const_H_time * (frame_num - 1) / frame_num + solve_time / frame_num;
                T1[time_log_counter] = Measures.lidar_beg_time;
                s_plot[time_log_counter] = t5 - t0;
                s_plot2[time_log_counter] = feats_undistort->points.size();
                s_plot3[time_log_counter] = kdtree_incremental_time;
                s_plot4[time_log_counter] = kdtree_search_time;
                s_plot5[time_log_counter] = kdtree_delete_counter;
                s_plot6[time_log_counter] = kdtree_delete_time;
                s_plot7[time_log_counter] = kdtree_size_st;
                s_plot8[time_log_counter] = kdtree_size_end;
                s_plot9[time_log_counter] = aver_time_consu;
                s_plot10[time_log_counter] = add_point_size;
                time_log_counter++;
                // printf("[ mapping ]: time: IMU + Map + Input Downsample: %0.6f ave match: %0.6f ave solve: %0.6f  ave ICP: %0.6f  map incre: %0.6f ave total: %0.6f icp: %0.6f construct H: %0.6f \n", t1 - t0, aver_time_match, aver_time_solve, t3 - t1, t5 - t3, aver_time_consu, aver_time_icp, aver_time_const_H_time);
                ext_euler = SO3ToEuler(state_point.offset_R_L_I);
                dump_lio_state_to_log(fp);
            }
            if (g_nr_cur_repaired)
            {
                // The repaired cloud went through this native update, not just through the queue.
                ++g_nr_repaired_in_update;
                g_nr_last_repaired_update_ns = (long long)std::llround(lidar_end_time * 1e9);
                g_nr_updates << "{\"scan_stamp_ns\":"
                    << (long long)std::llround(Measures.lidar_beg_time * 1e9)
                    << ",\"end_stamp_ns\":" << g_nr_last_repaired_update_ns
                    << ",\"map_update_count\":" << g_nr_repaired_map_updates
                    << ",\"map_points\":" << ikdtree.validnum() << "}" << std::endl;
            }
            g_nr_lidar_end = lidar_end_time;
            ++g_nr_frame;
            nr_record_comparison_frame(isPublish ? "lidar_tracking" : "tracking_unavailable");
            if (g_nr_refusal_target && g_nr_cur_is_replay && !g_nr_native_arm_running)
                ++g_nr_refusal_consumed;
            nr_log_fate(lidar_end_time, Measures.lidar_beg_time,
                        g_nr_cur_is_replay ? "replayed" : (g_nr_hold.load() ? "quarantined" : "ingested"));

        }
        status = ros::ok();
        rate.sleep();
    }

    /**************** save map ****************/
    /* 1. make sure you have enough memories
    /* 2. pcd save will largely influence the real-time performences **/
    if (pcl_wait_save->size() > 0 && pcd_save_en)
    {
        string file_name = string("scans.pcd");
        string all_points_dir(string(string(ROOT_DIR) + "PCD/") + file_name);
        pcl::PCDWriter pcd_writer;
        cout << "current scan saved to /PCD/" << file_name << endl;
        pcd_writer.writeBinary(all_points_dir, *pcl_wait_save);
    }

    if (runtime_pos_log)
    {
        vector<double> t, s_vec, s_vec2, s_vec3, s_vec4, s_vec5, s_vec6, s_vec7;
        FILE *fp2;
        string log_dir = root_dir + "/Log/fast_lio_time_log.csv";
        fp2 = fopen(log_dir.c_str(), "w");
        fprintf(fp2, "time_stamp, total time, scan point size, incremental time, search time, delete size, delete time, tree size st, tree size end, add point size, preprocess time\n");
        for (int i = 0; i < time_log_counter; i++)
        {
            fprintf(fp2, "%0.8f,%0.8f,%d,%0.8f,%0.8f,%d,%0.8f,%d,%d,%d,%0.8f\n", T1[i], s_plot[i], int(s_plot2[i]), s_plot3[i], s_plot4[i], int(s_plot5[i]), s_plot6[i], int(s_plot7[i]), int(s_plot8[i]), int(s_plot10[i]), s_plot11[i]);
            t.push_back(T1[i]);
            s_vec.push_back(s_plot9[i]);
            s_vec2.push_back(s_plot3[i] + s_plot6[i]);
            s_vec3.push_back(s_plot4[i]);
            s_vec5.push_back(s_plot[i]);
        }
        fclose(fp2);
    }

    return 0;
}
