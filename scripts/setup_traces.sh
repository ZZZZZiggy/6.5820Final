#!/bin/bash
# Deng数据集转换和测试脚本

echo "=== Deng数据集转换脚本 ==="

# 设置路径
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
INPUT_DIR="$PROJECT_DIR/../downloads/mptcp-data/20-location-data"
OUTPUT_DIR="$PROJECT_DIR/network/trace"

echo "项目目录: $PROJECT_DIR"
echo "输入目录: $INPUT_DIR"
echo "输出目录: $OUTPUT_DIR"

# 检查输入目录是否存在
if [ ! -d "$INPUT_DIR" ]; then
    echo "❌ 错误: 输入目录不存在: $INPUT_DIR"
    echo "请确保已下载Deng数据集到正确位置"
    exit 1
fi

# 检查Python脚本是否存在
if [ ! -f "$SCRIPT_DIR/convert_deng_dataset.py" ]; then
    echo "❌ 错误: 转换脚本不存在: $SCRIPT_DIR/convert_deng_dataset.py"
    exit 1
fi

echo ""
echo "开始转换..."

# 运行转换脚本
cd "$PROJECT_DIR"
python3 scripts/convert_deng_dataset.py \
    --input "$INPUT_DIR" \
    --output "$OUTPUT_DIR"

# 检查结果
if [ $? -eq 0 ]; then
    echo ""
    echo "✅ 转换完成!"
    echo ""
    echo "生成的文件:"
    echo "📁 $OUTPUT_DIR/lte/"
    if [ -d "$OUTPUT_DIR/lte" ]; then
        ls -la "$OUTPUT_DIR/lte/"
    fi
    echo ""
    echo "📁 $OUTPUT_DIR/wifi/"
    if [ -d "$OUTPUT_DIR/wifi" ]; then
        ls -la "$OUTPUT_DIR/wifi/"
    fi

    echo ""
    echo "现在可以运行网络测试:"
    echo "  # 单路径测试"
    echo "  sudo python3 network/topology_enhanced.py --mode lte_only --link-mode dynamic --trace-file network/trace/lte/lte_downlink.dat"
    echo ""
    echo "  # MPTCP测试"
    echo "  sudo python3 network/topology_enhanced.py --mode lte_mptcp --link-mode dynamic --wifi-trace network/trace/wifi/wifi_downlink.dat --cell-trace network/trace/lte/lte_downlink.dat"

else
    echo "❌ 转换失败"
    exit 1
fi
