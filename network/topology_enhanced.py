#!/usr/bin/env python3
"""
增强版Mininet拓扑脚本 - 支持静态参数和真实trace动态回放对比

使用方式:
    # 静态参数模式
    sudo python3 topology_enhanced.py --mode lte_only --link-mode static

    # 真实trace回放模式
    sudo python3 topology_enhanced.py --mode lte_only --link-mode dynamic --trace-file traces/lte.dat

    # MPTCP + 动态回放
    sudo python3 topology_enhanced.py --mode 5g_mptcp --link-mode dynamic \
        --wifi-trace traces/wifi.dat --cell-trace traces/5g.dat

    # MPTCP Coupled vs Decoupled 模式对比
    sudo python3 topology_enhanced.py --mode lte_mptcp --mptcp-mode coupled
    sudo python3 topology_enhanced.py --mode lte_mptcp --mptcp-mode decoupled

    # 使用真实数据集trace文件
    sudo python3 topology_enhanced.py --mode lte_mptcp --mptcp-mode coupled \
        --wifi-trace network/trace/wifi/wifi_downlink.dat \
        --cell-trace network/trace/lte/lte_downlink.dat

    # 对比实验 (同时运行静态和动态)
    sudo python3 topology_enhanced.py --mode lte_only --compare
"""

import os
import sys
import argparse
import json
import time
import threading
import subprocess
from datetime import datetime
from collections import deque

from mininet.net import Mininet
from mininet.node import Controller, OVSSwitch
from mininet.link import TCLink
from mininet.cli import CLI
from mininet.log import setLogLevel, info, error

# 导入trace回放器
from trace_replayer import TraceReplayer, NetworkParamsLoader


# ============================================================================
#                          增强版拓扑类
# ============================================================================

class EnhancedCellularWiFiTopology:
    """
    增强版网络拓扑，支持:
    1. 静态参数模式 (link_mode='static')
    2. 动态trace回放模式 (link_mode='dynamic')
    3. 对比模式 (compare=True)
    """

    def __init__(self, trace_dir='network/trace', link_mode='static'):
        self.net = None
        self.params_loader = NetworkParamsLoader(trace_dir)
        self.link_mode = link_mode
        self.mode = None
        self.trace_replayers = []
        self.links = {}  # 保存link引用

    def create_single_path_topology(self, network_type, trace_file=None):
        """创建单路径拓扑"""
        info(f"*** Creating single-path topology: {network_type} (link_mode={self.link_mode})\n")

        self.net = Mininet(controller=Controller, switch=OVSSwitch, link=TCLink)

        # 添加控制器
        self.net.addController('c0')

        # 添加主机
        client = self.net.addHost('client', ip='10.0.1.1/24')
        server = self.net.addHost('server', ip='10.0.1.100/24')

        # 添加交换机
        switch = self.net.addSwitch('s1')

        # 获取网络参数
        if self.link_mode == 'static':
            params = self.params_loader.get_static_params(network_type)
        else:
            params = self.params_loader.get_params_from_trace(trace_file) if trace_file else \
                     self.params_loader.get_static_params(network_type)

        info(f"*** Initial params: bw={params['bw']:.1f}Mbps, delay={params['delay']}, loss={params['loss']}%\n")

        # 添加链路
        self.net.addLink(client, switch, cls=TCLink)
        link = self.net.addLink(switch, server, cls=TCLink,
                               bw=params['bw'],
                               delay=params['delay'],
                               loss=params['loss'],
                               jitter=params.get('jitter', '0ms'))

        self.links['main'] = link

        # 如果是动态模式，准备trace回放器
        if self.link_mode == 'dynamic' and trace_file:
            self.pending_trace = {
                'file': trace_file,
                'link': link,
                'intf': 's1-eth2'
            }

        return self.net

    def create_mptcp_topology(self, cellular_type, mptcp_mode='coupled', wifi_trace=None, cell_trace=None):
        """创建MPTCP多路径拓扑"""
        info(f"*** Creating MPTCP topology: {cellular_type} + WiFi ({mptcp_mode}, link_mode={self.link_mode})\n")
        self.mptcp_mode = mptcp_mode

        self.net = Mininet(controller=Controller, switch=OVSSwitch, link=TCLink)

        self.net.addController('c0')

        # 添加主机
        client = self.net.addHost('client', ip='10.0.1.1/24')
        server = self.net.addHost('server', ip='10.0.2.100/24')

        # 添加交换机
        wifi_switch = self.net.addSwitch('s_wifi')
        cell_switch = self.net.addSwitch('s_cell')
        core_switch = self.net.addSwitch('s_core')

        # 获取参数
        if self.link_mode == 'static':
            wifi_params = self.params_loader.get_static_params('wifi')
            cell_params = self.params_loader.get_static_params(cellular_type)
        else:
            wifi_params = self.params_loader.get_params_from_trace(wifi_trace) if wifi_trace else \
                         self.params_loader.get_static_params('wifi')
            cell_params = self.params_loader.get_params_from_trace(cell_trace) if cell_trace else \
                         self.params_loader.get_static_params(cellular_type)

        info(f"*** WiFi params: bw={wifi_params['bw']:.1f}Mbps, delay={wifi_params['delay']}\n")
        info(f"*** {cellular_type.upper()} params: bw={cell_params['bw']:.1f}Mbps, delay={cell_params['delay']}\n")

        # 添加链路
        self.net.addLink(client, wifi_switch,
                        intfName1='client-wifi',
                        params1={'ip': '10.0.1.1/24'},
                        cls=TCLink)

        self.net.addLink(client, cell_switch,
                        intfName1='client-cell',
                        params1={'ip': '10.0.2.1/24'},
                        cls=TCLink)

        wifi_link = self.net.addLink(wifi_switch, core_switch, cls=TCLink,
                                     bw=wifi_params['bw'],
                                     delay=wifi_params['delay'],
                                     loss=wifi_params['loss'],
                                     jitter=wifi_params.get('jitter', '0ms'))

        cell_link = self.net.addLink(cell_switch, core_switch, cls=TCLink,
                                     bw=cell_params['bw'],
                                     delay=cell_params['delay'],
                                     loss=cell_params['loss'],
                                     jitter=cell_params.get('jitter', '0ms'))

        self.net.addLink(core_switch, server, cls=TCLink)

        self.links['wifi'] = wifi_link
        self.links['cell'] = cell_link

        # 准备动态回放
        if self.link_mode == 'dynamic':
            self.pending_traces = []
            if wifi_trace:
                self.pending_traces.append({
                    'file': wifi_trace,
                    'link': wifi_link,
                    'intf': 's_wifi-eth2'
                })
            if cell_trace:
                self.pending_traces.append({
                    'file': cell_trace,
                    'link': cell_link,
                    'intf': 's_cell-eth2'
                })

        return self.net

    def configure_mptcp(self, mode='coupled'):
        """配置MPTCP (coupled或decoupled模式)"""
        info(f"*** Configuring MPTCP ({mode} mode)\n")

        client = self.net.get('client')
        server = self.net.get('server')

        # 基础MPTCP配置
        basic_commands = [
            'sysctl -w net.mptcp.enabled=1 2>/dev/null || true',
            'sysctl -w net.mptcp.checksum_enabled=0 2>/dev/null || true',
        ]

        # 模式特定配置
        if mode == 'coupled':
            # Coupled模式：使用联合拥塞控制
            mode_commands = [
                'sysctl -w net.mptcp.mptcp_congestion=coupled 2>/dev/null || true',
                'sysctl -w net.mptcp.mptcp_scheduler=default 2>/dev/null || true',
                'sysctl -w net.mptcp.mptcp_path_manager=fullmesh 2>/dev/null || true'
            ]
        else:  # decoupled
            # Decoupled模式：独立拥塞控制，更激进的调度
            mode_commands = [
                'sysctl -w net.mptcp.mptcp_congestion=lia 2>/dev/null || true',
                'sysctl -w net.mptcp.mptcp_scheduler=roundrobin 2>/dev/null || true',
                'sysctl -w net.mptcp.mptcp_path_manager=fullmesh 2>/dev/null || true'
            ]

        all_commands = basic_commands + mode_commands

        for cmd in all_commands:
            client.cmd(cmd)
            server.cmd(cmd)

        # 配置路由
        client.cmd('ip route add 10.0.2.0/24 dev client-cell 2>/dev/null || true')

        info(f"*** MPTCP {mode} mode configured\n")

    def start(self):
        """启动网络"""
        info("*** Starting network\n")
        self.net.start()

        # 启动trace回放器
        if self.link_mode == 'dynamic':
            self._start_trace_replayers()

    def _start_trace_replayers(self):
        """启动所有trace回放器"""
        if hasattr(self, 'pending_trace'):
            t = self.pending_trace
            replayer = TraceReplayer(t['file'], t['link'], t['intf'])
            replayer.start()
            self.trace_replayers.append(replayer)

        if hasattr(self, 'pending_traces'):
            for t in self.pending_traces:
                replayer = TraceReplayer(t['file'], t['link'], t['intf'])
                replayer.start()
                self.trace_replayers.append(replayer)

    def stop(self):
        """停止网络"""
        # 停止所有回放器
        for replayer in self.trace_replayers:
            replayer.stop()

        info("*** Stopping network\n")
        if self.net:
            self.net.stop()

    def run_test(self, test_type, duration=30, output_dir='data'):
        """运行性能测试"""
        info(f"*** Running {test_type} test for {duration}s (link_mode={self.link_mode})\n")

        client = self.net.get('client')
        server = self.net.get('server')

        # 创建输出目录
        result_dir = os.path.join(output_dir, self.link_mode, self.mode, test_type)
        os.makedirs(result_dir, exist_ok=True)

        results = {
            'mode': self.mode,
            'link_mode': self.link_mode,
            'test_type': test_type,
            'duration': duration,
            'timestamp': datetime.now().isoformat(),
            'metrics': {}
        }

        # 根据测试类型执行测试
        if test_type == 'file_download':
            results['metrics'] = self._run_iperf_test(client, server, duration)
        elif test_type == 'voip_call':
            results['metrics'] = self._run_udp_test(client, server, duration, bandwidth='64k')
        elif test_type == 'video_streaming':
            results['metrics'] = self._run_iperf_test(client, server, duration, bandwidth='25M')
        elif test_type == 'iot_sensors':
            results['metrics'] = self._run_udp_test(client, server, duration, bandwidth='100k', packet_size=64)
        elif test_type == 'web_browsing':
            results['metrics'] = self._run_ping_test(client, server, count=duration)
        else:
            results['metrics'] = self._run_iperf_test(client, server, duration)

        # 添加trace回放统计
        if self.trace_replayers:
            results['trace_stats'] = [r.stats for r in self.trace_replayers]

        # 保存结果
        result_file = os.path.join(result_dir, 'metrics.json')
        with open(result_file, 'w') as f:
            json.dump(results, f, indent=2)

        info(f"*** Results saved to {result_file}\n")
        return results

    def _run_iperf_test(self, client, server, duration, bandwidth=None):
        """运行iperf TCP测试"""
        info("*** Running iperf TCP test\n")

        server.cmd('iperf3 -s -D')
        time.sleep(1)

        bw_option = f'-b {bandwidth}' if bandwidth else ''
        result = client.cmd(f'iperf3 -c {server.IP()} -t {duration} {bw_option} -J')

        server.cmd('killall iperf3 2>/dev/null')

        try:
            data = json.loads(result)
            return {
                'throughput_mbps': data['end']['sum_received']['bits_per_second'] / 1e6,
                'retransmits': data['end']['sum_sent'].get('retransmits', 0),
                'mean_rtt_ms': data['end']['streams'][0]['sender'].get('mean_rtt', 0) / 1000
            }
        except (json.JSONDecodeError, KeyError) as e:
            info(f"*** iperf parse error: {e}\n")
            return {'raw_output': result[:500]}

    def _run_udp_test(self, client, server, duration, bandwidth='1M', packet_size=1400):
        """运行iperf UDP测试"""
        info("*** Running iperf UDP test\n")

        server.cmd('iperf3 -s -D')
        time.sleep(1)

        result = client.cmd(f'iperf3 -c {server.IP()} -u -t {duration} -b {bandwidth} -l {packet_size} -J')

        server.cmd('killall iperf3 2>/dev/null')

        try:
            data = json.loads(result)
            udp_data = data['end']['sum']
            return {
                'throughput_mbps': udp_data['bits_per_second'] / 1e6,
                'jitter_ms': udp_data.get('jitter_ms', 0),
                'lost_packets': udp_data.get('lost_packets', 0),
                'lost_percent': udp_data.get('lost_percent', 0)
            }
        except (json.JSONDecodeError, KeyError) as e:
            info(f"*** UDP test parse error: {e}\n")
            return {'raw_output': result[:500]}

    def _run_ping_test(self, client, server, count=30):
        """运行ping测试"""
        info("*** Running ping test\n")

        result = client.cmd(f'ping -c {count} {server.IP()}')

        lines = result.split('\n')
        rtt_line = [l for l in lines if 'rtt' in l or 'round-trip' in l]

        metrics = {'raw_output': result[:500]}

        if rtt_line:
            try:
                parts = rtt_line[0].split('=')[1].strip().split('/')
                metrics = {
                    'rtt_min_ms': float(parts[0]),
                    'rtt_avg_ms': float(parts[1]),
                    'rtt_max_ms': float(parts[2]),
                    'rtt_mdev_ms': float(parts[3].split()[0])
                }
            except (IndexError, ValueError):
                pass

        return metrics


# ============================================================================
#                          对比实验运行器
# ============================================================================

def run_comparison_experiment(mode, trace_file=None, wifi_trace=None, cell_trace=None,
                              output_dir='data', duration=30, test_types=None):
    """
    运行静态 vs 动态对比实验
    """
    if test_types is None:
        test_types = ['file_download', 'video_streaming', 'voip_call', 'web_browsing']

    comparison_results = {
        'static': {},
        'dynamic': {}
    }

    for link_mode in ['static', 'dynamic']:
        info(f"\n{'='*60}\n")
        info(f"*** Running experiments with link_mode={link_mode}\n")
        info(f"{'='*60}\n")

        topo = EnhancedCellularWiFiTopology(link_mode=link_mode)
        topo.mode = mode

        try:
            # 创建拓扑
            if mode in ['wifi_only', 'lte_only', '5g_only']:
                network_type = mode.replace('_only', '')
                topo.create_single_path_topology(network_type, trace_file)
            elif mode == 'lte_mptcp':
                mptcp_mode = getattr(args, 'mptcp_mode', 'coupled')
                topo.create_mptcp_topology('lte', mptcp_mode, wifi_trace, cell_trace)
                topo.configure_mptcp(mptcp_mode)
            elif mode == '5g_mptcp':
                mptcp_mode = getattr(args, 'mptcp_mode', 'coupled')
                topo.create_mptcp_topology('5g', mptcp_mode, wifi_trace, cell_trace)
                topo.configure_mptcp(mptcp_mode)

            topo.start()

            # 运行所有测试
            for test_type in test_types:
                info(f"\n*** Test: {test_type}\n")
                result = topo.run_test(test_type, duration, output_dir)
                comparison_results[link_mode][test_type] = result
                time.sleep(2)

        finally:
            topo.stop()

        time.sleep(3)  # 等待清理

    # 生成对比报告
    report = generate_comparison_report(comparison_results)

    report_file = os.path.join(output_dir, 'comparison_report.json')
    with open(report_file, 'w') as f:
        json.dump(report, f, indent=2)

    info(f"\n*** Comparison report saved to {report_file}\n")

    return report


def generate_comparison_report(results):
    """生成对比报告"""
    report = {
        'summary': {},
        'details': results
    }

    for test_type in results.get('static', {}):
        static_metrics = results['static'][test_type].get('metrics', {})
        dynamic_metrics = results['dynamic'].get(test_type, {}).get('metrics', {})

        report['summary'][test_type] = {
            'static': static_metrics,
            'dynamic': dynamic_metrics,
            'difference': {}
        }

        # 计算差异
        for key in static_metrics:
            if key in dynamic_metrics and isinstance(static_metrics[key], (int, float)):
                static_val = static_metrics[key]
                dynamic_val = dynamic_metrics[key]
                if static_val != 0:
                    diff_percent = (dynamic_val - static_val) / static_val * 100
                    report['summary'][test_type]['difference'][key] = {
                        'absolute': dynamic_val - static_val,
                        'percent': diff_percent
                    }

    return report


def run_all_tests(topo, output_dir='data', duration=30):
    """运行所有测试"""
    test_types = ['video_streaming', 'voip_call', 'iot_sensors', 'file_download', 'web_browsing']

    results = {}
    for test_type in test_types:
        info(f"\n{'='*50}\n")
        results[test_type] = topo.run_test(test_type, duration, output_dir)
        time.sleep(2)

    return results


# ============================================================================
#                               MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description='Enhanced Cellular vs WiFi Network Topology with Static/Dynamic comparison',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # 静态参数模式
    sudo python3 topology_enhanced.py --mode lte_only --link-mode static

    # 动态trace回放
    sudo python3 topology_enhanced.py --mode lte_only --link-mode dynamic --trace-file traces/lte.dat

    # 对比实验
    sudo python3 topology_enhanced.py --mode lte_only --compare --trace-file traces/lte.dat

    # MPTCP + 动态
    sudo python3 topology_enhanced.py --mode 5g_mptcp --link-mode dynamic \\
        --wifi-trace traces/wifi.dat --cell-trace traces/5g.dat
        """
    )

    parser.add_argument('--mode', type=str, required=True,
                       choices=['wifi_only', 'lte_only', '5g_only', 'lte_mptcp', '5g_mptcp'],
                       help='Network mode to test')
    parser.add_argument('--link-mode', type=str, default='static',
                       choices=['static', 'dynamic'],
                       help='Link mode: static params or dynamic trace replay')
    parser.add_argument('--trace-file', type=str,
                       help='Trace file for single-path dynamic mode')
    parser.add_argument('--wifi-trace', type=str,
                       help='WiFi trace file for MPTCP mode')
    parser.add_argument('--cell-trace', type=str,
                       help='Cellular trace file for MPTCP mode')
    parser.add_argument('--mptcp-mode', type=str, choices=['coupled', 'decoupled'],
                       default='coupled', help='MPTCP scheduling mode (coupled or decoupled)')
    parser.add_argument('--trace-dir', type=str, default='network/trace',
                       help='Directory containing trace files')
    parser.add_argument('--output-dir', type=str, default='data',
                       help='Directory to save results')
    parser.add_argument('--duration', type=int, default=30,
                       help='Test duration in seconds')
    parser.add_argument('--cli', action='store_true',
                       help='Enter Mininet CLI after setup')
    parser.add_argument('--compare', action='store_true',
                       help='Run comparison between static and dynamic modes')
    parser.add_argument('--test', type=str, default='all',
                       choices=['all', 'video_streaming', 'voip_call', 'iot_sensors',
                               'file_download', 'web_browsing'],
                       help='Test type to run')

    args = parser.parse_args()

    setLogLevel('info')

    # 对比模式
    if args.compare:
        info("*** Running comparison experiment (static vs dynamic)\n")
        run_comparison_experiment(
            mode=args.mode,
            trace_file=args.trace_file,
            wifi_trace=args.wifi_trace,
            cell_trace=args.cell_trace,
            output_dir=args.output_dir,
            duration=args.duration
        )
        return

    # 单独模式
    topo = EnhancedCellularWiFiTopology(trace_dir=args.trace_dir, link_mode=args.link_mode)
    topo.mode = args.mode

    try:
        if args.mode == 'wifi_only':
            topo.create_single_path_topology('wifi', args.trace_file)
        elif args.mode == 'lte_only':
            topo.create_single_path_topology('lte', args.trace_file)
        elif args.mode == '5g_only':
            topo.create_single_path_topology('5g', args.trace_file)
        elif args.mode == 'lte_mptcp':
            topo.create_mptcp_topology('lte', args.mptcp_mode, args.wifi_trace, args.cell_trace)
            topo.configure_mptcp(args.mptcp_mode)
        elif args.mode == '5g_mptcp':
            topo.create_mptcp_topology('5g', args.mptcp_mode, args.wifi_trace, args.cell_trace)
            topo.configure_mptcp(args.mptcp_mode)

        topo.start()

        if args.cli:
            CLI(topo.net)
        else:
            if args.test == 'all':
                run_all_tests(topo, args.output_dir, args.duration)
            else:
                topo.run_test(args.test, args.duration, args.output_dir)

    finally:
        topo.stop()


if __name__ == '__main__':
    main()
