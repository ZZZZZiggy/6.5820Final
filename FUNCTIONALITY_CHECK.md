# 功能检查清单

## ✅ 已恢复的功能

### 1. MPTCP 模式支持

- [x] `--mptcp-mode coupled` 联合拥塞控制模式
- [x] `--mptcp-mode decoupled` 独立拥塞控制模式
- [x] 系统级 MPTCP 参数配置差异化

### 2. 网络拓扑功能

- [x] 单路径拓扑: `wifi_only`, `lte_only`, `5g_only`
- [x] MPTCP 拓扑: `lte_mptcp`, `5g_mptcp`
- [x] 静态参数模式 (`--link-mode static`)
- [x] 动态 trace 回放模式 (`--link-mode dynamic`)

### 3. 数据集转换脚本

- [x] `scripts/convert_deng_dataset.py` - ARFF 转 dat 格式
- [x] `scripts/setup_traces.sh` - 一键转换脚本
- [x] 支持生成 LTE 和 WiFi 的所有参数文件:
  - 上下行带宽 (`*_uplink.dat`, `*_downlink.dat`)
  - RTT 延迟 (`*_rtt.dat`)
  - 丢包率 (`*_loss.dat`)
  - 抖动 (`*_jitter.dat`)

### 4. 命令行参数

- [x] `--mode` (网络模式选择)
- [x] `--link-mode` (静态/动态模式)
- [x] `--mptcp-mode` (MPTCP 调度模式)
- [x] `--wifi-trace`, `--cell-trace` (trace 文件路径)
- [x] `--duration` (测试持续时间)
- [x] `--test` (应用场景选择)
- [x] `--cli` (进入 Mininet CLI)
- [x] `--compare` (对比模式)

### 5. 应用场景测试

- [x] `video_streaming` (视频流)
- [x] `voip_call` (VoIP 通话)
- [x] `iot_sensors` (IoT 传感器)
- [x] `file_download` (文件下载)
- [x] `web_browsing` (网页浏览)

## 🎯 使用示例

### 基础测试

```bash
# LTE单路径 - 静态参数
sudo python3 network/topology_enhanced.py --mode lte_only --link-mode static

# LTE单路径 - 真实数据动态回放
sudo python3 network/topology_enhanced.py --mode lte_only --link-mode dynamic --trace-file network/trace/lte/lte_downlink.dat
```

### MPTCP 模式对比

```bash
# MPTCP Coupled模式
sudo python3 network/topology_enhanced.py --mode lte_mptcp --mptcp-mode coupled \
    --wifi-trace network/trace/wifi/wifi_downlink.dat \
    --cell-trace network/trace/lte/lte_downlink.dat

# MPTCP Decoupled模式
sudo python3 network/topology_enhanced.py --mode lte_mptcp --mptcp-mode decoupled \
    --wifi-trace network/trace/wifi/wifi_downlink.dat \
    --cell-trace network/trace/lte/lte_downlink.dat
```

### 数据集转换

```bash
# 转换Deng数据集为trace格式
cd /Users/xiangyuguan/Documents/MIT/6.5820/final/6.5820_final
./scripts/setup_traces.sh

# 或手动转换
python3 scripts/convert_deng_dataset.py \
    --input ../downloads/mptcp-data/20-location-data/ \
    --output network/trace/
```

## 🚀 现在可以进行的完整实验

1. **LTE vs 5G 单路径对比** (5 个应用场景)
2. **WiFi vs LTE vs 5G 三路对比**
3. **MPTCP Coupled vs Decoupled 对比** (LTE 数据)
4. **LTE MPTCP vs 5G MPTCP 对比**
5. **静态参数 vs 真实数据重放对比**

所有功能已完整恢复! 🎉
