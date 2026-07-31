## week4 工作周报

## 1. SO101 网球放置数据集采集与整理

本周主要完成了 SO101 主从臂数据采集环境的重新整理，并基于真实机械臂采集了网球抓取放置任务数据。任务目标是让 follower arm 根据 leader arm 的遥操作轨迹，完成“捡起网球并放到目标区域”的操作。

本周采集任务英文指令统一为：

```text
Pick up the tennis ball and place it in the target area.
```

当前数据集已整理为 LeRobot v3.0 格式，并上传到 Hugging Face，并做了详细的当前的内容的可复现工作整理 **目标是该仓库是可被别人用相同的硬件直接复现的**：

```text
https://huggingface.co/datasets/vvzc/ChenLong_Embodied_Intelligence_Dataset
```

### 1.1 当前数据集规模

| 项目 | 当前数值 |
| --- | --- |
| 数据格式 | LeRobot v3.0 |
| 机器人类型 | `so_follower` |
| 总 episodes | 48 |
| 总帧数 | 21187 |
| 任务数量 | 1 |
| 采集帧率 | 30 FPS |
| 图像分辨率 | 640 x 480 |
| 摄像头数量 | 2 |
| 动作维度 | 6 |
| 状态维度 | 6 |
| 数据划分 | `train: 0:48` |

数据集包含两个视觉输入：

```text
observation.images.overhead
observation.images.wrist
```

其中 `overhead` 是俯视摄像头，用于观察桌面整体布局、网球位置和目标区域；`wrist` 是手腕摄像头，用于观察夹爪附近的抓取细节。

### 1.2 数据字段

当前数据集主要字段如下：

| 字段 | 类型 | 形状 | 含义 |
| --- | --- | --- | --- |
| `action` | `float32` | `[6]` | 主臂遥操作产生的动作目标 |
| `observation.state` | `float32` | `[6]` | 从臂当前关节状态 |
| `observation.images.overhead` | `video` | `[480, 640, 3]` | 俯视摄像头视频 |
| `observation.images.wrist` | `video` | `[480, 640, 3]` | 手腕摄像头视频 |
| `timestamp` | `float32` | `[1]` | 当前帧时间戳 |
| `frame_index` | `int64` | `[1]` | episode 内帧编号 |
| `episode_index` | `int64` | `[1]` | episode 编号 |
| `index` | `int64` | `[1]` | 全局帧编号 |
| `task_index` | `int64` | `[1]` | 任务编号 |

`action` 和 `observation.state` 的 6 个关节顺序为：

```text
shoulder_pan.pos
shoulder_lift.pos
elbow_flex.pos
wrist_flex.pos
wrist_roll.pos
gripper.pos
```

### 1.3 采集硬件与端口

本周使用一台原生 Ubuntu 电脑重新配置采集环境，避免之前 WSL2 下 USB 摄像头转发不稳定的问题。

当前硬件配置：

| 设备 | 作用 | 当前端口 |
| --- | --- | --- |
| SO101 follower arm | 从臂，实际执行动作 | `/dev/ttyACM0` |
| SO101 leader arm | 主臂，人工遥操作输入 | `/dev/ttyACM1` |
| overhead camera | 俯视摄像头 | `/dev/video4` |
| wrist camera | 手腕摄像头 | `/dev/video2` |

主从臂电机环境检查结果：

```text
motor ids: 1, 2, 3, 4, 5, 6
baud rate: 1000000
model: 777
```

说明换臂后电机 ID、波特率和 SO101 默认配置一致，不需要重新写电机 ID，只需要重新完成机械臂校准。

### 1.4 采集参数与复现命令

本周最终固定的数据采集参数为：

| 参数 | 数值 |
| --- | --- |
| 每次采集条数 | 10 episodes |
| 单条采集时间 | 15 秒 |
| 每条 reset 时间 | 10 秒 |
| 采集 FPS | 30 |
| 视频分辨率 | 640 x 480 |
| 视频编码 | AV1 |
| 是否追加数据集 | `--resume=true` |

每次追加采集 10 条数据时使用的脚本为：

```bash
~/so101_record_tennis_append10.sh
```

脚本内部核心命令如下：

```bash
lerobot-record \
  --robot.type=so101_follower \
  --robot.port="/dev/ttyACM0" \
  --robot.id="so101_follower_sakura" \
  --robot.cameras="{overhead: {type: opencv, index_or_path: /dev/video4, width: 640, height: 480, fps: 30}, wrist: {type: opencv, index_or_path: /dev/video2, width: 640, height: 480, fps: 30}}" \
  --teleop.type=so101_leader \
  --teleop.port="/dev/ttyACM1" \
  --teleop.id="so101_leader_sakura" \
  --display_data=true \
  --dataset.root="/home/sakura/lerobot_data" \
  --dataset.repo_id="local/so101_tennis" \
  --dataset.single_task="Pick up the tennis ball and place it in the target area." \
  --dataset.fps=30 \
  --dataset.episode_time_s=15 \
  --dataset.reset_time_s=10 \
  --dataset.num_episodes=10 \
  --dataset.video=true \
  --dataset.push_to_hub=false \
  --dataset.streaming_encoding=true \
  --dataset.encoder_threads=2 \
  --resume=true
```

其中 `--resume=true` 是关键参数，用于在已有数据集后继续追加采集，避免覆盖已有 episode。

## 2. 数据集发布与说明文档完善

本周还整理并上传了数据集说明文档。README 中补充了硬件配置、端口映射、采集参数、字段结构、读取方式和复现命令，使其他人拿到相同 SO101 主从臂和双摄像头后，可以按照文档重新搭建采集流程。

README 中重点说明了：

- follower arm 和 leader arm 的作用区分。
- 双摄像头字段命名必须固定为 `overhead` 和 `wrist`。
- episode 采集时间为 15 秒，reset 时间为 10 秒。
- 数据集字段需要保持 `observation.images.overhead`、`observation.images.wrist`、`observation.state` 和 `action` 一致。
- 追加采集时必须使用 `--resume=true`。

这一步的意义是把能在本机跑通”的流程转化为别人可以复现的数据集交付材料。

## 3. SmolVLA 模型训练

在数据集采集完成后，本周使用当前 SO101 网球放置数据集对 SmolVLA 进行了微调训练。训练在 WSL2 的 `Ubuntu-24.04` 中完成，使用 `lerobot` conda 环境。

训练完成后的模型位置为：

```text
/home/czw1/lerobot/outputs/train/smolvla_chenlong_2000steps_run1/checkpoints/002000/pretrained_model
```

训练日志位置为：

```text
/home/czw1/lerobot/training_logs/smolvla_chenlong_2000steps_run1.log
```

### 3.1 训练结果

| 项目 | 结果 |
| --- | --- |
| policy 类型 | `smolvla` |
| 训练步数 | `2000/2000 steps` |
| 最终 loss | `0.116` |
| 输入视觉特征 | `observation.images.overhead`, `observation.images.wrist` |
| 输入状态特征 | `observation.state` |
| 输出特征 | `action` |
| 最终模型文件 | `model.safetensors` |
| 模型文件大小 | 约 907 MB |
| 训练总输出目录大小 | 约 5.0 GB |
| 训练进程状态 | 已结束，无残留训练进程 |

这次训练说明当前自采 LeRobotDataset 已经能够被 SmolVLA 正常识别和加载，双摄像头图像、机器人状态和动作输出字段也已经和模型输入输出对齐。

### 3.2 本次训练的意义

本次训练完成后，项目从“采集数据”推进到了“用自采数据微调 VLA 模型”的阶段。相比直接使用社区公开 SO101 模型，本次训练使用的是当前实验环境中的真实摄像头视角、真实桌面背景、真实网球和目标区域，因此模型更贴近实际部署环境。

本次训练验证了以下内容：

- 自采数据集的 schema 可以被 LeRobot 训练流程读取。
- 双摄像头输入可以进入 SmolVLA 模型。
- `observation.state` 与 `action` 字段维度正确。
- 训练可以完整跑到 2000 steps。
- 输出 checkpoint 可以保存为可复用的 `pretrained_model` 目录。

## 

下周计划重点从训练完成转向模型验证和数据质量提升：

1. 使用训练得到的 SmolVLA checkpoint 做真实机械臂 rollout 测试。
2. 观察模型是否能够根据 `Pick up the tennis ball and place it in the target area.` 完成闭环动作。
3. 根据失败案例补采数据，例如抓取偏差、放置偏差、夹爪闭合不稳定等情况。
4. 尝试扩大数据集规模，从 48 条增加到 100 条以上。
5. 对比不同训练步数下的 checkpoint 表现，例如 2000 steps、5000 steps 和更长训练。
6. 继续完善标准化文档，让其他同学可以按同样流程复现 SO101 数据采集、训练和部署。
