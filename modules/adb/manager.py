"""ADB管理器 — 基于 adb-shell 库实现"""

import os
import socket
import time
import threading
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field

try:
    from adb_shell.adb_device import AdbDeviceTcp
    from adb_shell.auth.sign_pythonrsa import PythonRSASigner
    try:
        from adb_shell.keygen import keygen
    except ImportError:
        try:
            from adb_shell.tools import keygen
        except ImportError:
            keygen = None
    ADB_SHELL_AVAILABLE = True
except ImportError:
    ADB_SHELL_AVAILABLE = False


# ======================== 数据模型 ========================

@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str
    ip: str
    port: int
    status: str          # CONNECTED, DISCONNECTED, FOUND, USB_DEVICE, ERROR
    model: str = ""
    version: str = ""
    manufacturer: str = ""


@dataclass
class DeviceStatus:
    """设备状态"""
    device_id: str
    status: str
    error_message: str = ""
    last_connected: Optional[float] = None


# ======================== ADB 管理器 ========================

class ADBManager:
    """ADB管理器 — 通过 adb-shell 库与设备通信"""

    # 默认 ADB 密钥路径
    ADB_KEY_DIR = os.path.expanduser("~/.android")
    ADB_KEY_PATH = os.path.join(ADB_KEY_DIR, "adbkey")

    def __init__(self):
        self.devices: Dict[str, Dict[str, Any]] = {}  # device_id -> {device: AdbDeviceTcp, info: DeviceInfo, ...}
        self.device_groups: Dict[str, List[str]] = {}
        self.device_tags: Dict[str, List[str]] = {}
        self._lock = threading.Lock()
        self._signer = None

        if ADB_SHELL_AVAILABLE:
            self._load_or_generate_keys()
        else:
            print("[ADBManager] 警告: adb-shell 未安装，请执行: pip install adb-shell")

    # ==================== 密钥管理 ====================

    def _load_or_generate_keys(self):
        """加载或生成 ADB RSA 密钥"""
        if not os.path.exists(self.ADB_KEY_DIR):
            try:
                os.makedirs(self.ADB_KEY_DIR, exist_ok=True)
            except OSError as e:
                print(f"[ADBManager] 创建密钥目录失败: {e}")
                return

        # 如果密钥不存在则生成
        if not os.path.exists(self.ADB_KEY_PATH):
            if keygen:
                try:
                    keygen(self.ADB_KEY_PATH)
                    print(f"[ADBManager] 已生成 ADB 密钥: {self.ADB_KEY_PATH}")
                except Exception as e:
                    print(f"[ADBManager] 生成密钥失败: {e}")
                    return
            else:
                print("[ADBManager] keygen 不可用，留空 signer")
                return

        # 加载密钥
        try:
            with open(self.ADB_KEY_PATH) as f:
                priv = f.read()
            with open(self.ADB_KEY_PATH + ".pub") as f:
                pub = f.read()
            self._signer = PythonRSASigner(pub, priv)
        except Exception as e:
            print(f"[ADBManager] 加载 ADB 密钥失败: {e}")
            self._signer = None

    # ==================== 设备发现 ====================

    def list_devices(self) -> List[DeviceInfo]:
        """
        列出所有已连接的设备。
        通过系统 adb devices 发现设备（adb-shell 无内置设备发现 API）。
        """
        devices = []
        try:
            import subprocess
            result = subprocess.run(
                ['adb', 'devices', '-l'],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode != 0:
                return devices

            for line in result.stdout.strip().split('\n')[1:]:
                if not line.strip():
                    continue
                parts = line.split()
                if len(parts) < 2:
                    continue
                device_id = parts[0]
                status = parts[1]

                if status != 'device':
                    continue

                # 解析 -l 输出的详细信息（可选）
                model = "Unknown"
                version = "Unknown"
                manufacturer = ""
                for token in parts[2:]:
                    if token.startswith("model:"):
                        model = token.split(":", 1)[1].replace("_", " ")
                    elif token.startswith("version:"):
                        version = token.split(":", 1)[1]

                if ':' in device_id:
                    ip, port_str = device_id.split(':')
                    port = int(port_str)
                    info = DeviceInfo(
                        device_id=device_id, ip=ip, port=port,
                        status="FOUND", model=model, version=version,
                        manufacturer=manufacturer
                    )
                else:
                    info = DeviceInfo(
                        device_id=device_id, ip="localhost", port=5555,
                        status="USB_DEVICE", model=model, version=version,
                        manufacturer=manufacturer
                    )
                devices.append(info)
        except Exception as e:
            print(f"[ADBManager] 设备发现失败: {e}")
        return devices

    # ==================== 连接 / 断开 ====================

    def connect(self, ip: str, port: int, auth_timeout_s: int = 10) -> bool:
        """
        通过 adb-shell 的 AdbDeviceTcp 连接设备。
        替代: adb connect <ip>:<port>
        """
        if not ADB_SHELL_AVAILABLE:
            print("[ADBManager] 错误: adb-shell 未安装")
            return False

        device_id = f"{ip}:{port}"
        with self._lock:
            if device_id in self.devices:
                existing = self.devices[device_id]
                if existing['info'].status == "CONNECTED":
                    print(f"[ADBManager] 设备 {device_id} 已连接")
                    return True

        try:
            device = AdbDeviceTcp(ip, port)
            device.connect(
                rsa_keys=[self._signer] if self._signer else [],
                auth_timeout_s=auth_timeout_s
            )

            # 连接成功后获取设备属性
            model = "Unknown"
            version = "Unknown"
            manufacturer = ""
            try:
                model = device.shell("getprop ro.product.model").strip()
                version = device.shell("getprop ro.build.version.release").strip()
                manufacturer = device.shell("getprop ro.product.manufacturer").strip()
            except Exception:
                pass

            info = DeviceInfo(
                device_id=device_id, ip=ip, port=port,
                status="CONNECTED", model=model,
                version=version, manufacturer=manufacturer
            )

            with self._lock:
                self.devices[device_id] = {
                    'device': device,
                    'info': info,
                    'last_connected': time.time()
                }
            print(f"[ADBManager] ✅ 连接成功: {device_id} ({model})")
            return True

        except Exception as e:
            print(f"[ADBManager] ❌ 连接失败 {ip}:{port}: {e}")
            return False

    def disconnect(self, device_id: str) -> bool:
        """断开设备连接"""
        with self._lock:
            entry = self.devices.pop(device_id, None)
        if entry is None:
            print(f"[ADBManager] 设备 {device_id} 未连接")
            return False

        try:
            device: AdbDeviceTcp = entry['device']
            device.close()
            print(f"[ADBManager] ✅ 已断开: {device_id}")
        except Exception as e:
            print(f"[ADBManager] 断开 {device_id} 时出错: {e}")
        return True

    # ==================== 状态查询 ====================

    def get_status(self, device_id: str) -> DeviceStatus:
        """获取设备状态（含存活检测）"""
        with self._lock:
            entry = self.devices.get(device_id)

        if entry is None:
            return DeviceStatus(device_id, "DISCONNECTED", error_message="Device not found")

        # 存活检测：执行一个轻量命令
        try:
            device: AdbDeviceTcp = entry['device']
            device.shell("echo alive")
            status = "CONNECTED"
            error = ""
        except Exception as e:
            status = "ERROR"
            error = str(e)
            # 连接已断开，自动清理
            with self._lock:
                self.devices.pop(device_id, None)

        return DeviceStatus(
            device_id, status,
            error_message=error,
            last_connected=entry.get('last_connected')
        )

    def get_device_info(self, device_id: str) -> Optional[DeviceInfo]:
        """获取缓存的设备信息"""
        with self._lock:
            entry = self.devices.get(device_id)
        return entry['info'] if entry else None

    # ==================== Shell 命令执行 ====================

    def execute_command(self, device_id: str, command: str) -> str:
        """在设备上执行 shell 命令"""
        device = self._get_device(device_id)
        if device is None:
            return f"Error: Device {device_id} not connected"

        try:
            result = device.shell(command)
            # shell() 返回 str 或 bytes，统一为 str
            return result if isinstance(result, str) else result.decode('utf-8', errors='replace')
        except Exception as e:
            return f"Error: {e}"

    def execute_command_with_timeout(self, device_id: str, command: str, timeout_s: int = 30) -> str:
        """带超时的 shell 命令执行"""
        device = self._get_device(device_id)
        if device is None:
            return f"Error: Device {device_id} not connected"

        original_timeout = device.default_timeout_ms
        try:
            device.default_timeout_ms = timeout_s * 1000
            result = device.shell(command)
            return result if isinstance(result, str) else result.decode('utf-8', errors='replace')
        except Exception as e:
            return f"Error (timeout={timeout_s}s): {e}"
        finally:
            device.default_timeout_ms = original_timeout

    # ==================== 文件操作 ====================

    def push_file(self, device_id: str, local_path: str, remote_path: str) -> bool:
        """推送文件到设备"""
        device = self._get_device(device_id)
        if device is None:
            return False
        try:
            device.push(local_path, remote_path)
            return True
        except Exception as e:
            print(f"[ADBManager] push 失败: {e}")
            return False

    def pull_file(self, device_id: str, remote_path: str, local_path: str) -> bool:
        """从设备拉取文件"""
        device = self._get_device(device_id)
        if device is None:
            return False
        try:
            data = device.pull(remote_path)
            # pull() 返回 bytes
            with open(local_path, 'wb') as f:
                f.write(data)
            return True
        except Exception as e:
            print(f"[ADBManager] pull 失败: {e}")
            return False

    # ==================== HCI 日志 ====================

    def start_hci_log(self, device_id: str) -> bool:
        """启用 btsnoop HCI 日志"""
        try:
            self.execute_command(device_id, "setprop persist.bluetooth.btsnooplogmode full")
            self.execute_command(device_id, "stop bluetooth")
            self.execute_command(device_id, "start bluetooth")
            return True
        except Exception as e:
            print(f"[ADBManager] 开启 HCI 日志失败: {e}")
            return False

    def stop_hci_log(self, device_id: str) -> bool:
        """禁用 btsnoop HCI 日志"""
        try:
            self.execute_command(device_id, "setprop persist.bluetooth.btsnooplogmode disable")
            self.execute_command(device_id, "stop bluetooth")
            self.execute_command(device_id, "start bluetooth")
            return True
        except Exception as e:
            print(f"[ADBManager] 停止 HCI 日志失败: {e}")
            return False

    def pull_hci_log(self, device_id: str, output_file: str) -> bool:
        """拉取 HCI 日志文件"""
        return self.pull_file(device_id, "/sdcard/btsnoop_hci.log", output_file)

    # ==================== 设备健康检查 ====================

    def check_device_health(self, device_id: str) -> dict:
        """检查设备健康状态"""
        health = {}
        try:
            health['battery'] = self.execute_command(device_id, "dumpsys battery")
            health['storage'] = self.execute_command(device_id, "df -h /data")
            health['memory'] = self.execute_command(device_id, "cat /proc/meminfo")
            health['uptime'] = self.execute_command(device_id, "uptime")
        except Exception as e:
            health['error'] = str(e)
        return health

    # ==================== APP 管理 ====================

    def list_apps(self, device_id: str, system_apps: bool = False, third_party: bool = False) -> str:
        """列出已安装 APP（通过 shell pm 命令）"""
        cmd = "pm list packages"
        if system_apps:
            cmd += " -s"
        elif third_party:
            cmd += " -3"
        return self.execute_command(device_id, cmd)

    def start_app(self, device_id: str, package_name: str, activity: str = None) -> str:
        """启动 APP"""
        if activity:
            cmd = f"am start -n {package_name}/{activity}"
        else:
            cmd = f"monkey -p {package_name} -c android.intent.category.LAUNCHER 1"
        return self.execute_command(device_id, cmd)

    def stop_app(self, device_id: str, package_name: str) -> str:
        """停止 APP"""
        return self.execute_command(device_id, f"am force-stop {package_name}")

    def install_app(self, device_id: str, apk_path: str, reinstall: bool = False) -> str:
        """
        安装 APP。
        注: adb-shell 无 install 协议 API，仍使用系统 adb 命令。
        """
        try:
            import subprocess
            cmd = ['adb', '-s', device_id, 'install']
            if reinstall:
                cmd.append('-r')
            cmd.append(apk_path)
            result = subprocess.run(cmd, capture_output=True, timeout=60)
            out = self._decode_output(result.stdout)
            err = self._decode_output(result.stderr)
            return out if result.returncode == 0 else f"安装失败: {err}"
        except subprocess.TimeoutExpired:
            return "安装超时 (60s)"
        except Exception as e:
            return f"安装失败: {e}"

    def uninstall_app(self, device_id: str, package_name: str, keep_data: bool = False) -> str:
        """卸载 APP"""
        try:
            import subprocess
            cmd = ['adb', '-s', device_id, 'uninstall']
            if keep_data:
                cmd.append('-k')
            cmd.append(package_name)
            result = subprocess.run(cmd, capture_output=True, timeout=30)
            out = self._decode_output(result.stdout)
            return f"卸载成功: {package_name}" if result.returncode == 0 else f"卸载失败: {out}"
        except Exception as e:
            return f"卸载失败: {e}"

    # ==================== APP 命令通信 ====================

    def send_app_command(self, device_id: str, package_name: str, command: str,
                         args: str = "", callback_id: str = None, action: str = None) -> str:
        """发送命令给指定 APP（通过 am broadcast）"""
        import uuid
        if callback_id is None:
            callback_id = str(uuid.uuid4())[:8]
        if action is None:
            action = f"{package_name}.ACTION_EXECUTE_COMMAND"

        cmd = (
            f"am broadcast -a {action} "
            f"--es command '{command}' "
            f"--es args '{args}' "
            f"--es callback_id '{callback_id}'"
        )
        result = self.execute_command(device_id, cmd)
        return f"命令已发送，回调ID: {callback_id}" if "Broadcast completed" in result else f"发送失败: {result}"

    def get_app_result(self, device_id: str,
                       result_file: str = "/sdcard/myapp_command_result.txt",
                       local_file: str = None) -> str:
        """获取 APP 执行结果"""
        # 检查文件是否存在
        check = self.execute_command(device_id, f"ls {result_file} 2>/dev/null && echo OK")
        if "OK" not in check:
            return f"结果文件不存在: {result_file}"

        if local_file:
            if self.pull_file(device_id, result_file, local_file):
                try:
                    with open(local_file, 'r', encoding='utf-8') as f:
                        return f.read()
                except Exception as e:
                    return f"读取本地文件失败: {e}"
            return "拉取文件失败"
        else:
            return self.execute_command(device_id, f"cat {result_file}")

    def app_command_with_result(self, device_id: str, package_name: str, command: str,
                                args: str = "", action: str = None,
                                result_file: str = "/sdcard/myapp_command_result.txt",
                                wait_ms: int = 1000) -> str:
        """发送命令并获取结果（完整流程）"""
        send_result = self.send_app_command(device_id, package_name, command, args, action=action)
        if wait_ms > 0:
            time.sleep(wait_ms / 1000)
        return self.get_app_result(device_id, result_file)

    # ==================== 设备分组 / 标签 ====================

    def add_device_to_group(self, device_id: str, group_name: str) -> bool:
        with self._lock:
            if device_id not in self.devices:
                return False
            self.device_groups.setdefault(group_name, [])
            if device_id not in self.device_groups[group_name]:
                self.device_groups[group_name].append(device_id)
        return True

    def remove_device_from_group(self, device_id: str, group_name: str) -> bool:
        with self._lock:
            if group_name not in self.device_groups:
                return False
            if device_id in self.device_groups[group_name]:
                self.device_groups[group_name].remove(device_id)
        return True

    def get_devices_in_group(self, group_name: str) -> List[str]:
        with self._lock:
            return list(self.device_groups.get(group_name, []))

    def get_all_groups(self) -> Dict[str, List[str]]:
        with self._lock:
            return {k: list(v) for k, v in self.device_groups.items()}

    def add_tag_to_device(self, device_id: str, tag: str) -> bool:
        with self._lock:
            if device_id not in self.devices:
                return False
            self.device_tags.setdefault(device_id, [])
            if tag not in self.device_tags[device_id]:
                self.device_tags[device_id].append(tag)
        return True

    def remove_tag_from_device(self, device_id: str, tag: str) -> bool:
        with self._lock:
            if device_id not in self.device_tags:
                return False
            if tag in self.device_tags[device_id]:
                self.device_tags[device_id].remove(tag)
        return True

    def get_device_tags(self, device_id: str) -> List[str]:
        with self._lock:
            return list(self.device_tags.get(device_id, []))

    # ==================== 自动连接 ====================

    def auto_connect(self, subnet: str = "192.168.1", port: int = 5555) -> List[str]:
        """扫描子网并自动连接设备"""
        connected = []
        for i in range(1, 255):
            ip = f"{subnet}.{i}"
            try:
                with socket.create_connection((ip, port), timeout=0.05):
                    if self.connect(ip, port):
                        connected.append(f"{ip}:{port}")
            except (socket.timeout, ConnectionRefusedError, OSError):
                pass
        return connected

    # ==================== 错误码 ====================

    def get_error_code(self, error_message: str) -> int:
        codes = {
            "Device not found": 1001,
            "Connection failed": 1002,
            "Command execution failed": 1003,
            "Permission denied": 1004,
            "Timeout": 1005,
        }
        for key, code in codes.items():
            if key in error_message:
                return code
        return 9999

    # ==================== 内部辅助 ====================

    def _get_device(self, device_id: str) -> Optional[AdbDeviceTcp]:
        """获取 AdbDeviceTcp 实例（线程安全）"""
        with self._lock:
            entry = self.devices.get(device_id)
            if entry is None:
                return None
            return entry.get('device')

    @staticmethod
    def _decode_output(data: bytes) -> str:
        """尝试多编码解码"""
        for encoding in ('utf-8', 'gbk', 'latin-1'):
            try:
                return data.decode(encoding, errors='replace')
            except (UnicodeDecodeError, LookupError):
                continue
        return str(data)

    # ==================== 清理 ====================

    def disconnect_all(self):
        """断开所有已连接的设备"""
        with self._lock:
            device_ids = list(self.devices.keys())
        for did in device_ids:
            self.disconnect(did)
