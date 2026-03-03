#!/usr/bin/env python3
"""
WatchDog - 轻量级API监控工具
"""

import argparse
import json
import time
import urllib.request
import urllib.error
import os
import signal
import sys
from datetime import datetime
from typing import Optional, Dict, List

# 颜色定义
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
RESET = '\033[0m'

class FeishuNotifier:
    """飞书机器人通知"""
    
    def __init__(self, webhook: str):
        self.webhook = webhook
    
    def send(self, message: str, status: str = "warning") -> bool:
        """发送飞书消息"""
        color = {"info": "green", "warning": "orange", "error": "red"}.get(status, "gray")
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {
                        "tag": "plain_text",
                        "content": "🚨 WatchDog 告警" if status == "error" else "ℹ️ WatchDog 通知"
                    },
                    "template": color
                },
                "elements": [
                    {
                        "tag": "markdown",
                        "content": message
                    }
                ]
            }
        }
        
        try:
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                self.webhook,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"发送飞书消息失败: {e}")
            return False


class Monitor:
    """API监控器"""
    
    def __init__(self, name: str, url: str, interval: int = 60, timeout: int = 10):
        self.name = name
        self.url = url
        self.interval = interval
        self.timeout = timeout
        self.last_status: Optional[bool] = None
        self.notifier: Optional[FeishuNotifier] = None
    
    def set_notifier(self, notifier: FeishuNotifier):
        self.notifier = notifier
    
    def check(self) -> Dict:
        """检查API状态"""
        start_time = time.time()
        try:
            req = urllib.request.Request(self.url)
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                elapsed = time.time() - start_time
                status = 200 <= response.status < 400
                return {
                    "status": status,
                    "status_code": response.status,
                    "response_time": round(elapsed * 1000, 2),
                    "error": None
                }
        except urllib.error.HTTPError as e:
            return {
                "status": False,
                "status_code": e.code,
                "response_time": round((time.time() - start_time) * 1000, 2),
                "error": f"HTTP {e.code}"
            }
        except urllib.error.URLError as e:
            return {
                "status": False,
                "status_code": None,
                "response_time": round((time.time() - start_time) * 1000, 2),
                "error": str(e.reason)
            }
        except Exception as e:
            return {
                "status": False,
                "status_code": None,
                "response_time": round((time.time() - start_time) * 1000, 2),
                "error": str(e)
            }
    
    def notify(self, result: Dict):
        """发送告警"""
        if not self.notifier:
            return
        
        if result["status"]:
            message = f"""✅ **{self.name}** 恢复健康
- URL: {self.url}
- 响应码: {result.get('status_code')}
- 响应时间: {result['response_time']}ms
- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            status = "info"
        else:
            message = f"""❌ **{self.name}** 服务异常
- URL: {self.url}
- 错误: {result.get('error', 'Unknown')}
- 响应时间: {result['response_time']}ms
- 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
            status = "error"
        
        self.notifier.send(message, status)


def parse_config(config_path: str) -> Dict:
    """解析配置文件"""
    import yaml
    try:
        with open(config_path, 'r') as f:
            return yaml.safe_load(f)
    except ImportError:
        # 如果没有yaml，用json
        with open(config_path, 'r') as f:
            return json.load(f)


def run_monitor(monitor: Monitor, feishu_webhook: Optional[str] = None):
    """运行监控"""
    # 设置飞书告警
    if feishu_webhook:
        notifier = FeishuNotifier(feishu_webhook)
        monitor.set_notifier(notifier)
    
    running = True
    
    def signal_handler(sig, frame):
        nonlocal running
        print(f"\n{GREEN}停止监控...{RESET}")
        running = False
    
    signal.signal(signal.SIGINT, signal_handler)
    
    print(f"""
{GREEN}🔍 WatchDog API Monitor{RESET}
{'='*40}
{GREEN}监控目标:{RESET} {monitor.url}
{GREEN}检测间隔:{RESET} {monitor.interval}秒
{GREEN}超时设置:{RESET} {monitor.timeout}秒
{'='*40}
{YELLOW}按 Ctrl+C 停止监控{RESET}
""")
    
    while running:
        result = monitor.check()
        
        status_icon = f"{GREEN}✓{RESET}" if result["status"] else f"{RED}✗{RESET}"
        status_text = "健康" if result["status"] else "异常"
        
        # 状态变化时发送告警
        if monitor.last_status is not None and monitor.last_status != result["status"]:
            monitor.notify(result)
        
        monitor.last_status = result["status"]
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] {status_icon} {status_text} | "
              f"响应时间: {result['response_time']}ms | "
              f"错误: {result.get('error', '-')}")
        
        # 等待下一次检查
        for _ in range(monitor.interval):
            if not running:
                break
            time.sleep(1)


def main():
    parser = argparse.ArgumentParser(description='WatchDog - 轻量级API监控工具')
    parser.add_argument('--url', '-u', help='监控的URL')
    parser.add_argument('--name', '-n', help='监控名称')
    parser.add_argument('--interval', '-i', type=int, default=60, help='检测间隔(秒)')
    parser.add_argument('--timeout', '-t', type=int, default=10, help='请求超时(秒)')
    parser.add_argument('--feishu-webhook', '-f', help='飞书webhook地址')
    parser.add_argument('--config', '-c', help='配置文件路径')
    
    args = parser.parse_args()
    
    # 从配置文件加载
    if args.config:
        config = parse_config(args.config)
        
        # 优先使用命令行参数
        feishu_webhook = args.feishu_webhook or config.get('feishu', {}).get('webhook')
        
        monitors = []
        for m in config.get('monitors', []):
            monitor = Monitor(
                name=m.get('name', 'API'),
                url=m['url'],
                interval=m.get('interval', 60),
                timeout=m.get('timeout', 10)
            )
            monitors.append((monitor, feishu_webhook))
        
        # TODO: 支持多监控
        if monitors:
            run_monitor(monitors[0][0], monitors[0][1])
    else:
        # 命令行模式
        if not args.url:
            parser.error('--url 是必需的')
        
        name = args.name or args.url
        monitor = Monitor(name, args.url, args.interval, args.timeout)
        
        run_monitor(monitor, args.feishu_webhook)


if __name__ == '__main__':
    main()
