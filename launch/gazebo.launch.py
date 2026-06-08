import os
from launch import LaunchDescription
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():

    pkg_share = get_package_share_directory('warehouse_pkg')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    world_file = os.path.join(pkg_share, 'worlds', 'custom_world.world')
    bridge_config = os.path.join(pkg_share, 'config', 'gz_bridge.yaml')

    robot_description_content = ParameterValue(Command([
        'xacro ',
        os.path.join(pkg_share, 'urdf', 'warehouse_bot.urdf.xacro')
    ]), value_type=str)

    robot_description = {'robot_description': robot_description_content}

    gz_sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(pkg_ros_gz_sim, 'launch', 'gz_sim.launch.py')
        ),
        launch_arguments={'gz_args': ['-r ', world_file]}.items()
    )

    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[robot_description, {'use_sim_time': True}]
    )

    spawn_entity = Node(
        package='ros_gz_sim',
        executable='create',
        arguments=[
            '-topic', 'robot_description',
            '-name', 'warehouse_bot',
            '-x', '0.0',
            '-y', '-7.5',
            '-z', '0.0'
        ],
        output='screen'
    )

    gz_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        parameters=[{'config_file': bridge_config}],
        output='screen'
    )

    return LaunchDescription([
        robot_state_publisher,
        gz_sim,
        spawn_entity,
        gz_bridge,
    ])
