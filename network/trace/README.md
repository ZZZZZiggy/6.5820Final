# 网络 Trace 文件目录

本目录存放用于 Mininet 仿真的网络 trace 文件(.mahi 格式)

## 文件列表

### 单路径网络 Trace

- `wifi.mahi` - WiFi 网络参数 (从 LTE 数据集提取)
- `lte.mahi` - LTE 网络参数 (从 Deng 2013 数据集)
- `5g.mahi` - 5G 网络参数 (从爱尔兰 5G 数据集)

## MPTCP 组合

运行 MPTCP 测试时使用以下组合:

- **LTE MPTCP**: `lte.mahi` + `wifi.mahi`
- **5G MPTCP**: `5g.mahi` + `wifi.mahi`

## 文件格式

.mahi 文件为 Mahimahi 网络模拟器的标准 trace 格式，包含:

- 时间戳
- 网络带宽
- 延迟参数
- 丢包率
