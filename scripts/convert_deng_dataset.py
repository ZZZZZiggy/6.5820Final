#!/usr/bin/env python3
"""
Deng数据集转换脚本
将ARFF格式的LTE数据集转换为统一的.dat格式用于网络重放

用法:
    python convert_deng_dataset.py --input downloads/mptcp-data/20-location-data/ --output network/trace/

生成文件:
    network/trace/lte/*.dat
    network/trace/wifi/*.dat
"""

import os
import sys
import argparse
import glob
from collections import defaultdict
import statistics

def parse_arff_file(file_path):
    """解析单个ARFF文件"""
    print(f"解析文件: {file_path}")

    # 存储数据
    data_records = []

    with open(file_path, 'r', encoding='utf-8') as f:
        in_data_section = False

        for line_num, line in enumerate(f, 1):
            line = line.strip()

            # 找到数据段开始
            if line.startswith('@DATA'):
                in_data_section = True
                continue

            # 跳过注释和属性定义
            if not in_data_section or not line or line.startswith('@') or line.startswith('%'):
                continue

            # 解析数据行
            try:
                parts = line.split(',')
                if len(parts) < 40:  # 确保有足够的字段
                    continue

                # 提取关键字段 (基于实际ARFF结构)
                # 字段索引对应: 0=id, 1=gps_available, 2=direction, 3=phone_type, 4=activity, ...
                record = {
                    'id': parts[0].strip('"'),
                    'direction': parts[2].strip('"'),  # send/recv (索引2)
                    'phone_type': parts[3].strip('"'), # verizon/sprint (索引3)
                    'activity': parts[4].strip('"'),   # still/moving (索引4)

                    # WiFi参数
                    'wifi_avg_ping_rtt': float(parts[8]) if parts[8] != '?' and parts[8] != '2147483647' else None,  # 索引8
                    'wifi_mdev_ping_rtt': float(parts[9]) if parts[9] != '?' and parts[9] != '2147483647' else None,  # 索引9
                    'wifi_rssi': float(parts[11]) if parts[11] != '?' and parts[11] != '2147483647' else None,  # 索引11
                    'wifi_udp_tput': float(parts[13]) if parts[13] != '?' and parts[13] != '2147483647' else None,  # 索引13
                    'wifi_udp_lossrate': float(parts[14]) if parts[14] != '?' and parts[14] != '2147483647' else None,  # 索引14

                    # Cellular参数
                    'cell_avg_ping_rtt': float(parts[26]) if parts[26] != '?' and parts[26] != '2147483647' else None,  # 索引26
                    'cell_mdev_ping_rtt': float(parts[27]) if parts[27] != '?' and parts[27] != '2147483647' else None,  # 索引27
                    'cell_udp_tput': float(parts[29]) if parts[29] != '?' and parts[29] != '2147483647' else None,  # 索引29
                    'cell_udp_lossrate': float(parts[30]) if parts[30] != '?' and parts[30] != '2147483647' else None,  # 索引30

                    # 主要吞吐量字段 (核心数据)
                    'cell_tput': float(parts[35]) if parts[35] != '?' and parts[35] != '2147483647' else None,  # 索引35
                    'wifi_tput': float(parts[36]) if parts[36] != '?' and parts[36] != '2147483647' else None,  # 索引36
                    'cell_rtt': float(parts[37]) if parts[37] != '?' and parts[37] != '2147483647' else None,   # 索引37
                    'wifi_rtt': float(parts[38]) if parts[38] != '?' and parts[38] != '2147483647' else None,   # 索引38
                }

                data_records.append(record)

            except (ValueError, IndexError) as e:
                print(f"警告: 第{line_num}行解析失败: {e}")
                continue

    print(f"成功解析 {len(data_records)} 条记录")
    return data_records

def aggregate_data_by_direction(all_records):
    """按方向聚合数据 (send=上行, recv=下行)"""

    # 分别存储上行和下行数据
    uplink_data = {'lte': [], 'wifi': []}      # direction = 'send'
    downlink_data = {'lte': [], 'wifi': []}    # direction = 'recv'

    for record in all_records:
        direction = record['direction']

        # LTE数据
        lte_record = {
            'bandwidth': record['cell_tput'],
            'rtt': record['cell_rtt'],
            'loss_rate': record['cell_udp_lossrate'],
            'jitter': record['cell_mdev_ping_rtt']
        }

        # WiFi数据
        wifi_record = {
            'bandwidth': record['wifi_tput'],
            'rtt': record['wifi_rtt'],
            'loss_rate': record['wifi_udp_lossrate'],
            'jitter': record['wifi_mdev_ping_rtt']
        }

        # 过滤无效数据
        if all(v is not None for v in lte_record.values()):
            if direction == 'send':
                uplink_data['lte'].append(lte_record)
            else:  # recv
                downlink_data['lte'].append(lte_record)

        if all(v is not None for v in wifi_record.values()):
            if direction == 'send':
                uplink_data['wifi'].append(wifi_record)
            else:  # recv
                downlink_data['wifi'].append(wifi_record)

    return uplink_data, downlink_data

def write_dat_files(uplink_data, downlink_data, output_dir):
    """写入.dat文件"""

    os.makedirs(f"{output_dir}/lte", exist_ok=True)
    os.makedirs(f"{output_dir}/wifi", exist_ok=True)

    networks = ['lte', 'wifi']
    directions = [('uplink', uplink_data), ('downlink', downlink_data)]

    for network in networks:
        for direction_name, data_dict in directions:
            network_data = data_dict[network]

            if not network_data:
                print(f"警告: {network} {direction_name} 数据为空")
                continue

            print(f"写入 {network} {direction_name} 数据: {len(network_data)} 条记录")

            # 写入带宽文件
            bw_file = f"{output_dir}/{network}/{network}_{direction_name}.dat"
            with open(bw_file, 'w') as f:
                f.write("# 时间戳(ms),带宽(Mbps)\n")
                for i, record in enumerate(network_data):
                    timestamp = i * 100  # 100ms间隔
                    bw = max(0.1, record['bandwidth'])  # 最小0.1Mbps
                    f.write(f"{timestamp},{bw:.2f}\n")

            # 写入RTT文件 (只对下行数据，上行RTT通常相同)
            if direction_name == 'downlink':
                rtt_file = f"{output_dir}/{network}/{network}_rtt.dat"
                with open(rtt_file, 'w') as f:
                    f.write("# 时间戳(ms),RTT(ms)\n")
                    for i, record in enumerate(network_data):
                        timestamp = i * 100
                        rtt = max(1, record['rtt'])  # 最小1ms
                        f.write(f"{timestamp},{rtt:.2f}\n")

                # 写入丢包率文件
                loss_file = f"{output_dir}/{network}/{network}_loss.dat"
                with open(loss_file, 'w') as f:
                    f.write("# 时间戳(ms),丢包率(%)\n")
                    for i, record in enumerate(network_data):
                        timestamp = i * 100
                        loss = min(50, max(0, record['loss_rate']))  # 0-50%
                        f.write(f"{timestamp},{loss:.3f}\n")

                # 写入抖动文件
                jitter_file = f"{output_dir}/{network}/{network}_jitter.dat"
                with open(jitter_file, 'w') as f:
                    f.write("# 时间戳(ms),抖动(ms)\n")
                    for i, record in enumerate(network_data):
                        timestamp = i * 100
                        jitter = max(0, record['jitter'])  # 最小0ms
                        f.write(f"{timestamp},{jitter:.2f}\n")

def print_statistics(uplink_data, downlink_data):
    """打印统计信息"""
    print("\n=== 数据统计 ===")

    for network in ['lte', 'wifi']:
        print(f"\n{network.upper()} 网络:")

        # 上行统计
        if uplink_data[network]:
            up_bw = [r['bandwidth'] for r in uplink_data[network]]
            print(f"  上行: {len(up_bw)} 条记录")
            print(f"    带宽: {min(up_bw):.1f} - {max(up_bw):.1f} Mbps (平均 {statistics.mean(up_bw):.1f})")

        # 下行统计
        if downlink_data[network]:
            down_bw = [r['bandwidth'] for r in downlink_data[network]]
            down_rtt = [r['rtt'] for r in downlink_data[network]]
            down_loss = [r['loss_rate'] for r in downlink_data[network]]

            print(f"  下行: {len(down_bw)} 条记录")
            print(f"    带宽: {min(down_bw):.1f} - {max(down_bw):.1f} Mbps (平均 {statistics.mean(down_bw):.1f})")
            print(f"    RTT: {min(down_rtt):.1f} - {max(down_rtt):.1f} ms (平均 {statistics.mean(down_rtt):.1f})")
            print(f"    丢包率: {min(down_loss):.1f} - {max(down_loss):.1f} % (平均 {statistics.mean(down_loss):.3f})")

def main():
    parser = argparse.ArgumentParser(description='转换Deng数据集为统一dat格式')
    parser.add_argument('--input', required=True,
                       help='输入目录路径 (包含.arff文件)')
    parser.add_argument('--output', default='network/trace',
                       help='输出目录路径')
    parser.add_argument('--pattern', default='*.arff',
                       help='文件匹配模式')

    args = parser.parse_args()

    # 查找所有ARFF文件
    input_pattern = os.path.join(args.input, args.pattern)
    arff_files = glob.glob(input_pattern)

    if not arff_files:
        print(f"错误: 在 {args.input} 中未找到匹配 {args.pattern} 的文件")
        sys.exit(1)

    print(f"找到 {len(arff_files)} 个ARFF文件")

    # 解析所有文件
    all_records = []
    for file_path in arff_files:
        records = parse_arff_file(file_path)
        all_records.extend(records)

    print(f"总计 {len(all_records)} 条记录")

    # 聚合数据
    print("\n开始数据聚合...")
    uplink_data, downlink_data = aggregate_data_by_direction(all_records)

    # 写入文件
    print(f"\n写入文件到 {args.output}")
    write_dat_files(uplink_data, downlink_data, args.output)

    # 统计信息
    print_statistics(uplink_data, downlink_data)

    print(f"\n✅ 转换完成! 文件已保存到: {args.output}")
    print(f"   LTE文件: {args.output}/lte/")
    print(f"   WiFi文件: {args.output}/wifi/")

if __name__ == '__main__':
    main()
