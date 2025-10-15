# OSU Bot 测试文档

本目录包含 nonebot-plugin-osubot 的所有测试。

## 测试结构

测试文件按功能模块组织：

- `conftest.py` - pytest 配置和共享 fixtures
- `test_matchers.py` - 所有 matcher 的基本导入和处理器测试
- `test_bind.py` - 绑定相关的 matcher 测试
- `test_bp.py` - BP 相关的 matcher 测试
- `test_info.py` - 信息查询相关的 matcher 测试
- `test_map.py` - 地图相关的 matcher 测试
- `test_score.py` - 成绩相关的 matcher 测试
- `test_update.py` - 更新相关的 matcher 测试
- `test_guess.py` - 游戏相关的 matcher 测试
- `test_misc.py` - 其他杂项 matcher 测试
- `test_preview.py` - 预览和转换相关的 matcher 测试

## 运行测试

### 使用 PDM

```bash
pdm install -d
pdm run pytest tests/ -v
```

### 直接使用 pytest

```bash
pytest tests/ -v
```

### 运行特定测试文件

```bash
pytest tests/test_bind.py -v
```

### 运行特定测试函数

```bash
pytest tests/test_bind.py::test_bind_matcher_exists -v
```

## 测试覆盖的内容

每个 matcher 的测试包括：

1. **存在性测试** - 验证 matcher 可以正确导入
2. **优先级测试** - 验证 matcher 优先级为 11
3. **阻断行为测试** - 验证 matcher 的 block 属性为 True
4. **类型测试** - 验证 matcher 是正确的 Matcher 类型
5. **处理器测试** - 验证 matcher 有注册的处理器（handler），确保能够处理消息不会报错

## 持续集成

GitHub Actions 会在以下情况自动运行测试：

- 推送到 master 分支
- 创建 Pull Request

测试会在多个 Python 版本上运行（3.9, 3.10, 3.11, 3.12）以确保兼容性。

## 贡献指南

添加新 matcher 时，请：

1. 在相应的测试文件中添加测试
2. 如果是新的功能模块，创建新的测试文件
3. 确保添加以下测试：
   - 导入存在性测试
   - 优先级测试（如果适用）
   - 阻断行为测试（如果适用）
   - 处理器存在性测试
4. 确保所有测试通过后再提交代码

## 注意事项

- 测试使用 `nonebug` 作为测试框架
- 测试使用 `pytest-asyncio` 支持异步测试
- 所有测试都应该是独立的，不依赖外部状态
- 处理器测试确保 matcher 至少有一个处理器注册，这验证了 matcher 能够响应消息而不会立即报错
