# WatchDog - 轻量级API监控工具

![Python Version](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Status](https://img.shields.io/badge/status-alpha-red)

一个轻量级的API监控工具，支持定时检测和飞书告警。

## 特性

- 🚀 一行命令启动监控
- 🔔 支持飞书机器人告警
- ⏱️ 灵活的配置检测间隔
- 📊 简单的状态面板
- 🎯 零依赖（仅需Python标准库）

## 安装

```bash
pip install watchdog-cli
```

或者直接运行:

```bash
python watchdog.py
```

## 使用方法

### 1. 基础监控

```bash
python watchdog.py --url https://api.example.com/health
```

### 2. 带飞书告警

```bash
python watchdog.py --url https://api.example.com/health --feishu-webhook "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

### 3. 配置文件

创建 `watchdog.yaml`:

```yaml
monitors:
  - name: "My API"
    url: "https://api.example.com/health"
    interval: 60  # 秒
    
feishu:
  webhook: "https://open.feishu.cn/open-apis/bot/v2/hook/xxx"
```

运行:

```bash
python watchdog.py --config watchdog.yaml
```

## 配置说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| --url | 监控的URL | - |
| --interval | 检测间隔(秒) | 60 |
| --feishu-webhook | 飞书webhook地址 | - |
| --config | 配置文件路径 | - |
| --timeout | 请求超时(秒) | 10 |

## 输出示例

```
🔍 WatchDog API Monitor
========================
URL: https://api.example.com/health
Interval: 60s
Status: ✅ Running

Press Ctrl+C to stop
```

## 告警消息示例

当API不可用时，发送飞书消息:

```
🚨 API告警

服务: My API
URL: https://api.example.com/health
状态: ❌ 不可用
时间: 2026-03-03 10:00:00
错误: Connection timeout
```

## 开发

```bash
# 克隆项目
git clone https://github.com/yourname/watchdog-cli.git
cd watchdog-cli

# 安装开发依赖
pip install -r requirements-dev.txt

# 运行测试
python -m pytest tests/
```

## License

MIT License
