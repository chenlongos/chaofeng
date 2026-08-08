# 第五周（2026-08-03 ~ 2026-08-07）

---

## 总结：

1. SG2002 上完成语音识别：不可行（×）

   SG2002 侧已经验证过轻量关键词识别路线，但要做完整语音识别转指令，算力、音频前端和模型部署成本都不合适，因此不作为当前主线。

2. RK3588 上完成语音识别转指令：已验证

   当前已经能在 RK3588 上跑通语音识别链路。实际效果是，把录音切成约 2s 一段后，识别结果已经可以直接做关键词匹配，转换成“前进、后退、左转、右转”等控制指令。

   后续机器人控制部分与我无关，只需要把这一路识别输出对接给控制同学即可。

   DEMO：把控制部分对接完就有了，与我没关系。

3. Ascend 310B 上语音识别转指令：SD 卡里已有流程基础，待端到端验证

   SD 卡里已经有两部分：一部分是 SenseVoice OM 模型推理，另一部分是开发板录音样例。也就是说“录音”和“模型推理”都已经有基础，下一步要把录音、特征处理、模型推理、文本解码和关键词转指令串成完整链路，并在 310B 板端验证。

4. 本周文档已重新精简

   把这周的文档总结去掉了老板看不懂的专业术语，只保留结论、现状和下一步。

   鉴于老板嫌弃之前写的文档太长了，且老板日理万机，无暇顾及，故精简至此。

## 下一步

1. 验证 Ascend 310B 上录音到指令的端到端链路，并与相关人员对接语音控制。
2. 考虑到 SmolVLA 可能已经训练完成，尝试在 Ascend 310B 上进行推理。

## 细节（老板不看的）

### SG2002 结论

SG2002 上之前验证过关键词识别（KWS）方向，包括中文方向命令、DS-CNN、小模型导出和板端推理。该路线适合做固定短词检测，但不适合直接承担完整 SenseVoice 这类语音识别任务。

主要原因：

1. 完整语音识别模型本体远重于 KWS，小板端部署收益不高。
2. 音频前端、VAD、模型推理、文本后处理都需要稳定常驻，SG2002 上工程成本偏高。
3. 如果目标只是“语音转控制指令”，RK3588 和 Ascend 310B 都更合适。

因此 SG2002 不再作为完整语音识别主线。

### RK3588 语音识别转指令

RK3588 上使用 SenseVoice RKNN 模型完成验证。当前已经完成：

1. 下载并部署 SenseVoice RKNN 模型到 RK3588。
2. 安装并验证 RKNN Runtime、ONNX Runtime、特征提取和分词依赖。
3. 跑通离线音频识别，40s 左右样例音频可以正常输出中文文本。
4. 增加边录音边识别脚本，使用 `arecord` 采集 16kHz 单声道音频。
5. 定位并修复 ES8388 录音输入问题：真实麦克风输入在 Line2，而不是默认 Line1。
6. 验证录音切分后可以输出短句结果，后续可直接做关键词匹配转控制指令。

目前可用脚本在 RK3588 板端：

```bash
cd ~/Sensevoice-RK3588
./setup_mic_es8388.sh 3
python3 ./live_record_asr.py --alsa-device plughw:3,0 --chunk-seconds 2 --language auto --use-itn
```

其中 `chunk-seconds=2` 时，输出粒度更接近控制指令，可直接映射：

```text
前进 -> forward
后退 -> back
左转 -> left
右转 -> right
停止 -> stop
```

后续只需要把识别文本交给控制模块做关键词匹配和动作下发。

### Ascend 310B 语音识别转指令

SD 卡里实际存在两类 310B 相关内容：

1. SenseVoice OM 模型推理基准：

   ```text
   /home/HwHiAiUser/voice-robot-bench/
   ```

2. 录音/播音样例：

   ```text
   /opt/opi_test/USBAudio/
   /opt/opi_test/audio/record.sh
   ```

`voice-robot-bench` 中已有：

```text
benchmark_ascend_om.py
sensevoice_t100.om
speech.bin
speech_lengths.bin
language.bin
textnorm.bin
```

其中 `benchmark_ascend_om.py` 已经完成 310B 上的 OM 模型加载、输入构造和 ACL 推理：

1. 加载 SenseVoice OM 模型。
2. 准备 `speech`、`speech_lengths`、`language`、`textnorm` 输入。
3. 通过 PyACL 调用 `acl.mdl.execute` 执行模型。
4. 输出推理耗时和 NPU 内存占用。

录音侧已有两条参考：

1. `/opt/opi_test/audio/record.sh` 使用 `arecord` 录制 48kHz PCM，并用 `aplay` 回放。
2. `/opt/opi_test/USBAudio/main.c` 使用 FFmpeg/ALSA 从 USB 麦克风录音，生成 `audio.pcm`。

因此 310B 上的端到端链路不是从零开始，而是需要把 SD 卡中已有的两段流程接起来：

```text
麦克风录音
  -> 音频重采样/切片
  -> fbank/LFR/CMVN 特征
  -> speech / speech_lengths / language / textnorm 输入
  -> sensevoice_t100.om
  -> 文本解码
  -> 关键词转控制指令
```

当前已有模型本体推理基线：SenseVoiceSmall FP16 OM 在 310B 上单次推理约 33ms，模型本身不是瓶颈。下一步重点不是重新做模型，而是补齐录音到模型输入、模型输出到文本、文本到指令这三段胶水逻辑，并做板端真实麦克风验证。

