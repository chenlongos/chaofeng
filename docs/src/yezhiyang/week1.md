# 第一周

## 本周目标

围绕 Orange Pi AIpro20T 平台，完成 SmolVLA 异步推理链路的前期调研、模型拆解、板端部署验证和 NPU 加速瓶颈分析，为后续实现稳定的异步推理服务和算子级优化打基础。

## 主要工作

1. 梳理 SmolVLA 推理流程，明确视觉输入、语言输入、状态输入和动作输出之间的数据依赖关系。
2. 分析主机端与板端的运行环境，确认 Orange Pi AIpro20T 上昇腾 CANN、ACL Runtime、自定义算子和 benchmark 的基本使用方式。
3. 拆分 SmolVLA 推理链路中的关键子图，围绕视觉编码、语言/动作条件、denoise 循环和 action head 进行导出与板端验证。
4. 搭建 ACL/ACLLN 侧的输入构造、模型运行、结果对齐和耗时统计脚本，用于比较 CPU/PyTorch 参考结果与 NPU 推理结果。
5. 针对 attention 计算路径进行性能分析，对比普通 Attention 拆算子方案与 FlashAttention 思路在 310B1 上的可行性。
6. 使用 Ascend C 尝试实现 FA1 attention kernel，验证 QK、online softmax、P@V 等路径的正确性、数值稳定性和板端性能。
7. 对 P@V 的 vector 累加、Cube MatMul、GM workspace、UB/TSCM 数据布局等方案进行实验，定位当前自定义 FA1 kernel 慢于 BatchMatMulV2 + SoftmaxV2 + BatchMatMulV2 的原因。
8. 形成当前优化判断：简单局部 vector 化收益有限，后续需要从 tile 调度、K/V 复用、更大 fused tile 或更合适的 MatMul 调用模型上继续优化。

## 当前结论

SmolVLA 在 Orange Pi AIpro20T 上可以通过拆分子图和 ACL Runtime 逐步推进部署，但 attention 路径是主要性能瓶颈之一。当前自定义 FlashAttention 原型已经完成正确性验证，但要超过平台内置 BatchMatMul/Softmax 拆算子方案，需要进一步减少小 MatMul 调用次数，并提高 K/V tile 的复用效率。

## 下周计划

1. 继续推进 SmolVLA 异步推理框架，把视觉编码、语言条件和动作生成拆成可流水执行的任务。
2. 优化 attention kernel 的 tile 组织方式，重点验证多 Q block 共享 K/V tile 和更大 fused tile 的可行性。
3. 完善板端 benchmark，记录端到端延迟、单子图延迟、NPU 利用率和精度误差。
4. 将可稳定复现的部署步骤整理成文档，便于后续移植和复测。
