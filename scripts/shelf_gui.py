#!/usr/bin/env python3

import math
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

import rclpy
import yaml
from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, PoseWithCovarianceStamped
from nav2_msgs.action import NavigateToPose
from rclpy.action import ActionClient
from rclpy.node import Node


def yaw_to_quaternion(yaw):
    half_yaw = yaw * 0.5
    return {
        'z': math.sin(half_yaw),
        'w': math.cos(half_yaw),
    }


class ShelfNavigator(Node):
    def __init__(self):
        super().__init__('shelf_gui_action_client')
        self.declare_parameter('goal_file', '')

        self.goal_file = self.get_parameter('goal_file').value
        self.shelves, self.home = self.load_goals(self.goal_file)
        self.client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.active_goal_handle = None
        self.home_from_initial_pose = None
        self.spin_lock = threading.Lock()
        self.create_subscription(
            PoseWithCovarianceStamped,
            'initialpose',
            self.initial_pose_callback,
            10
        )

    def load_goals(self, path):
        if not path:
            raise RuntimeError('goal_file parameter is empty')

        with open(path, 'r', encoding='utf-8') as file:
            data = yaml.safe_load(file)

        shelves = data.get('shelves', {})
        home = data.get('home')
        if not shelves or home is None:
            raise RuntimeError(f'No shelves/home goals found in {path}')

        return shelves, home

    def make_pose(self, goal):
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()

        if '_pose' in goal:
            pose.pose = goal['_pose']
            return pose

        pose.pose.position.x = float(goal['x'])
        pose.pose.position.y = float(goal['y'])
        pose.pose.position.z = 0.0

        quat = yaw_to_quaternion(float(goal.get('yaw', 0.0)))
        pose.pose.orientation.z = quat['z']
        pose.pose.orientation.w = quat['w']
        return pose

    def initial_pose_callback(self, msg):
        self.home_from_initial_pose = msg.pose.pose
        x = msg.pose.pose.position.x
        y = msg.pose.pose.position.y
        self.get_logger().info(f'Updated GUI home pose from RViz initial pose: x={x:.2f}, y={y:.2f}')

    def get_home_goal(self):
        if self.home_from_initial_pose is not None:
            return {
                'label': 'RViz Initial Pose',
                '_pose': self.home_from_initial_pose,
            }
        return self.home

    def spin_once_nonblocking(self):
        if not self.spin_lock.acquire(blocking=False):
            return
        try:
            rclpy.spin_once(self, timeout_sec=0.0)
        finally:
            self.spin_lock.release()

    def send_navigation_goal(self, goal, feedback_cb):
        self.client.wait_for_server(timeout_sec=2.0)
        if not self.client.server_is_ready():
            raise RuntimeError('Nav2 navigate_to_pose action server is not ready')

        action_goal = NavigateToPose.Goal()
        action_goal.pose = self.make_pose(goal)

        with self.spin_lock:
            send_future = self.client.send_goal_async(action_goal)
            rclpy.spin_until_future_complete(self, send_future)
            goal_handle = send_future.result()

        if goal_handle is None or not goal_handle.accepted:
            raise RuntimeError('Navigation goal was rejected by Nav2')

        self.active_goal_handle = goal_handle
        result_future = goal_handle.get_result_async()

        while rclpy.ok() and not result_future.done():
            feedback_cb()
            with self.spin_lock:
                rclpy.spin_once(self, timeout_sec=0.1)

        result = result_future.result()
        self.active_goal_handle = None
        return result.status == GoalStatus.STATUS_SUCCEEDED


class ShelfGui:
    def __init__(self, node):
        self.node = node
        self.busy = False

        self.root = tk.Tk()
        self.root.title('Warehouse Shelf Picker')
        self.root.geometry('520x430')
        self.root.minsize(480, 390)

        self.status_var = tk.StringVar(value='Set the 2D initial pose in RViz, then choose a shelf.')
        self.detail_var = tk.StringVar(value='Waiting for shelf selection.')

        self.build_ui()
        self.poll_ros()

    def build_ui(self):
        main = ttk.Frame(self.root, padding=16)
        main.pack(fill=tk.BOTH, expand=True)

        title = ttk.Label(main, text='Electronic Warehouse Picker', font=('Sans', 16, 'bold'))
        title.pack(anchor=tk.W)

        status = ttk.Label(main, textvariable=self.status_var, wraplength=460, font=('Sans', 11))
        status.pack(anchor=tk.W, pady=(10, 4))

        detail = ttk.Label(main, textvariable=self.detail_var, wraplength=460)
        detail.pack(anchor=tk.W, pady=(0, 12))

        button_frame = ttk.Frame(main)
        button_frame.pack(fill=tk.BOTH, expand=True)

        for index, (key, goal) in enumerate(self.node.shelves.items()):
            row = index // 2
            col = index % 2
            label = goal.get('label', key.replace('_', ' ').title())
            button = ttk.Button(
                button_frame,
                text=label,
                command=lambda shelf_key=key: self.start_shelf_task(shelf_key)
            )
            button.grid(row=row, column=col, sticky='nsew', padx=6, pady=6)

        for col in range(2):
            button_frame.columnconfigure(col, weight=1)
        for row in range(3):
            button_frame.rowconfigure(row, weight=1)

        self.progress = ttk.Progressbar(main, mode='indeterminate')
        self.progress.pack(fill=tk.X, pady=(12, 0))

        home_label = self.node.home.get('label', 'Home Position')
        ttk.Label(
            main,
            text=f'Home: {home_label} ({self.node.home["x"]}, {self.node.home["y"]})',
            foreground='#555555'
        ).pack(anchor=tk.W, pady=(10, 0))

    def set_status(self, message, detail=None):
        self.root.after(0, lambda: self.status_var.set(message))
        if detail is not None:
            self.root.after(0, lambda: self.detail_var.set(detail))

    def set_busy(self, busy):
        self.busy = busy
        if busy:
            self.root.after(0, self.progress.start)
        else:
            self.root.after(0, self.progress.stop)

    def poll_ros(self):
        if not self.busy:
            self.node.spin_once_nonblocking()
        self.root.after(100, self.poll_ros)

    def start_shelf_task(self, shelf_key):
        if self.busy:
            messagebox.showinfo('Navigation active', 'Robot is already working on a shelf task.')
            return

        thread = threading.Thread(target=self.run_shelf_task, args=(shelf_key,), daemon=True)
        thread.start()

    def run_shelf_task(self, shelf_key):
        self.set_busy(True)
        shelf = self.node.shelves[shelf_key]
        label = shelf.get('label', shelf_key.replace('_', ' ').title())

        try:
            self.set_status(
                f'On my way to {label}',
                'Sending shelf goal to Nav2.'
            )
            reached_shelf = self.node.send_navigation_goal(
                shelf,
                lambda: None
            )

            if not reached_shelf:
                self.set_status(f'Could not reach {label}', 'Nav2 reported the shelf goal failed.')
                return

            self.set_status(f'Reached {label}. Collecting the component', 'Pickup in progress.')
            time.sleep(2.0)
            self.set_status('Successfully picked the component', 'Returning to home position.')
            time.sleep(0.7)

            home_goal = self.node.get_home_goal()
            home_label = home_goal.get('label', 'Home Position')
            self.set_status('Returning to home position', f'Navigating to {home_label}.')
            reached_home = self.node.send_navigation_goal(
                home_goal,
                lambda: None
            )

            if reached_home:
                self.set_status('Reached home position', f'Task complete for {label}.')
            else:
                self.set_status('Could not reach home position', 'Nav2 reported the home goal failed.')

        except Exception as exc:
            self.node.get_logger().error(str(exc))
            self.set_status('Navigation could not start', str(exc))
        finally:
            self.set_busy(False)

    def run(self):
        self.root.mainloop()


def main():
    rclpy.init()
    node = ShelfNavigator()

    try:
        gui = ShelfGui(node)
        gui.run()
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
