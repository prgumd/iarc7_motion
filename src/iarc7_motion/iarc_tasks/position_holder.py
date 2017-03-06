#!/usr/bin/env python

# A helper class for a task that will spit out a velocity that's appropriate
# to reach and hold a desired position

import math
import threading

import rospy

from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry

class PositionHolder():
    def __init__(self, x=None, y=None):
        update_rate = rospy.get_param('~update_rate', False)
        #self._update_period = 1.0/update_rate
        self._update_period = 0.1
        self._lock = threading.RLock()
        self._odometry = None
        self._hold_x = x
        self._hold_y = y
        self._max_acceleration = rospy.get_param('~max_translation_acceleration', 0.0)
        self._max_speed = rospy.get_param('~max_translation_speed', 0.0)
        self._position_tolerance = rospy.get_param('~translation_position_hold_tolerance', 0.0)
        self._current_velocity_sub = rospy.Subscriber('/odometry/filtered',
                                              Odometry,
                                              self._current_velocity_callback)

    def get_xy_hold_response(self, current_x, current_y, z_velocity=None):
        with self._lock:
            if self._odometry is not None:
                delta_x = current_x - self._hold_x
                delta_y = current_y - self._hold_y
                response = self._get_next_acceleration_target_trapezoidal(delta_x,
                                                                          delta_y,
                                                                          self._odometry.twist,
                                                                          z_velocity=z_velocity)
            else:
                rospy.logerr('get_xy_hold_response called before odometry published')

            return response

    def _current_velocity_callback(self, odometry):
        with self._lock:
            if odometry.header.frame_id == 'map' and odometry.child_frame_id == 'level_quad':
                self._odometry = odometry
                if self._hold_x is None:
                    self._hold_x = odometry.pose.pose.position.x
                if self._hold_y is None:
                    self._hold_y = odometry.pose.pose.position.y

    def _calculate_trapezoidal_acceleration(self, distance, speed):
        # Check if we can decelerate in time
        try:
            target_acceleration = (speed**2)/(2*distance)
        except ZeroDivisionError:
            # We are at the target point, no need to accelerate anywhere
            return 0.0

        if target_acceleration < self._max_acceleration:
            if speed < self._max_speed:
                target_acceleration = self._max_acceleration
            else:
                target_acceleration = 0
        else:
            target_acceleration = -self._max_acceleration

        return target_acceleration

    def _get_next_acceleration_target_trapezoidal(self, x, y, current_twist, z_velocity=None):
        # calculate current straight line velocity
        speed = math.sqrt(current_twist.twist.linear.x**2 + current_twist.twist.linear.y**2)
        # calculate straight line distance
        distance = math.sqrt(x**2 + y**2)

        target_acceleration = self._calculate_trapezoidal_acceleration(distance, speed)

        current_angle = math.atan2(y, x)

        target_twist = TwistStamped()
        target_twist.header.stamp = rospy.Time.now()
        target_twist.header.frame_id = 'level_quad'

        if distance > self._position_tolerance:
            target_twist.twist.linear.x = (current_twist.twist.linear.x
                                          + (target_acceleration
                                          *  self._update_period
                                          * -math.cos(current_angle)))
            target_twist.twist.linear.y = (current_twist.twist.linear.y
                                          + (target_acceleration
                                          * self._update_period
                                          * -math.sin(current_angle)))
        else:
            target_twist.twist.linear.x = 0.0
            target_twist.twist.linear.y = 0.0
            rospy.logdebug('tolerance hit')

        rospy.logdebug('ta %s current angle %s', target_acceleration, current_angle)
        rospy.logdebug('dx %s dy %s dvx %s dvy %s vx %s vy %s', x, y,
         target_acceleration * self._update_period * -math.cos(current_angle),
         target_acceleration * self._update_period * -math.sin(current_angle),
         target_twist.twist.linear.x, target_twist.twist.linear.y)

        if z_velocity is not None:
            target_twist.twist.linear.z = z_velocity

        # Set a target accleration by setting velocity that's timestamped into the future based on the current velocity
        return target_twist
