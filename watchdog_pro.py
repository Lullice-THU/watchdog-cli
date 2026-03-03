#!/usr/bin/env python3
"""
WatchDog Pro - 分布式API监控系统
支持: HTTP/TCP/UDP/WS/WebSocket/DNS/SSL 监控
"""

import asyncio
import json
import time
import signal
import sys
import argparse
from datetime import datetime
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
import urllib.request
import urllib.error
import socket
import ssl
import urllib.parse

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False


class CheckType(Enum):
    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    UDP = "udp"
    DNS = "dns"
    SSL = "ssl"
    PING = "ping"
    WEBSOCKET = "ws"


@dataclass
class MonitorTarget:
    """监控目标"""
    name: str
    url: str
    check_type: CheckType = CheckType.HTTP
    interval: int = 60
    timeout: int = 10
    expected_status: int = 200
    headers: Dict = field(default_factory=dict)
    method: str = "GET"
    body: Optional[str] = None
    retry: int = 2
    enabled: bool = True


@dataclass
class CheckResult:
    """检查结果"""
    target: str
    timestamp: str
    success: bool
    response_time_ms: float
    status_code: Optional[int] = None
    error: Optional[str] = None
    details: Dict = field(default_factory=dict)


class NotificationHandler:
    """通知处理器"""
    
    def __init__(self):
        self.handlers: List[Callable] = []
    
    def add_handler(self, handler: Callable):
        self.handlers.append(handler)
    
    async def notify(self, result: CheckResult, config: Dict):
        for handler in self.handlers:
            try:
                await handler(result, config)
            except Exception as e:
                print(f"通知失败: {e}")


class FeishuNotifier:
    """飞书通知"""
    
    def __init__(self, webhook: str):
        self.webhook = webhook
    
    async def send(self, message: str, status: str = "info"):
        color_map = {
            "info": "green",
            "warning": "orange", 
            "error": "red",
            "success": "green"
        }
        
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "🚨 WatchDog 告警" if status == "error" else "ℹ️ WatchDog 通知"},
                    "template": color_map.get(status, "gray")
                },
                "elements": [
                    {"tag": "markdown", "content": message}
                ]
            }
        }
        
        data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            self.webhook,
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.status == 200
        except Exception as e:
            print(f"飞书通知失败: {e}")
            return False


class MonitorEngine:
    """监控引擎"""
    
    def __init__(self, targets: List[MonitorTarget], notifier: Optional[NotificationHandler] = None):
        self.targets = targets
        self.notifier = notifier
        self.running = False
        self.last_status: Dict[str, bool] = {}
        self.results: List[CheckResult] = []
        self.stats: Dict[str, Dict] = {}
    
    async def check_http(self, target: MonitorTarget) -> CheckResult:
        """HTTP/HTTPS检查"""
        start = time.time()
        try:
            if HAS_AIOHTTP:
                async with aiohttp.ClientSession() as session:
                    async with session.request(
                        target.method,
                        target.url,
                        headers=target.headers,
                        data=target.body,
                        timeout=aiohttp.ClientTimeout(total=target.timeout),
                        ssl=target.check_type == CheckType.HTTPS
                    ) as response:
                        elapsed = (time.time() - start) * 1000
                        success = response.status == target.expected_status
                        return CheckResult(
                            target=target.name,
                            timestamp=datetime.now().isoformat(),
                            success=success,
                            response_time_ms=round(elapsed, 2),
                            status_code=response.status,
                            details={"url": target.url}
                        )
            else:
                req = urllib.request.Request(target.url, headers=target.headers, method=target.method)
                if target.body:
                    req.data = target.body.encode('utf-8')
                
                with urllib.request.urlopen(req, timeout=target.timeout) as response:
                    elapsed = (time.time() - start) * 1000
                    success = response.status == target.expected_status
                    return CheckResult(
                        target=target.name,
                        timestamp=datetime.now().isoformat(),
                        success=success,
                        response_time_ms=round(elapsed, 2),
                        status_code=response.status,
                        details={"url": target.url}
                    )
        except urllib.error.HTTPError as e:
            return CheckResult(
                target=target.name,
                timestamp=datetime.now().isoformat(),
                success=False,
                response_time_ms=(time.time() - start) * 1000,
                status_code=e.code,
                error=f"HTTP {e.code}"
            )
        except Exception as e:
            return CheckResult(
                target=target.name,
                timestamp=datetime.now().isoformat(),
                success=False,
                response_time_ms=(time.time() - start) * 1000,
                error=str(e.reason) if hasattr(e, 'reason') else str(e)
            )
    
    async def check_tcp(self, target: MonitorTarget) -> CheckResult:
        """TCP端口检查"""
        start = time.time()
        try:
            url = urllib.parse.urlparse(target.url)
            host = url.hostname or "localhost"
            port = url.port or 80
            
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=target.timeout
            )
            writer.close()
            await writer.wait_closed()
            
            return CheckResult(
                target=target.name,
                timestamp=datetime.now().isoformat(),
                success=True,
                response_time_ms=(time.time() - start) * 1000,
                details={"host": host, "port": port}
            )
        except Exception as e:
            return CheckResult(
                target=target.name,
                timestamp=datetime.now().isoformat(),
                success=False,
                response_time_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def check_ssl(self, target: MonitorTarget) -> CheckResult:
        """SSL证书检查"""
        start = time.time()
        try:
            url = urllib.parse.urlparse(target.url)
            host = url.hostname or "localhost"
            port = url.port or 443
            
            context = ssl.create_default_context()
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port, ssl=context),
                timeout=target.timeout
            )
            
            # 获取证书信息
            ssl_obj = writer.get_extra_info('ssl_context')
            cert = ssl_obj.getpeercert()
            
            writer.close()
            await writer.wait_closed()
            
            # 解析证书过期时间
            from email.utils import parsedate_to_datetime
            not_after = cert.get('notAfter', '')
            
            return CheckResult(
                target=target.name,
                timestamp=datetime.now().isoformat(),
                success=True,
                response_time_ms=(time.time() - start) * 1000,
                details={"host": host, "port": port, "cert_expires": not_after}
            )
        except Exception as e:
            return CheckResult(
                target=target.name,
                timestamp=datetime.now().isoformat(),
                success=False,
                response_time_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def check_dns(self, target: MonitorTarget) -> CheckResult:
        """DNS检查"""
        start = time.time()
        try:
            url = urllib.parse.urlparse(target.url)
            host = url.hostname
            
            ip = socket.gethostbyname(host)
            
            return CheckResult(
                target=target.name,
                timestamp=datetime.now().isoformat(),
                success=True,
                response_time_ms=(time.time() - start) * 1000,
                details={"host": host, "ip": ip}
            )
        except Exception as e:
            return CheckResult(
                target=target.name,
                timestamp=datetime.now().isoformat(),
                success=False,
                response_time_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def check_target(self, target: MonitorTarget) -> CheckResult:
        """检查单个目标"""
        if target.check_type in (CheckType.HTTP, CheckType.HTTPS):
            return await self.check_http(target)
        elif target.check_type == CheckType.TCP:
            return await self.check_tcp(target)
        elif target.check_type == CheckType.SSL:
            return await self.check_ssl(target)
        elif target.check_type == CheckType.DNS:
            return await self.check_dns(target)
        else:
            return CheckResult(
                target=target.name,
                timestamp=datetime.now().isoformat(),
                success=False,
                response_time_ms=0,
                error=f"不支持的检查类型: {target.check_type}"
            )
    
    async def run_check_cycle(self):
        """执行一轮检查"""
        tasks = [self.check_target(t) for t in self.targets if t.enabled]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                continue
            
            self.results.append(result)
            
            # 状态变化通知
            prev = self.last_status.get(result.target)
            if prev is not None and prev != result.success:
                await self._notify_status_change(result)
            
            self.last_status[result.target] = result.success
            
            # 更新统计
            self._update_stats(result)
    
    async def _notify_status_change(self, result: CheckResult):
        """通知状态变化"""
        if self.notifier:
            status = "success" if result.success else "error"
            msg = f"""✅ **{result.target}** 恢复健康
- URL: {result.details.get('url', 'N/A')}
- 响应时间: {result.response_time_ms}ms
- 时间: {result.timestamp}""" if result.success else f"""❌ **{result.target}** 服务异常
- 错误: {result.error}
- 响应时间: {result.response_time_ms}ms
- 时间: {result.timestamp}"""
            
            await self.notifier.notify(result, {"message": msg, "status": status})
    
    def _update_stats(self, result: CheckResult):
        """更新统计"""
        name = result.target
        if name not in self.stats:
            self.stats[name] = {
                "total": 0,
                "success": 0,
                "fail": 0,
                "avg_response_time": 0,
                "last_success": None,
                "last_fail": None,
            }
        
        stats = self.stats[name]
        stats["total"] += 1
        if result.success:
            stats["success"] += 1
            stats["last_success"] = result.timestamp
        else:
            stats["fail"] += 1
            stats["last_fail"] = result.timestamp
        
        # 计算平均响应时间
        if stats["total"] > 1:
            stats["avg_response_time"] = (
                (stats["avg_response_time"] * (stats["total"] - 1) + result.response_time_ms)
                / stats["total"]
            )
        else:
            stats["avg_response_time"] = result.response_time_ms
    
    async def run(self):
        """运行监控"""
        self.running = True
        
        def signal_handler(sig, frame):
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        
        while self.running:
            await self.run_check_cycle()
            await asyncio.sleep(1)


class WatchDogCLI:
    """WatchDog CLI主类"""
    
    def __init__(self):
        self.targets: List[MonitorTarget] = []
        self.notifier = NotificationHandler()
        self.engine: Optional[MonitorEngine] = None
    
    def add_target(self, target: MonitorTarget):
        self.targets.append(target)
    
    def add_feishu_webhook(self, webhook: str):
        self.notifier.add_handler(Feishunotifier(webhook))
    
    async def run(self):
        """运行"""
        self.engine = MonitorEngine(self.targets, self.notifier)
        await self.engine.run()


def parse_config(config_path: str) -> Dict:
    """解析配置文件"""
    with open(config_path, 'r') as f:
        if config_path.endswith('.yaml') or config_path.endswith('.yml'):
            import yaml
            return yaml.safe_load(f)
        else:
            return json.load(f)


def main():
    parser = argparse.ArgumentParser(description='WatchDog Pro - 分布式API监控系统')
    parser.add_argument('--config', '-c', help='配置文件')
    parser.add_argument('--url', '-u', help='监控URL')
    parser.add_argument('--name', '-n', help='名称')
    parser.add_argument('--type', '-t', default='http', choices=['http', 'https', 'tcp', 'dns', 'ssl'])
    parser.add_argument('--interval', '-i', type=int, default=60)
    parser.add_argument('--timeout', default=10, type=int)
    parser.add_argument('--feishu', '-f', help='飞书webhook')
    parser.add_argument('--status', action='store_true', help='显示状态')
    
    args = parser.parse_args()
    
    cli = WatchDogCLI()
    
    if args.config:
        config = parse_config(args.config)
        
        # 加载目标
        for t in config.get('targets', []):
            target = MonitorTarget(
                name=t['name'],
                url=t['url'],
                check_type=CheckType(t.get('type', 'http')),
                interval=t.get('interval', 60),
                timeout=t.get('timeout', 10),
                expected_status=t.get('expected_status', 200),
            )
            cli.add_target(target)
        
        # 加载飞书
        if config.get('feishu_webhook'):
            cli.add_feishu_webhook(config['feishu_webhook'])
    elif args.url:
        target = MonitorTarget(
            name=args.name or args.url,
            url=args.url,
            check_type=CheckType(args.type),
            interval=args.interval,
            timeout=args.timeout,
        )
        cli.add_target(target)
        
        if args.feishu:
            cli.add_feishu_webhook(args.feishu)
    else:
        parser.error("请提供 --config 或 --url")
    
    # 运行
    print(f"🚀 WatchDog Pro 启动")
    print(f"   监控目标: {len(cli.targets)} 个")
    print(f"   按 Ctrl+C 停止\n")
    
    asyncio.run(cli.run())


if __name__ == '__main__':
    main()
