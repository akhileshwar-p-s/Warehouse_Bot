# 🏭 Warehouse Inventory Robot — ROS 2 Jazzy

A simulated autonomous warehouse robot built with **ROS 2 Jazzy**, **Gazebo Harmonic**, and **Nav2**. The robot navigates a custom warehouse world, visits predefined inventory shelf zones in sequence, and returns to its home position — mimicking a real-world inventory scan cycle.

---

## 📽️ Demo

<img width="1920" height="1080" alt="Screenshot from 2026-06-08 22-49-53" src="https://github.com/user-attachments/assets/789b08fb-feb0-4bc6-89a3-64bc79a8f263" />

<img width="1920" height="1080" alt="Screenshot from 2026-06-08 22-50-14" src="https://github.com/user-attachments/assets/454c96e8-0245-49fa-8be6-ca8775c63ffa" />

<img width="891" height="608" alt="Screenshot from 2026-06-08 22-52-28" src="https://github.com/user-attachments/assets/0fc3cb07-42ec-4118-98e1-02b97ea7de31" />

<img width="848" height="873" alt="Screenshot from 2026-06-08 22-53-12" src="https://github.com/user-attachments/assets/98abd342-82f4-41cb-84fb-f0cf16181c1a" />

---

## 📦 Package Structure

```
Warehouse_Bot/
├── config/          
├── launch/         
├── maps/           
├── rviz/          
├── scripts/         
├── urdf/            
├── worlds/         
├── CMakeLists.txt
└── package.xml
```

---

## 🔧 Dependencies

| Tool | Version |
|---|---|
| ROS 2 | Jazzy |
| Gazebo | Harmonic |
| Nav2 | Jazzy |
| Python | 3.x |
| Ubuntu | 24.04 |

Install Nav2:
```bash
sudo apt install ros-jazzy-navigation2 ros-jazzy-nav2-bringup
```

## 🗺️ Warehouse World

The custom Gazebo world features:

- A rectangular warehouse floor plan
- Shelf rack rows (Zones A–D) placed as static obstacles
- Clear navigation corridors for the robot
- A defined **Home Zone** where the robot starts and returns after each mission cycle

---

## 🤖 Robot Description

The robot is a differential-drive mobile platform with:

- **Chassis** — rectangular body with caster wheel
- **Drive wheels** — two actuated wheels (left/right)
- **LiDAR sensor** — 360° scan for SLAM and obstacle avoidance
- **ros2_control** — hardware interface via `gz_ros2_control/GazeboSimSystem`

---

## 🧭 Navigation Architecture

```
Gazebo Sim
    │
    ├── /scan  (LiDAR)
    ├── /odom  (diff drive)
    └── /tf    (transforms)
          │
        Nav2
          ├── AMCL (localization on saved map)
          ├── Global Planner (NavFn / Smac)
          └── Local Planner (DWB controller)
                │
          inventory_mission.py
          (sends goal poses → Nav2 Action Server)
```

## 📋 Inventory Mission Logic

The `inventory_mission.py` script sends sequential `NavigateToPose` action goals to Nav2:

1. Navigate to **Shelf Zone A**
2. Simulate inventory scan (2-second pause)
3. Navigate to **Shelf Zone B**
4. Simulate inventory scan
5. *(repeat for all zones)*
6. Return to **Home Position**

Zone coordinates are defined as a list of `(x, y, yaw)` tuples inside the script, matched to physical shelf positions in the Gazebo world.

---

## 🐛 Problems Encountered & Solutions

### 1. Robot Not Returning to Home Position

**Problem:** After completing the shelf visits, the robot failed to navigate back to the home position. It either spun in place or the Nav2 goal was rejected immediately.

**Root Cause:** A mismatch between the **home pose saved in the map** and the **robot's actual spawn pose in Gazebo**.

When the map was saved during a SLAM session, the robot happened to be at a different position than `(0, 0, 0)`. Later, the Gazebo world was configured to spawn the robot at `(0, 0, 0)`. This meant AMCL was localizing the robot against a map whose origin frame didn't match the spawn point — so the "home" goal coordinates from the map were incorrect in the Gazebo frame.

**Fix:**
- Opened the saved `.yaml` map file and noted the `origin` field (x, y, yaw).
- Matched the robot's spawn pose in the Gazebo launch file to exactly that origin.
- Alternatively, re-saved the map with the robot explicitly parked at the intended home pose before running `map_saver`.
- After aligning both, AMCL localization was consistent and the home-return goal succeeded reliably.

**Lesson:** Always verify that `map origin == robot spawn pose` in Gazebo. A quick sanity check is to set a `2D Pose Estimate` in RViz after launch and confirm the robot marker overlaps the correct map position before starting a mission.

---

### 2. Incorrect Goal Poses for Each Shelf

**Problem:** The `NavigateToPose` goals sent to Nav2 for each shelf zone were often off-target — the robot would navigate to the correct area but face the wrong direction, or stop short of the rack, making the "inventory scan" simulation unrealistic.

**Root Cause:** Goal poses were initially guessed by eyeballing the Gazebo world, without precisely extracting the shelf coordinates.

**Fix:**
- Drove the robot manually to each shelf using `teleop_twist_keyboard` and recorded the exact pose from `/amcl_pose` topic:
  ```bash
  ros2 topic echo /amcl_pose
  ```
- Used those precise `(x, y, quaternion)` values directly in `inventory_mission.py`.
- For yaw, ensured the robot faces the shelf face (perpendicular to the rack) by computing the correct quaternion using:
  ```python
  from tf_transformations import quaternion_from_euler
  q = quaternion_from_euler(0, 0, yaw_radians)
  ```
- This made the robot stop directly in front of each rack, facing it squarely.

---

### 3. Nav2 Costmap Inflation Blocking Narrow Aisles

**Problem:** The robot refused to enter the aisle between shelf rows — the global planner found no valid path.

**Root Cause:** The inflation radius in `nav2_params.yaml` was set too large, causing the costmap to mark the entire aisle as lethal space.

**Fix:** Reduced `inflation_radius` in the costmap config from `0.55` to `0.30` to match the actual clearance of the warehouse aisles.

---

## 📄 License

This project is submitted as part of the ROS 2 Nano Degree program at **myEquation**.

---

## 👤 Author

**Akhileshwar Pratap Singh**
RGIPT | Electronics Engineering
[GitHub](https://github.com/akhileshwar-p-s)
