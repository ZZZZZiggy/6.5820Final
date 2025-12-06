# 测试数据目录

本目录存放不同应用场景下的测试结果数据

## 目录结构

```
data/
├── video_streaming/    # 视频流媒体测试结果
├── voip_call/          # VoIP实时通信测试结果
├── iot_sensors/        # IoT传感器数据传输测试结果
├── file_download/      # 文件下载测试结果
└── web_browsing/       # 网页浏览测试结果
```

## 每个场景的测试矩阵

每个场景目录下包含 5 种网络配置的测试结果:

1. `wifi_only/` - WiFi 单独
2. `lte_only/` - LTE 单独
3. `5g_only/` - 5G 单独
4. `lte_mptcp/` - LTE + WiFi MPTCP
5. `5g_mptcp/` - 5G + WiFi MPTCP

## 数据格式

每个测试的输出包括:

- `metrics.json` - 性能指标 (吞吐量、延迟、丢包率等)
- `timeline.csv` - 时间序列数据
- `summary.txt` - 测试摘要
