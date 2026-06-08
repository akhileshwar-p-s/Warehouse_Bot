import os
from launch import LaunchDescription
from launch.actions import EmitEvent, IncludeLaunchDescription, LogInfo, RegisterEventHandler, TimerAction
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.events import matches_action
from launch.substitutions import Command
from launch_ros.actions import LifecycleNode, Node
from launch_ros.event_handlers import OnStateTransition
from launch_ros.events.lifecycle import ChangeState
from launch_ros.parameter_descriptions import ParameterValue
from ament_index_python.packages import get_package_share_directory
from lifecycle_msgs.msg import Transition

def generate_launch_description():

    pkg_share = get_package_share_directory('warehouse_pkg')
    pkg_ros_gz_sim = get_package_share_directory('ros_gz_sim')

    world_file = os.path.join(pkg_share, 'worlds', 'custom_world.world')
    urdf_file = os.path.join(pkg_share, 'urdf', 'warehouse_bot.urdf.xacro')
    rviz_config = os.path.join(pkg_share, 'rviz', 'slam.rviz')
    slam_params = os.path.join(pkg_share, 'config', 'mapper_params_online_async.yaml')
    bridge_config = os.path.join(pkg_share, 'config', 'gz_bridge.yaml')

    robot_description_content = ParameterValue(
        Command(['xacro ', urdf_file]),
        value_type=str
    )

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
        parameters=[{
            'robot_description': robot_description_content,
            'use_sim_time': True
        }]
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

    slam_toolbox = LifecycleNode(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        namespace='',
        parameters=[
            slam_params,
            {
                'use_lifecycle_manager': False,
                'use_sim_time': True
            }
        ]
    )

    configure_slam_toolbox = EmitEvent(
        event=ChangeState(
            lifecycle_node_matcher=matches_action(slam_toolbox),
            transition_id=Transition.TRANSITION_CONFIGURE
        )
    )

    activate_slam_toolbox = RegisterEventHandler(
        OnStateTransition(
            target_lifecycle_node=slam_toolbox,
            start_state='configuring',
            goal_state='inactive',
            entities=[
                LogInfo(msg='[LifecycleLaunch] Slam Toolbox node is activating.'),
                EmitEvent(
                    event=ChangeState(
                        lifecycle_node_matcher=matches_action(slam_toolbox),
                        transition_id=Transition.TRANSITION_ACTIVATE
                    )
                )
            ]
        )
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        name='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': True}]
    )

    return LaunchDescription([
        robot_state_publisher,
        gz_sim,
        spawn_entity,
        gz_bridge,
        TimerAction(
            period=3.0,
            actions=[
                slam_toolbox,
                activate_slam_toolbox,
                configure_slam_toolbox
            ]
        ),
        TimerAction(
            period=4.0,
            actions=[rviz]
        ),
    ])
