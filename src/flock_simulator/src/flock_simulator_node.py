#!/usr/bin/env python

import rospy
import tf
import state_manager
from std_msgs.msg import String, Bool, UInt8, UInt32
from geometry_msgs.msg import Pose2D, Twist, Vector3
from flock_simulator.msg import Request, FlockState, FlockCommand, DuckieState


class FlockSimulatorNode(object):
    def __init__(self, map_name, n_duckies, t_requests):
        self.node_name = rospy.get_name()

        self.state_manager = state_manager.StateManager(
            map_name, n_duckies, t_requests)

        # Subscribers
        self.sub_paths = rospy.Subscriber(
            '/flock_simulator/commands',
            FlockCommand,
            self.cbCommands,
            queue_size=1)

        # Publishers
        self.pub_state = rospy.Publisher(
            '/flock_simulator/state', FlockState, queue_size=1)
        self.msg_state = FlockState()

        self.isUpdating = False

    def cbCommands(self, msg):
        # Return same state if last callback has not finished
        if self.isUpdating:
            rospy.logwarn(
                'State not finished updating. Publishing previous state again.'
            )
            self.pub_state.publish(self.msg_state)
            return

        # Update state
        self.isUpdating = True
        dt = msg.dt.data
        commands = self.getCommands(msg)
        self.state_manager.updateState(commands, dt)
        self.isUpdating = False

        # Publish
        self.msg_state = self.generateFlockStateMsg(
            self.state_manager.duckies, self.state_manager.requests,
            self.state_manager.filled_requests)
        self.pub_state.publish(self.msg_state)
        self.publishTf()

    def getCommands(self, msg):
        commands = {}
        for command in msg.duckie_commands:
            on_rails = command.on_rails.data
            if on_rails:
                path = []
                for node in command.path:
                    path.append(node.data)
                commands[command.duckie_id.data] = {
                    'path': path,
                    'on_rails': on_rails,
                    'request_id': command.request_id.data
                }
            else:
                commands[command.duckie_id.data] = {
                    'linear': command.velocity_command.linear.x,
                    'angular': command.velocity_command.angular.z,
                    'on_rails': on_rails
                }
        return commands

    def generateFlockStateMsg(self, duckies, requests, filled_requests):
        msg = FlockState()
        msg.header.stamp = rospy.Time.now()

        for request_id in requests:
            request = requests[request_id]
            request_msg = Request()
            request_msg.request_id = String(data=request.id)
            request_msg.start_time = UInt32(data=request.start_time)
            request_msg.pickup_time = UInt32(data=request.pickup_time)
            request_msg.start_node = String(data=request.start_node)
            request_msg.end_node = String(data=request.end_node)
            request_msg.duckie_id = String(data=request.duckie_id)
            msg.requests.append(request_msg)

        for request_id in filled_requests:
            request = filled_requests[request_id]
            request_msg = Request()
            request_msg.request_id = String(data=request.id)
            request_msg.start_time = UInt32(data=request.start_time)
            request_msg.pickup_time = UInt32(data=request.pickup_time)
            request_msg.end_time = UInt32(data=request.end_time)
            request_msg.start_node = String(data=request.start_node)
            request_msg.end_node = String(data=request.end_node)
            request_msg.duckie_id = String(data=request.duckie_id)
            msg.filled_requests.append(request_msg)

        for duckie_id in duckies:
            duckie = duckies[duckie_id]
            duckiestate_msg = DuckieState()
            duckiestate_msg.duckie_id = String(data=duckie_id)
            duckiestate_msg.status = String(data=duckie.status)
            duckiestate_msg.lane = String(data=duckie.next_point['lane'])
            duckiestate_msg.pose = Pose2D(
                x=duckie.pose.p[0] * self.state_manager.dt_map.tile_size,
                y=duckie.pose.p[1] * self.state_manager.dt_map.tile_size,
                theta=duckie.pose.theta)
            duckiestate_msg.velocity = Twist(
                linear=Vector3(duckie.velocity['linear'], 0, 0),
                angular=Vector3(0, 0, duckie.velocity['angular']))
            duckiestate_msg.in_fov = [
                String(data=visible_duckie) for visible_duckie in duckie.in_fov
            ]
            duckiestate_msg.collision_level = UInt8(
                data=duckie.collision_level)
            msg.duckie_states.append(duckiestate_msg)
        return msg

    def publishTf(self):
        duckies = self.state_manager.duckies
        requests = self.state_manager.requests
        stamp = rospy.Time.now()

        for duckie in duckies.values():
            theta = duckie.pose.theta
            x = duckie.pose.p[0] * self.state_manager.dt_map.tile_size
            y = duckie.pose.p[1] * self.state_manager.dt_map.tile_size

            transform_broadcaster.sendTransform((x, y, 0), \
                tf.transformations.quaternion_from_euler(0, 0, theta), \
                stamp, duckie.id, "duckiebot_link")

        for request in requests.values():
            if request.status == 'WAITING':
                pos_start = self.state_manager.dt_map.nodeToPose(
                    request.start_node).p.copy()
                pos_start[0] = pos_start[
                    0] * self.state_manager.dt_map.tile_size
                pos_start[1] = pos_start[
                    1] * self.state_manager.dt_map.tile_size
                transform_broadcaster.sendTransform((pos_start[0], pos_start[1], 0), \
                    tf.transformations.quaternion_from_euler(0, 0, 0), \
                    stamp, '%s' % request.id, "request_link")
            elif request.status == 'PICKEDUP':
                pos_end = self.state_manager.dt_map.nodeToPose(
                    request.end_node).p.copy()
                pos_end[0] = pos_end[0] * self.state_manager.dt_map.tile_size
                pos_end[1] = pos_end[1] * self.state_manager.dt_map.tile_size
                transform_broadcaster.sendTransform((pos_end[0], pos_end[1], 0), \
                    tf.transformations.quaternion_from_euler(0, 0, 0), \
                    stamp, '%s' % request.id, "request_link")

    def onShutdown(self):
        self.state_manager.printStatus(n_duckies, t_requests)
        rospy.loginfo('[%s] Shutdown.' % (self.node_name))


if __name__ == '__main__':
    rospy.init_node('flock_simulator_node', anonymous=False)
    map_name = rospy.get_param('~map_name')
    n_duckies = rospy.get_param('~n_duckies')
    t_requests = rospy.get_param('~t_requests')
    transform_broadcaster = tf.TransformBroadcaster()
    flock_simulator_node = FlockSimulatorNode(map_name, n_duckies, t_requests)
    rospy.on_shutdown(flock_simulator_node.onShutdown)
    rospy.spin()
