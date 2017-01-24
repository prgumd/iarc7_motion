////////////////////////////////////////////////////////////////////////////
//
// Quad Velocity Controller
//
// Accepts a target velocity and uses 4 PID loops (pitch, yaw, roll, thrust)
// To attempt to hit the target velocity.
//
////////////////////////////////////////////////////////////////////////////

#ifndef QUAD_VELOCITY_CONTROLLER_H
#define QUAD_VELOCITY_CONTROLLER_H

#include <ros/ros.h>
#include "iarc7_motion/FeedForwardPid.hpp"
#include "tf2_ros/transform_listener.h"

#include "geometry_msgs/Transform.h"
#include "geometry_msgs/TransformStamped.h"
#include "geometry_msgs/TwistStamped.h"
#include "geometry_msgs/Vector3.h"
#include "geometry_msgs/Vector3Stamped.h"
#include "iarc7_msgs/Float64Stamped.h"
#include "iarc7_msgs/OrientationThrottleStamped.h"

namespace Iarc7Motion
{

    class QuadVelocityController
    {
    public:
        QuadVelocityController() = delete;

        // Require that PID parameters are passed in upon class creation
        QuadVelocityController(double thrust_pid[5],
                               double pitch_pid[5],
                               double roll_pid[5],
                               double yaw_pid[5]);

        ~QuadVelocityController() = default;

        // Don't allow the copy constructor or assignment.
        QuadVelocityController(const QuadVelocityController& rhs) = delete;
        QuadVelocityController& operator=(const QuadVelocityController& rhs) = delete;

        // Require checking of the returned value.
        // Used to update all PID loops according to a time delta that is passed in.
        // Return the uav_command it wants sent to the flight controller.
        bool __attribute__((warn_unused_result)) update(
            const ros::Time& time,
            iarc7_msgs::OrientationThrottleStamped& uav_command);

        // Set a target velocity for the PID loops
        void setTargetVelocity(geometry_msgs::Twist twist);

    private:

        /// Waits until a transform is available at time or later, returns
        /// true on success, returns a transform using the passed in reference to
        /// a transform.
        bool __attribute__((warn_unused_result)) getTransformAfterTime(
            const ros::Time& time,
            geometry_msgs::TransformStamped& transform,
            const ros::Time& latest_time_allowed = ros::Time(0));

        /// Waits for the next transform to come in, returns true if velocities
        /// are valid.
        ///
        /// This must receive two transforms within the timeout period to
        /// consider the velocity valid.
        bool __attribute__((warn_unused_result)) getVelocities(
            geometry_msgs::Twist& return_velocities);

        // Used to store the transform buffer, required for tf2
        tf2_ros::Buffer tfBuffer_;
        // Used to store the transform listener, required for tf2
        tf2_ros::TransformListener tfListener_;

        // The four PID controllers
        FeedForwardPid throttle_pid_;
        FeedForwardPid pitch_pid_;
        FeedForwardPid roll_pid_;
        FeedForwardPid yaw_pid_;

        // A fudge feed forward value used for more stable hovering
        static constexpr double hover_throttle_{58.0};

        // Holds the last transform received to calculate velocities
        geometry_msgs::TransformStamped last_transform_stamped_;
        // Hold the last yaw for calculations
        double last_yaw_;

        // Holds the last valid velocity reading
        bool have_last_velocity_stamped_;
        geometry_msgs::TwistStamped last_velocity_stamped_;

        // Makes sure that we have a lastTransformStamped before returning a valid velocity
        bool ran_once_;

        static constexpr double MAX_TRANSFORM_WAIT_SECONDS{1.0};
        static constexpr double MAX_TRANSFORM_DIFFERENCE_SECONDS{0.3};
    };

}

#endif // QUAD_VELOCITY_CONTROLLER_H
