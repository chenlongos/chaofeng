# SimCar 端侧闭环 Demo

## 能力边界

本 Demo 使用 SimCar 公开真值状态完成“分段接近并抓球”，用于验证 AgentOS 的端侧系统集成。它不是视觉识别、VLA、Nav2 或完整自主避障。

当前承诺：

- 准备好的无障碍场景；
- 文本指令触发自动接近和抓取；
- hasBall + armState=holding 状态判定；
- 碰撞、断连、超时立即停止并失败；
- 否定指令不下发动作。

当前不承诺：

- “这个障碍物”的 grounding；
- 绕障规划；
- 把球放入桶；
- 图像 Judge。

## 启动

1. 打开 <https://simcar.chenlongrobot.com/>。
2. 等待页面显示 Connected，复制 clientId。
3. 在 WSL 中运行：

    export SIMCAR_CLIENT_ID=car-xxxxxxxxx
    export SIMCAR_LIVE=1
    bash scripts/demo_simcar_link.sh

页面与终端并排展示。输入“帮我把球捡起来”；输入“不要捡球”可演示安全否决。

## 坐标校准

2026-07-17 实测：初始朝 -Z 时 rotation=π，left 会增加 rotation；比例采用 API 文档并由 5 cm 前进实测确认约为 1 cm = 0.09 仿真单位。Gateway 因此使用 π 朝向偏移，并在观察到动作进度后等待对应速度归零，避免转向惯性带入下一段。

## 安全设计

- Demo 配置固定 max_retries: 1；
- 每个移动片段不超过 5 cm；
- 每段动作后重新读取状态；
- 碰撞、状态超时和抓取超时都会发送 stop；
- 退出脚本也会尽力发送 stop；
- live e2e 默认跳过，只有显式设置 SIMCAR_E2E_LIVE=1 才启用。

## Reset 现状

公开 reset 接口会返回重置后的 JSON，但 2026-07-17 实测浏览器仿真实体仍可能继续上报旧状态。端侧不能把 reset HTTP 响应当作完成证据；现场以刷新模拟器页面并重新读取状态为准。
