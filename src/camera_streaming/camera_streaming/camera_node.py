#!/usr/bin/env python3
"""Publish surface/underwater USB camera frames as ROS 2 image topics.

Captures frames with OpenCV (no usb_cam dependency) and publishes them as
sensor_msgs/Image on /camera/surface/image_raw and
/camera/underwater/image_raw. If a camera is not connected yet, this keeps
retrying to open it instead of crashing.
"""

import time

import cv2
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image


class CameraPublisher:
    def __init__(self, node: Node, name: str, device, topic: str,
                 width: int, height: int, fps: float):
        self.node = node
        self.name = name
        self.device = device
        self.frame_id = f'{name}_camera'
        self.pub = node.create_publisher(Image, topic, 10)
        self.cap = None
        self.width = width
        self.height = height
        self.fps = fps
        self.retry_interval = 2.0
        self.next_open_at = 0.0
        self._open()
        period = 1.0 / fps if fps > 0 else 0.1
        node.create_timer(period, self._tick)

    @staticmethod
    def _fourcc(value):
        value = int(value)
        return ''.join(chr((value >> (8 * i)) & 0xff) for i in range(4))

    def _open(self):
        # Force the Linux V4L2 backend instead of relying on OpenCV's backend
        # auto-detection. V4L2 opens the file descriptor first and negotiates
        # the format before streaming starts; bandwidth is allocated when the
        # stream is started by read().
        cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
        # Request MJPG (compressed) instead of the default uncompressed
        # format: two UVC cameras sharing one USB hub can exceed the hub's
        # isochronous bandwidth ("Not enough bandwidth for altsetting")
        # unless each stream is compressed.
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        if self.width:
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height:
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
        if self.fps > 0:
            cap.set(cv2.CAP_PROP_FPS, self.fps)

        if cap.isOpened():
            self.cap = cap
            actual_fourcc = self._fourcc(cap.get(cv2.CAP_PROP_FOURCC))
            actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            actual_fps = cap.get(cv2.CAP_PROP_FPS)
            self.node.get_logger().info(
                f'[{self.name}] opened {self.device}: '
                f'{actual_fourcc} {actual_width}x{actual_height} '
                f'@ {actual_fps:.1f} fps')
        else:
            cap.release()
            self.cap = None
            self.next_open_at = time.monotonic() + self.retry_interval
            self.node.get_logger().warn(
                f'[{self.name}] could not open {self.device}; '
                f'retrying in {self.retry_interval:.1f}s')

    def _tick(self):
        if self.cap is None:
            if time.monotonic() >= self.next_open_at:
                self._open()
            return
        ok, frame = self.cap.read()
        if not ok:
            self.node.get_logger().warn(
                f'[{self.name}] read failed on {self.device}; '
                f'retrying in {self.retry_interval:.1f}s')
            self.cap.release()
            self.cap = None
            self.next_open_at = time.monotonic() + self.retry_interval
            return
        msg = Image()
        msg.header.stamp = self.node.get_clock().now().to_msg()
        msg.header.frame_id = self.frame_id
        msg.height, msg.width = frame.shape[0], frame.shape[1]
        msg.encoding = 'bgr8'
        msg.is_bigendian = 0
        msg.step = msg.width * 3
        msg.data = frame.tobytes()
        self.pub.publish(msg)

    def release(self):
        if self.cap is not None:
            self.cap.release()


def main():
    rclpy.init()
    node = Node('camera_node')
    node.declare_parameter('surface_device', '/dev/video0')
    node.declare_parameter('underwater_device', '/dev/video6')
    node.declare_parameter('width', 640)
    node.declare_parameter('height', 480)
    node.declare_parameter('fps', 15.0)

    surface_device = node.get_parameter('surface_device').value
    underwater_device = node.get_parameter('underwater_device').value
    width = node.get_parameter('width').value
    height = node.get_parameter('height').value
    fps = node.get_parameter('fps').value

    cameras = [
        CameraPublisher(node, 'surface', surface_device,
                         '/camera/surface/image_raw', width, height, fps),
        CameraPublisher(node, 'underwater', underwater_device,
                         '/camera/underwater/image_raw', width, height, fps),
    ]

    try:
        rclpy.spin(node)
    finally:
        for cam in cameras:
            cam.release()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
