////////////////////////////////////////////////////////////////////////////
//
// Land Controller
//
// Handles basic landing
//
////////////////////////////////////////////////////////////////////////////

#ifndef LAND_CONTROLLER_H
#define LAND_CONTROLLER_H

#include <ros/ros.h>

#include "ros_utils/LinearMsgInterpolator.hpp"
#include "ros_utils/SafeTransformWrapper.hpp"

// ROS message headers
#include "iarc7_msgs/BoolStamped.h"
#include "iarc7_msgs/MotionPointStamped.h"
#include "iarc7_msgs/Arm.h"

namespace Iarc7Motion
{

enum class LandState { DESCEND,
                       DONE };

class LandPlanner
{
public:
    LandPlanner() = delete;

    // Require construction with a node handle and action server
    LandPlanner(ros::NodeHandle& nh, ros::NodeHandle& private_nh);

    ~LandPlanner() = default;

    // Don't allow the copy constructor or assignment.
    LandPlanner(const LandPlanner& rhs) = delete;
    LandPlanner& operator=(const LandPlanner& rhs) = delete;

    // Used to prepare and check initial conditions for landing
    bool __attribute__((warn_unused_result)) prepareForTakeover(
        const ros::Time& time);

    // Used to get a uav control message
    bool __attribute__((warn_unused_result)) getTargetMotionPoint(
        const ros::Time& time,
        iarc7_msgs::MotionPointStamped& target_twist);

    /// Waits until this object is ready to begin normal operation
    bool __attribute__((warn_unused_result)) waitUntilReady();

    bool isDone();

private:
    ros_utils::SafeTransformWrapper transform_wrapper_;

    LandState state_;

    double requested_x_;
    double requested_y_;
    double requested_height_;
    double cushion_height_;

    double actual_descend_rate_;

    // Rate at whicch to descent
    const double descend_rate_;
    const double cushion_rate_;

    // Rate at which to accelerate to descent velocity
    const double descend_acceleration_;
    const double cushion_acceleration_;

    // Height below which is considered landed
    const double landing_detected_height_;

    // Last time an update was successful
    ros::Time last_update_time_;

    // Max allowed timeout waiting for first velocity and transform
    const ros::Duration startup_timeout_;

    // Max allowed timeout waiting for velocities and transforms
    const ros::Duration update_timeout_;

    // Establishing service client used for disarm request
    ros::ServiceClient uav_arm_client_;
};

} // End namespace Iarc7Motion

#endif // LAND_CONTROLLER_H
