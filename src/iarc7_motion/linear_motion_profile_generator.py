#!/usr/bin/env python

import rospy
import numpy as np

from iarc7_msgs.msg import MotionPointStamped, MotionPointStampedArray

# Convert a 3 element numpy array to a Vector3 message
def np_to_msg(array, msg):
    msg.x = array[0]
    msg.y = array[1]
    msg.z = array[2]
    return msg

# Convert a Vector3 message to 3 element numpy array
def msg_to_np(msg):
    return np.array([msg.x, msg.y, msg.z])

# Interpolate two values
def interpolate(first, second, fraction):
    return fraction * (second - first) + first

# Interpolate two motion points
def interpolate_motion_points(first, second, time):
    fraction = ((time - first.header.stamp)
                / (second.header.stamp - first.header.stamp))

    result = MotionPointStamped()
    result.header.stamp = time

    result.motion_point.pose.position.x = interpolate(
                      first.motion_point.pose.position.x,
                      second.motion_point.pose.position.x,
                      fraction)
    result.motion_point.pose.position.y = interpolate(
                      first.motion_point.pose.position.y,
                      second.motion_point.pose.position.y,
                      fraction)
    result.motion_point.pose.position.z = interpolate(
                      first.motion_point.pose.position.z,
                      second.motion_point.pose.position.z,
                      fraction)

    result.motion_point.twist.linear.x = interpolate(
                      first.motion_point.twist.linear.x,
                      second.motion_point.twist.linear.x,
                      fraction)
    result.motion_point.twist.linear.y = interpolate(
                      first.motion_point.twist.linear.y,
                      second.motion_point.twist.linear.y,
                      fraction)
    result.motion_point.twist.linear.z = interpolate(
                      first.motion_point.twist.linear.z,
                      second.motion_point.twist.linear.z,
                      fraction)

    result.motion_point.accel.linear.x = interpolate(
                      first.motion_point.accel.linear.x,
                      second.motion_point.accel.linear.x,
                      fraction)
    result.motion_point.accel.linear.y = interpolate(
                      first.motion_point.accel.linear.y,
                      second.motion_point.accel.linear.y,
                      fraction)
    result.motion_point.accel.linear.z = interpolate(
                      first.motion_point.accel.linear.z,
                      second.motion_point.accel.linear.z,
                      fraction)

    return result

# Generates fully defined motion profiles
class LinearMotionProfileGenerator(object):
    def __init__(self, start_motion_point):
        self._last_motion_plan = None
        self._start_motion_point = start_motion_point

        try:
            self._TARGET_ACCEL = rospy.get_param('~linear_motion_profile_acceleration')
            self._PLAN_DURATION = rospy.get_param('~linear_motion_profile_duration')
            self._PROFILE_TIMESTEP = rospy.get_param('~linear_motion_profile_timestep')
        except KeyError as e:
            rospy.logerr('Could not lookup a parameter for linear motion profile generator')
            raise

        self._last_stamp = rospy.Time.now()

    # Reinitialize the start point to some desired value
    def reinitialize_start_point(self, start_motion_point):
        self._start_motion_point = start_motion_point

    # Get a starting motion point for a given time
    def _get_start_point(self, time):
        # Get the starting point from the current motion plane
        if self._start_motion_point is not None:
            start_motion_point = self._start_motion_point
            self._start_motion_point = None

            # Check that the time is at least equal to the current time
            # before generating a plan
            if start_motion_point.header.stamp < rospy.Time.now():
                start_motion_point.header.stamp = rospy.Time.now()
            return start_motion_point

        else:
            # Make sure a starting point newer than the last sent time is sent
            for i in range(1, len(self._last_motion_plan.motion_points)):
                if self._last_motion_plan.motion_points[i].header.stamp > time:
                    first_point = self._last_motion_plan.motion_points[i-1]
                    second_point = self._last_motion_plan.motion_points[i]
                    return interpolate_motion_points(first_point, second_point, time)

            # A point was not sent before the buffer ran out
            # Use the oldest and reset the timestamp
            self._last_motion_plan.motion_points[-1].header.stamp = rospy.Time.now()
            return self._last_motion_plan.motion_points[-1]

    # Get a motion plan that attempts to achieve a given velocity target
    def get_velocity_plan(self, velocity_command):

        # Get the stating motion point for the time that the velocity is desired
        start_point = self._get_start_point(velocity_command.target_twist.header.stamp)

        self._last_stamp = velocity_command.target_twist.header.stamp

        p_start = msg_to_np(start_point.motion_point.pose.position)
        v_start = msg_to_np(start_point.motion_point.twist.linear)
        v_desired = msg_to_np(velocity_command.target_twist.twist.linear)
        v_delta = v_desired - v_start

        # Assign a direction to the target acceleration
        a_target = self._TARGET_ACCEL * v_delta / np.linalg.norm(v_delta)

        # Find the time required to accelerate to the desired velocity
        acceleration_time = min(np.linalg.norm(v_delta) / self._TARGET_ACCEL, self._PLAN_DURATION)

        # Use the rest of the profile duration to hold the velocity
        steady_velocity_time = self._PLAN_DURATION - acceleration_time

        # Calculate the number of discrete steps spent in each state
        accel_steps = np.floor(acceleration_time / self._PROFILE_TIMESTEP)
        vel_steps = np.floor(steady_velocity_time / self._PROFILE_TIMESTEP)

        # Initialize the velocities array with the starting velocity
        velocities = [v_start]

        # Generate velocities corresponding to the acceleration period
        if accel_steps > 0:
            accel_times = (np.linspace(0.0, accel_steps*self._PROFILE_TIMESTEP, accel_steps)
                     * accel_steps
                     * self._PROFILE_TIMESTEP)
            velocities.extend([a_target * accel_time + v_start for accel_time in accel_times])

        # Add the velocities for the steady velocity period
        velocities.extend([v_desired for i in range(0, int(vel_steps))])

        velocities = np.array(velocities)

        # Differentiate velocities to get the accelerations
        # This results in an array one element shorter than
        # the velocities array
        accelerations = np.diff(velocities, axis=0) / self._PROFILE_TIMESTEP

        # Integrate the velocities to get the position deltas
        # This results in an array the same length as the velocities array
        # But the positions correspond to the velocities one index higher than
        # the given positio index
        positions = (np.cumsum(velocities, axis=0) * self._PROFILE_TIMESTEP
                     + p_start)

        plan = MotionPointStampedArray()

        # Fill out the first motion point since it follows different
        # rules than the rest
        motion_point = MotionPointStamped()
        motion_point.header.stamp = start_point.header.stamp
        np_to_msg(accelerations[0], motion_point.motion_point.accel.linear)
        np_to_msg(v_start, motion_point.motion_point.twist.linear)
        np_to_msg(p_start, motion_point.motion_point.pose.position)
        plan.motion_points.append(motion_point)

        # Generate the motion profile for all the remaining velocities and accelerations
        for i in range(1, velocities.shape[0]-1):
            motion_point = MotionPointStamped()
            motion_point.header.stamp = (start_point.header.stamp
                                         + rospy.Duration(i * self._PROFILE_TIMESTEP))
            np_to_msg(accelerations[i], motion_point.motion_point.accel.linear)
            np_to_msg(velocities[i], motion_point.motion_point.twist.linear)
            np_to_msg(positions[i-1], motion_point.motion_point.pose.position)
            plan.motion_points.append(motion_point)

        self._last_motion_plan = plan
        return plan
