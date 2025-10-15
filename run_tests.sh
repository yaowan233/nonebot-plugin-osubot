#!/bin/bash
# 运行测试的简单脚本

echo "运行 nonebot-plugin-osubot 测试..."
echo ""

# 检查是否安装了 pdm
if command -v pdm &> /dev/null; then
    echo "使用 PDM 运行测试..."
    pdm run pytest tests/ -v
else
    echo "PDM 未安装，尝试使用 pytest..."
    if command -v pytest &> /dev/null; then
        pytest tests/ -v
    else
        echo "错误: pytest 未安装"
        echo "请运行: pip install pytest pytest-asyncio nonebug"
        exit 1
    fi
fi
