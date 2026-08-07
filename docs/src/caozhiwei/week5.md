# week5 工作周报

## 1. Hugging Face 数据与模型仓库整理

本周首先完成了辰龙机器人实习数据与模型仓库的集中整理工作，将后续要使用的数据集、模型权重、训练结果和说明文档统一放入 Hugging Face 仓库中管理：

```text
https://huggingface.co/datasets/vvzc/ChenLong_Embodied_Intelligence_Dataset
```

本次整理的主要工作量包括：

- 将具身智能采集数据整理到 `embodied_dataset/` 目录，保留 LeRobot v3.0 的 `data/`、`meta/`、`videos/` 结构。
- 将 YOLO 目标检测模型和训练评估结果整理到 `yolo_dataset/` 目录，当前包含蓝色桶检测模型 `blue_bucket_yolov8/`。
- 为仓库配置 Git LFS，确保 `.parquet`、`.mp4`、`.pt`、`.png` 等大文件能够正常上传和同步。
- 完善主 README，说明仓库用途、当前目录结构，以及后续新增数据集和模型时需要保留的关键信息。
- 完善子目录 README，补充数据字段、采集格式、模型文件、训练参数和复现说明，方便其他同学按照同一标准继续采集和维护。

通过这部分工作，仓库从单纯的数据存放位置整理成了可长期维护的数据与模型交付仓库。后续新增任务、采集批次或模型版本时，可以继续按当前结构补充。

## 2. 继续采集 50 条具身数据并放入仓库

本周继续围绕 SO101 主从机械臂的网球抓取放置任务进行数据采集，在已有数据基础上追加采集了 50 条 episode，并整理后放入 Hugging Face 仓库。

任务文本保持不变：

```text
Pick up the tennis ball and place it in the target area.
```

采集标准继续沿用当前 LeRobot 数据格式：

- 机器人：SO101 follower arm
- 遥操作设备：SO101 leader arm
- 相机视角：overhead camera 和 wrist camera
- 数据格式：LeRobot v3.0
- 图像数据：MP4 视频
- 状态与动作数据：Parquet 文件
- 主要字段：`observation.images.overhead`、`observation.images.wrist`、`observation.state`、`action`

追加采集时重点保证：

- 新采集 episode 不覆盖已有数据。
- episode 编号、frame 编号和全局 index 保持连续。
- 视频与动作数据能够对应。
- 采集完成后更新仓库说明，确保别人能理解当前数据规模和目录组织方式。

这 50 条数据的补充使当前数据集规模进一步扩大，也为后续 SmolVLA 或其他 VLA 模型训练提供了更多真实操作样本。

## 3. SmolVLA 模型微调、结果验证与本地推理准备

本周在 WSL2 Ubuntu-24.04 的 LeRobot 环境中，基于已经整理好的 SO101 网球抓取放置数据集，对 SmolVLA 模型进行了本地微调，并完成了模型文件、离线推理和实机推理环境的初步验证。

### 3.1 训练环境

训练使用本机 WSL2 中的 `Ubuntu-24.04` 发行版，主要环境如下：

- Conda 环境：`lerobot`
- Python 版本：`3.12.13`
- LeRobot 版本：`0.5.2`
- PyTorch 版本：`2.11.0+cu128`
- GPU：NVIDIA GeForce RTX 5060 Laptop GPU
- CUDA：可用

训练前首先确认了 LeRobot、PyTorch、CUDA、GPU 和数据集路径都能正常访问，避免由于环境或路径问题导致训练中断。

### 3.2 训练数据

训练数据使用本地 LeRobot v3.0 格式数据集：

```text
/home/czw1/chenlong-val-data
```

数据集对应 Hugging Face 仓库：

```text
vvzc/ChenLong_Embodied_Intelligence_Dataset
```

数据集基本信息如下：

- 任务文本：`Pick up the tennis ball and place it in the target area.`
- episode 数量：50
- 总帧数：21187
- 采集帧率：30 FPS
- 图像视角：`observation.images.overhead`、`observation.images.wrist`
- 状态维度：6
- 动作维度：6
- 机器人类型：`so_follower`

训练前用 `LeRobotDataset` 成功加载该数据集，确认数据集长度、FPS、图像字段、状态字段和动作字段都能被当前 LeRobot 版本识别。

### 3.3 训练方式与关键参数

本次训练采用 `lerobot/smolvla_base` 作为预训练基座模型进行微调。由于 `smolvla_base` 默认期望的相机字段是 `camera1/camera2/camera3`，而当前数据集使用的是 `overhead/wrist` 两路相机，因此训练时显式设置：

```text
--policy.input_features=null
--policy.output_features=null
```

让 LeRobot 从数据集自动推断输入输出特征，避免相机字段不一致导致训练失败。

最终训练命令的核心参数如下：

```bash
lerobot-train \
  --policy.path=lerobot/smolvla_base \
  --policy.input_features=null \
  --policy.output_features=null \
  --dataset.repo_id=vvzc/ChenLong_Embodied_Intelligence_Dataset \
  --dataset.root=/home/czw1/chenlong-val-data \
  --batch_size=8 \
  --steps=2000 \
  --save_freq=500 \
  --log_freq=50 \
  --num_workers=0 \
  --output_dir=/home/czw1/lerobot/outputs/train/smolvla_chenlong_2000steps_run1 \
  --job_name=smolvla_chenlong_2000steps \
  --policy.device=cuda \
  --policy.use_amp=true \
  --policy.push_to_hub=false \
  --wandb.enable=false
```

训练前先分别进行了 `batch_size=1` 和 `batch_size=8` 的 2-step smoke test，确认模型权重加载、视频解码、CUDA 训练、loss 计算和 checkpoint 写入都能正常工作。`batch_size=8` 时显存占用约 2.95 GB，因此正式训练采用 batch size 8。

### 3.4 训练结果

正式训练共进行 2000 steps，训练过程正常结束，最终日志显示：

```text
step:2K smpl:16K ep:36 epch:0.76 loss:0.116 grdn:1.993 lr:2.5e-06 mem_gb:2.96
End of training
```

训练过程中 loss 从早期的约 0.47 逐步下降到 0.11 左右，说明模型已经在当前数据集上完成了有效拟合。训练期间保存了 4 个 checkpoint：

```text
/home/czw1/lerobot/outputs/train/smolvla_chenlong_2000steps_run1/checkpoints/000500
/home/czw1/lerobot/outputs/train/smolvla_chenlong_2000steps_run1/checkpoints/001000
/home/czw1/lerobot/outputs/train/smolvla_chenlong_2000steps_run1/checkpoints/001500
/home/czw1/lerobot/outputs/train/smolvla_chenlong_2000steps_run1/checkpoints/002000
```

最终模型路径为：

```text
/home/czw1/lerobot/outputs/train/smolvla_chenlong_2000steps_run1/checkpoints/002000/pretrained_model
```

最终模型目录包含：

- `config.json`
- `model.safetensors`
- `train_config.json`
- `policy_preprocessor.json`
- `policy_postprocessor.json`
- normalizer / unnormalizer processor 权重文件

其中 `model.safetensors` **约 865 MB**，整个训练输出目录约 5.0 GB。最终模型配置中确认输入特征已经正确适配为：

```text
observation.images.overhead
observation.images.wrist
observation.state
```

输出特征为：

```text
action
```

### 3.5 推理验证与实机准备

训练完成后，先进行了不控制机械臂的离线推理 smoke test。测试从本地数据集中读取一帧样本，加载最终 checkpoint，并在 CUDA 上调用 SmolVLA 输出动作。测试结果表明模型可以正常完成前向推理，输出形状为：

```text
action_shape=(1, 6)
```

随后对实机推理环境进行了准备和检查：

- 将之前 Ubuntu 中同一台 SO101 follower 从臂的校准文件复制到本机 LeRobot 默认校准目录。
- 通过 `usbipd` 将 follower 串口、overhead 相机和 wrist 相机挂载到 WSL2。
- 在 WSL 中确认 `/dev/serial/by-id/` 和 `/dev/v4l/by-id/` 稳定路径可用。
- 使用 OpenCV 分别读取 overhead 和 wrist 相机画面，均能获取 640 x 480 图像。
- 串口可以正常打开，当前用户也具备 `dialout` 和 `video` 组权限。

为后续复现实机推理，整理了以下辅助脚本：

```text
tools/smolvla_offline_infer_smoke.py
tools/run_chenlong_smolvla_rollout.py
tools/attach_smolvla_inference_devices.ps1
```

其中 `run_chenlong_smolvla_rollout.py` 默认使用本次训练出的本地 SmolVLA checkpoint，并使用 `overhead/wrist` 两路相机字段，与训练数据保持一致。

### 3.6 当前问题与后续计划总结

​	当前模型已经完成 2000-step 本地微调和离线推理验证，模型大小为865 MB，但是当前模型的表现效果不够优秀，可能的原因是数据采集数量不够准备加大数据量重新再往后训练v2版本的











