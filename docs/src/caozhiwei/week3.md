## week3

## 1.标准化部分调研以及模型数据集通用方法调研

本周补充调研了标准化方案。要求标准化的核心目标是：如果别人购买同样的 SO101 主从臂、同样的双摄像头和类似的桌面任务环境，可以尽量复用本项目的数据采集、训练和部署流程，而不是每个人都从零开始调设备、写命令、排查路径。

当前标准化计划分为硬件标准化、软件环境标准化、数据采集标准化、数据集格式标准化和模型训练标准化五部分。

### 1.1 硬件标准化

硬件标准化的目标是固定机器人和传感器组合，减少由于设备差异导致的模型不可复用问题。

| 标准化项目 | 当前约定 | 作用 |
| --- | --- | --- |
| 机械臂 | SO101 leader + SO101 follower | 保证动作空间、关节数量和控制方式一致 |
| 摄像头数量 | 2 路 | 保证视觉输入结构一致 |
| 摄像头视角 | overhead + wrist | 保证训练和部署时的视觉分布一致 |
| 任务物体 | tennis ball | 固定第一阶段任务对象 |
| 任务目标 | target area | 固定放置区域定义 |

后续如果其他同学购买同样硬件，只需要按照同样的机械臂型号、摄像头数量、摄像头位置和任务场景搭建，即可复用本项目的数据采集脚本和训练配置。

### 1.2 软件环境标准化

软件标准化主要解决“同一套命令在不同电脑上跑不起来”的问题。当前项目环境约定如下：

```text
 Ubuntu 22.04
Python 环境：conda env lerobot
机器人框架：LeRobot 0.5.2
采集命令：lerobot-record
训练命令：lerobot-train
数据格式：LeRobotDataset
```

需要标准化保存的内容包括：

- conda 环境名称和依赖版本。
- LeRobot 版本。
- 数据采集命令模板。
- 训练命令模板。

### 1.3 数据采集标准化

数据采集标准化的目标是让不同人采集的数据具有相同结构，后续可以合并训练。

当前任务文本统一为：

```text
Pick up the tennis ball and place it in the target area.
```

当前 camera key 统一为：

```text
overhead
wrist
```

这两个名称后续需要固定，不能一批数据叫 `top`，另一批叫 `front`，否则训练时模型输入字段不一致，会影响数据集合并和模型加载。

建议后续采集标准如下：

| 项目 | 建议标准 |
| --- | --- |
| episode 时长 | 30s |
| reset 时长 | 10s |
| 数据集 FPS | 优先 15fps，稳定后再尝试 30fps |
| 任务文本 | 固定英文任务描述 |
| 数据目录 | 使用时间戳，避免覆盖 |
| 失败样本 | 单独记录并剔除 |
| 摄像头 key | 固定为 `overhead` 和 `wrist` |

标准化采集的意义是：后续如果其他人用同样硬件采集同一任务，可以把数据直接合并到同一个 LeRobotDataset 训练流程中，而不需要重新写数据转换代码。

### 1.4 数据集格式通用性调研

LeRobot 的核心优势是数据集格式相对统一。通过 `lerobot-record` 采集的数据会保存为 LeRobotDataset，其中包括：

- 多路图像 observation。
- 机器人 state。
- 机器人 action。
- episode 信息。
- 任务文本 `task`。
- 数据集 meta 信息。

只要模型支持 LeRobotDataset，就可以在同一套数据上切换不同 policy 做实验。也就是说，本项目采集的数据不只服务于 SmolVLA，也可以用于对比其他 imitation learning 或 VLA 模型。

### 1.5 标准化交付计划

为了让其他人购买同样硬件后可以复用，本项目后续计划整理一套标准化交付材料：

```text
1. 硬件清单
2. 摄像头安装位置示意
3. LeRobot 环境安装说明
4. USB attach 脚本
5. 主从臂校准步骤
6. 双摄像头采集命令模板
7. LeRobotDataset 检查脚本
8. SmolVLA / ACT / Diffusion 训练命令模板
9. rollout 测试步骤
10. 常见错误排查表
```

标准化的最终目标是形成一套可以复制的 SO101 双摄像头 VLA 数据采集和训练流程。



## 2.训练模型部分

模型训练部分当前主要围绕自采 LeRobotDataset 展开。数据采集完成后，同一套数据集可以优先用于以下三类实验：

1. **SmolVLA **

   - 作为主线模型。
   - 使用双摄像头图像、机器人状态和文本任务描述。
   - 目标是训练可执行 “Pick up the tennis ball and place it in the target area.” 的 VLA 策略。

2. **Pi0 **

   - 作为更大模型方向储备。

   - 需要更多算力和更稳定的数据集。
   - 当前不作为第一优先级。

因此当前采集数据时，需要尽量保证数据字段通用：

```text
camera keys: overhead, wrist
task: Pick up the tennis ball and place it in the target area.
robot type: so101_follower
teleop type: so101_leader
fps: 15 或 30，但同一批数据内保持一致
```

这样后续可以在不重新采集数据的情况下，直接切换 `--policy.type=smolvla`、`--policy.type=act` 或 `--policy.type=diffusion` 进行训练对比。

**本周训练的采集数据遇到的硬件问题：**

问题 1：摄像头 FPS 设置失败

采集过程中出现过摄像头帧率设置失败：

```text
OpenCVCamera(...) failed to set fps=15 (actual_fps=30.0)
```

原因是部分 USB 摄像头实际只支持固定的 30fps 模式。即使在 LeRobot 配置中请求 15fps，驱动仍返回 30fps。LeRobot 会严格检查请求帧率和实际帧率是否一致，因此直接报错退出。

处理方式：

- 对实际只能 30fps 的摄像头，在摄像头配置中写 `fps=30`。
- 如果希望数据集帧率更低，可以通过 `--dataset.fps=15` 控制保存频率。
- 不强行把所有摄像头都设置为 15fps。

结论：摄像头采集帧率和数据集保存帧率可以分开考虑。摄像头按硬件支持的模式运行，数据集按训练需要保存。

问题 2：MJPG 坏帧

采集过程中频繁出现：

```text
Corrupt JPEG data: premature end of data segment
```

这是 OpenCV 解码 MJPG 图像流时打印的警告，说明摄像头传来的 JPEG 压缩帧不完整。该问题在 WSL2 + USB 摄像头环境中比较常见，尤其是在双摄像头同时采集时更明显。

原因分析：

- MJPG 本质是连续 JPEG 压缩帧。
- USB 转发过程中如果数据包不完整，OpenCV 会收到不完整 JPEG。
- 双摄像头同时采集会增加 USB 带宽压力。
- WSL2 的 USB 转发稳定性弱于原生 Linux。

处理方式：

- 对不稳定的俯视摄像头，尽量避免使用 MJPG，改用 YUYV。
- 对手腕摄像头保留 MJPG，但降低分辨率到 320x240。
- 降低数据集保存帧率到 15fps。
- 尽量不要让两个摄像头插在同一个 USB Hub 上。

结论：少量 `Corrupt JPEG data` 可以忍受，但如果伴随读帧超时，就必须降低负载或更换摄像头格式。

问题 3：读帧超时

双摄像头采集过程中还出现过更严重的错误：

```text
TimeoutError: OpenCVCamera(...) latest frame is too old
```

该错误会导致 LeRobot 停止录制。它说明某一路摄像头长时间没有提供新帧，超过了 LeRobot 的最大等待时间。

从日志看，主要不稳定的是俯视摄像头：

```text
usb-Sonix_Technology_Co.__Ltd._USB2.0_CAM1...
```

原因分析：

- 俯视摄像头在 MJPG 模式下容易出现坏帧。
- 双摄像头同时 30fps 会使 WSL2 USB 转发压力较大。
- 实时视频编码会进一步增加 CPU 压力。
- 当采集主循环低于目标 FPS 时，图像缓存中的最新帧可能变旧，最终触发 timeout。

处理方式：

```text
俯视摄像头：YUYV，640x480，15fps
手腕摄像头：MJPG，320x240，30fps
数据集保存：15fps
实时编码：关闭
```

结论：由于任务要求必须使用两路摄像头，当前不能简单改成单摄像头采集。较可行的方案是降低双摄像头整体负载，并让俯视摄像头避开不稳定的 MJPG 模式。

问题 4：采集循环低于目标 FPS

日志中多次出现：

```text
Record loop is running slower than the target FPS
```

这说明 LeRobot 的主循环速度低于设定的数据集 FPS，可能导致丢帧或机器人控制不稳定。

原因分析：

- 双摄像头读取耗时较高。
- 图像写盘线程占用 CPU。
- 视频编码占用 CPU。
- WSL2 文件系统和 USB 转发都有额外开销。

处理方式：

- 将 `--dataset.fps` 从 30 降到 15。
- 关闭 `--dataset.streaming_encoding`。
- 减少 `--dataset.num_image_writer_threads_per_camera`。
- 降低手腕摄像头分辨率。
- 采集时关闭不必要的后台程序。

结论：当前WSL2 环境下，双摄像头 30fps 采集不够稳定，硬件适配问题严重

 目前已更换ubuntu原生电脑来重新采集数据
