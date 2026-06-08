import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('warehouse_pkg')

    goal_file = LaunchConfiguration('goal_file')
    use_sim_time = LaunchConfiguration('use_sim_time')

    declare_goal_file = DeclareLaunchArgument(
        'goal_file',
        default_value=os.path.join(pkg_share, 'config', 'shelf_goals.yaml'),
        description='YAML file containing shelf and home navigation poses'
    )

    declare_use_sim_time = DeclareLaunchArgument(
        'use_sim_time',
        default_value='true',
        description='Use Gazebo simulation time'
    )

    shelf_gui = Node(
        package='warehouse_pkg',
        executable='shelf_gui.py',
        name='shelf_gui',
        output='screen',
        parameters=[{
            'goal_file': goal_file,
            'use_sim_time': use_sim_time,
        }]
    )

    return LaunchDescription([
        declare_goal_file,
        declare_use_sim_time,
        shelf_gui,
    ])
