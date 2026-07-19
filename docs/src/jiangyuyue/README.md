# 蒋玉月 · StarryOS SG2002 TPU 推理

负责 SG2002 (LicheeRV Nano) 平台上的 StarryOS 内核移植和 YOLO TPU/NPU 硬件推理加速。

- 内核：StarryOS (Rust 宏内核, RISC-V 64)
- 平台：算能 SG2002 (0.5 TOPS NPU)
- 目标：四语言 (C/C++/Python/Rust) TPU 推理 < 50ms
