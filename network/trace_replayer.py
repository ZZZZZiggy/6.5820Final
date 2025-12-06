#!/usr/bin/env python3
"""
网络trace动态回放器模块

支持的trace格式:
1. Mahimahi格式 (.mahi): 每行一个时间戳(ms)，表示可发送一个包的时刻
2. 带宽时间序列 (.dat/.csv): 每行 "时间戳,带宽(Mbps)" 或 每行一个带宽值
"""

import os
import time
import threading
import subprocess
from mininet.log import info, error


class TraceReplayer:
    """
    真实网络trace动态回放器

    支持的trace格式:
    1. Mahimahi格式 (.mahi): 每行一个时间戳(ms)，表示可发送一个包的时刻
    2. 带宽时间序列 (.dat/.csv): 每行 "时间戳,带宽(Mbps)" 或 每行一个带宽值
    """

    def __init__(self, trace_file, link, intf_name, interval_ms=100):
        """
        Args:
            trace_file: trace文件路径
            link: Mininet Link对象
            intf_name: 接口名称 (如 's1-eth2')
            interval_ms: 更新间隔(毫秒)
        """
        self.trace_file = trace_file
        self.link = link
        self.intf_name = intf_name
        self.interval = interval_ms / 1000.0
        self.running = False
        self.thread = None

        # 加载trace
        self.bandwidth_samples = self._load_trace(trace_file)
        info(f"*** TraceReplayer: Loaded {len(self.bandwidth_samples)} samples from {trace_file}\n")

        # 统计信息
        self.stats = {
            'updates': 0,
            'min_bw': min(self.bandwidth_samples) if self.bandwidth_samples else 0,
            'max_bw': max(self.bandwidth_samples) if self.bandwidth_samples else 0,
            'avg_bw': sum(self.bandwidth_samples) / len(self.bandwidth_samples) if self.bandwidth_samples else 0
        }
        info(f"*** TraceReplayer: BW range [{self.stats['min_bw']:.2f}, {self.stats['max_bw']:.2f}] Mbps, avg={self.stats['avg_bw']:.2f} Mbps\n")

    def _load_trace(self, filepath):
        """
        加载trace文件，转换为带宽序列 (Mbps)
        """
        if not os.path.exists(filepath):
            error(f"*** Trace file not found: {filepath}\n")
            return [10.0]  # 默认10Mbps

        ext = os.path.splitext(filepath)[1].lower()

        if ext == '.mahi':
            return self._load_mahi_trace(filepath)
        else:
            return self._load_bandwidth_trace(filepath)

    def _load_mahi_trace(self, filepath):
        """
        加载Mahimahi格式trace
        转换逻辑: 计算每个时间窗口内的包数 -> 带宽
        """
        timestamps = []
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    try:
                        timestamps.append(float(line))
                    except ValueError:
                        continue

        if not timestamps:
            return [10.0]

        # 按100ms窗口聚合，计算每个窗口的带宽
        window_ms = 100
        max_time = max(timestamps)
        bandwidths = []

        # 包大小假设为1500字节
        packet_bits = 1500 * 8

        for window_start in range(0, int(max_time), window_ms):
            window_end = window_start + window_ms
            # 统计这个窗口内的包数
            packets = sum(1 for t in timestamps if window_start <= t < window_end)
            # 转换为Mbps
            bw_mbps = (packets * packet_bits) / (window_ms / 1000) / 1e6
            bandwidths.append(max(0.1, bw_mbps))  # 最小0.1Mbps

        return bandwidths if bandwidths else [10.0]

    def _load_bandwidth_trace(self, filepath):
        """
        加载带宽时间序列文件
        格式: 每行一个带宽值(Mbps) 或 "时间,带宽"
        """
        bandwidths = []
        with open(filepath, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#'):
                    parts = line.split(',')
                    try:
                        if len(parts) >= 2:
                            bw = float(parts[1])
                        else:
                            bw = float(parts[0])
                        bandwidths.append(max(0.1, bw))
                    except ValueError:
                        continue

        return bandwidths if bandwidths else [10.0]

    def start(self):
        """开始回放"""
        self.running = True
        self.thread = threading.Thread(target=self._replay_loop, daemon=True)
        self.thread.start()
        info(f"*** TraceReplayer: Started for {self.intf_name}\n")

    def stop(self):
        """停止回放"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=2)
        info(f"*** TraceReplayer: Stopped. Total updates: {self.stats['updates']}\n")

    def _replay_loop(self):
        """回放主循环"""
        idx = 0
        while self.running:
            bw = self.bandwidth_samples[idx % len(self.bandwidth_samples)]

            # 使用tc命令动态修改带宽
            self._set_bandwidth(bw)

            self.stats['updates'] += 1
            idx += 1
            time.sleep(self.interval)

    def _set_bandwidth(self, bw_mbps):
        """使用tc命令设置带宽"""
        try:
            # 使用tc修改htb qdisc的rate
            cmd = f"tc qdisc change dev {self.intf_name} root tbf rate {bw_mbps}mbit burst 15k latency 50ms"
            subprocess.run(cmd, shell=True, capture_output=True, timeout=1)
        except Exception as e:
            # 备用方法：重新配置netem
            try:
                cmd = f"tc qdisc change dev {self.intf_name} root netem rate {bw_mbps}mbit"
                subprocess.run(cmd, shell=True, capture_output=True, timeout=1)
            except:
                pass

    def get_current_bw(self):
        """获取当前带宽"""
        idx = self.stats['updates'] % len(self.bandwidth_samples)
        return self.bandwidth_samples[idx]


class NetworkParamsLoader:
    """加载和管理网络参数"""

    # 静态默认参数 (基于典型网络特性)
    STATIC_DEFAULTS = {
        'wifi': {
            'bw': 50,           # Mbps
            'delay': '10ms',
            'loss': 0.1,        # %
            'jitter': '2ms'
        },
        'lte': {
            'bw': 20,           # Mbps
            'delay': '50ms',
            'loss': 0.5,        # %
            'jitter': '10ms'
        },
        '5g': {
            'bw': 100,          # Mbps
            'delay': '10ms',
            'loss': 0.1,        # %
            'jitter': '2ms'
        }
    }

    def __init__(self, trace_dir='network/trace'):
        self.trace_dir = trace_dir

    def get_static_params(self, network_type):
        """获取静态参数"""
        return self.STATIC_DEFAULTS.get(network_type, self.STATIC_DEFAULTS['lte']).copy()

    def get_params_from_trace(self, trace_file):
        """从trace文件提取平均参数"""
        if not os.path.exists(trace_file):
            info(f"*** Warning: Trace {trace_file} not found\n")
            return self.STATIC_DEFAULTS['lte'].copy()

        # 加载trace并计算统计
        replayer = TraceReplayer(trace_file, None, 'dummy', 100)

        return {
            'bw': replayer.stats['avg_bw'],
            'delay': '20ms',  # 默认延迟
            'loss': 0.5,
            'jitter': '5ms'
        }
