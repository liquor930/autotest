"""ADB管理器"""

import socket
import time
import os
from typing import List, Optional
from dataclasses import dataclass

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
except ImportError as e:
    print(f"警告: adb-shell 依赖项未安装: {e}")
    print("请运行: pip install adb-shell")
    ADB_SHELL_AVAILABLE = False


@dataclass
class DeviceInfo:
    """设备信息"""
    device_id: str
    ip: str
    port: int
    status: str  # CONNECTED, DISCONNECTED, ERROR
    model: str = ""
    version: str = ""


@dataclass
class DeviceStatus:
    """设备状态"""
    device_id: str
    status: str
    error_message: str = ""
    last_connected: Optional[float] = None


@dataclass
class CommandResult:
    """命令结果"""
    success: bool
    output: str
    error: str


class ADBManager:
    """ADB管理器"""

    def __init__(self):
        """初始化ADB管理器"""
        print("开始初始化ADB管理器...")
        self.devices = {}
        self.device_groups = {}  # 设备分组
        self.device_tags = {}  # 设备标签
        print("ADB_SHELL_AVAILABLE:", ADB_SHELL_AVAILABLE)
        # 暂时注释掉_setup_adb_keys方法的调用，避免可能的阻塞
        # if ADB_SHELL_AVAILABLE:
        #     print("调用_setup_adb_keys方法...")
        #     self._setup_adb_keys()
        # else:
        #     print("警告: adb-shell 依赖项未安装，部分功能可能无法使用")
        #     print("请运行: pip install adb-shell")
        print("ADB管理器初始化完成")

    def _setup_adb_keys(self):
        """设置ADB密钥"""
        import os
        
        # 生成ADB密钥
        key_path = os.path.expanduser("~/.android/adbkey")
        key_dir = os.path.dirname(key_path)
        
        # 确保目录存在
        if not os.path.exists(key_dir):
            try:
                os.makedirs(key_dir)
                print(f"创建目录: {key_dir}")
            except Exception as e:
                print(f"创建目录失败: {e}")
                return
        
        # 生成密钥
        try:
            keygen(key_path)
            print(f"生成ADB密钥: {key_path}")
        except Exception as e:
            # 密钥可能已经存在，忽略错误
            print(f"生成密钥时出错（可能已存在）: {e}")
        
        # 加载密钥
        try:
            with open(key_path, 'r') as f:
                priv = f.read()
            with open(key_path + '.pub', 'r') as f:
                pub = f.read()
            
            self.signer = PythonRSASigner(pub, priv)
            print("ADB密钥加载成功")
        except Exception as e:
            print(f"加载ADB密钥失败: {e}")
            print("请确保已正确安装ADB并生成了密钥")
            print("可以通过执行 'adb devices' 命令生成密钥")
            # 设置一个空的signer，避免后续操作失败
            self.signer = None

    def list_devices(self) -> List[DeviceInfo]:
        """列出所有可连接的设备"""
        devices = []
        
        print("开始列出设备...")
        
        # 直接运行adb devices命令
        print("运行adb devices命令...")
        try:
            import subprocess
            result = subprocess.run('adb devices', shell=True, capture_output=True, text=True, timeout=5)
            print(f"返回码: {result.returncode}")
            print(f"输出: {result.stdout}")
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                print(f"解析到的行: {lines}")
                if len(lines) > 1:
                    for line in lines[1:]:
                        if line.strip():
                            parts = line.split('\t')
                            print(f"设备信息: {parts}")
                            if len(parts) >= 2 and parts[1] == 'device':
                                device_id = parts[0]
                                print(f"找到设备: {device_id}")
                                
                                # 为所有设备创建基本信息
                                if ':' in device_id:
                                    # WiFi设备
                                    ip, port_str = device_id.split(':')
                                    port = int(port_str)
                                    device_info = DeviceInfo(
                                        device_id=device_id,
                                        ip=ip,
                                        port=port,
                                        status="FOUND",
                                        model="Unknown",
                                        version="Unknown"
                                    )
                                else:
                                    # USB设备
                                    device_info = DeviceInfo(
                                        device_id=device_id,
                                        ip="localhost",
                                        port=5555,
                                        status="USB_DEVICE",
                                        model="Unknown",
                                        version="Unknown"
                                    )
                                
                                # 添加设备到列表
                                devices.append(device_info)
                                print(f"已添加设备: {device_id}")
        except Exception as e:
            print(f"执行adb devices命令失败: {e}")
            import traceback
            traceback.print_exc()
        
        # 打印结果
        print(f"最终找到的设备数量: {len(devices)}")
        for device in devices:
            print(f"设备: {device.device_id}, 状态: {device.status}")
        
        return devices
    
    def auto_connect(self) -> List[str]:
        """自动发现并连接设备"""
        if not ADB_SHELL_AVAILABLE:
            print("错误: adb-shell 依赖项未安装，无法执行此操作")
            return []
        
        connected_devices = []
        
        # 扫描并连接设备
        for ip in self._scan_network('192.168.1.0/24'):
            try:
                if self.connect(ip, 5555):
                    device_id = f"{ip}:5555"
                    connected_devices.append(device_id)
                    print(f"自动连接成功: {device_id}")
            except Exception as e:
                print(f"自动连接 {ip}:5555 失败: {e}")
        
        return connected_devices

    def _scan_network(self, network):
        """扫描网络"""
        # 简单的网络扫描实现
        base_ip = network.split('/')[0].rsplit('.', 1)[0]
        ips = []
        
        # 扫描192.168.1.1-192.168.1.254
        for i in range(1, 255):
            ip = f"{base_ip}.{i}"
            if self._ping(ip):
                ips.append(ip)
        
        return ips

    def _ping(self, ip):
        """Ping设备"""
        try:
            socket.create_connection((ip, 5555), timeout=0.1)
            return True
        except:
            return False

    def _generate_key(self, key_path):
        """生成ADB密钥"""
        if keygen:
            keygen(key_path)
        else:
            from cryptography.hazmat.primitives.asymmetric import rsa
            from cryptography.hazmat.primitives import serialization
            from cryptography.hazmat.backends import default_backend
            
            private_key = rsa.generate_private_key(
                public_exponent=65537,
                key_size=2048,
                backend=default_backend()
            )
            
            pem_private = private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            
            public_key = private_key.public_key()
            pem_public = public_key.public_bytes(
                encoding=serialization.Encoding.OpenSSH,
                format=serialization.PublicFormat.OpenSSH
            )
            
            with open(key_path, 'wb') as f:
                f.write(pem_private)
            with open(key_path + '.pub', 'wb') as f:
                f.write(pem_public)

    def connect(self, ip: str, port: int) -> bool:
        """连接指定设备"""
        print(f"尝试连接设备 {ip}:{port}...")
        
        try:
            import subprocess
            
            result = subprocess.run(
                ['adb', 'connect', f'{ip}:{port}'],
                capture_output=True,
                timeout=30
            )
            
            try:
                stdout = result.stdout.decode('utf-8', errors='ignore')
            except:
                try:
                    stdout = result.stdout.decode('gbk', errors='ignore')
                except:
                    stdout = str(result.stdout)
            
            try:
                stderr = result.stderr.decode('utf-8', errors='ignore')
            except:
                try:
                    stderr = result.stderr.decode('gbk', errors='ignore')
                except:
                    stderr = str(result.stderr)
            
            print(f"adb connect 命令返回码: {result.returncode}")
            print(f"adb connect 输出: {stdout}")
            if stderr:
                print(f"adb connect 错误: {stderr}")
            
            if result.returncode == 0 and ("connected" in stdout or "connected" in stderr):
                device_id = f"{ip}:{port}"
                device_info = DeviceInfo(
                    device_id=device_id,
                    ip=ip,
                    port=port,
                    status="CONNECTED",
                    model="Unknown",
                    version="Unknown"
                )
                self.devices[device_id] = {
                    'device': None,
                    'info': device_info,
                    'last_connected': time.time()
                }
                print(f"连接成功")
                return True
            else:
                print(f"连接失败")
                return False
                
        except subprocess.TimeoutExpired:
            print("连接超时")
            return False
        except Exception as e:
            print(f"连接失败: {e}")
            return False

    def disconnect(self, device_id: str) -> bool:
        """断开与指定设备的连接"""
        try:
            import subprocess
            
            result = subprocess.run(
                ['adb', 'disconnect', device_id],
                capture_output=True,
                timeout=10
            )
            
            try:
                stdout = result.stdout.decode('utf-8', errors='ignore')
            except:
                try:
                    stdout = result.stdout.decode('gbk', errors='ignore')
                except:
                    stdout = str(result.stdout)
            
            print(f"adb disconnect 命令返回码: {result.returncode}")
            print(f"adb disconnect 输出: {stdout}")
            
            if device_id in self.devices:
                del self.devices[device_id]
            
            return result.returncode == 0
        except Exception as e:
            print(f"断开连接失败: {e}")
            if device_id in self.devices:
                del self.devices[device_id]
            return False

    def get_status(self, device_id: str) -> DeviceStatus:
        """获取设备状态"""
        if device_id in self.devices:
            device_info = self.devices[device_id]['info']
            return DeviceStatus(
                device_id=device_id,
                status=device_info.status,
                last_connected=self.devices[device_id].get('last_connected')
            )
        else:
            return DeviceStatus(
                device_id=device_id,
                status="DISCONNECTED",
                error_message="Device not found"
            )

    def execute_command(self, device_id: str, command: str) -> str:
        """在指定设备上执行命令"""
        try:
            import subprocess
            
            result = subprocess.run(
                ['adb', '-s', device_id, 'shell', command],
                capture_output=True,
                timeout=30
            )
            
            try:
                stdout = result.stdout.decode('utf-8', errors='ignore')
            except:
                try:
                    stdout = result.stdout.decode('gbk', errors='ignore')
                except:
                    stdout = str(result.stdout)
            
            try:
                stderr = result.stderr.decode('utf-8', errors='ignore')
            except:
                try:
                    stderr = result.stderr.decode('gbk', errors='ignore')
                except:
                    stderr = str(result.stderr)
            
            if result.returncode == 0:
                return stdout
            else:
                return f"Error: {stderr}"
        except subprocess.TimeoutExpired:
            return "Error: Command timeout"
        except Exception as e:
            return f"Error: {str(e)}"

    def start_hci_log(self, device_id: str) -> bool:
        """开始采集HCI日志"""
        try:
            # 启用HCI日志
            self.execute_command(device_id, 'setprop persist.bluetooth.btsnooplogmode full')
            self.execute_command(device_id, 'stop bluetooth')
            self.execute_command(device_id, 'start bluetooth')
            return True
        except Exception as e:
            print(f"开始采集HCI日志失败: {e}")
            return False

    def stop_hci_log(self, device_id: str) -> bool:
        """停止采集HCI日志"""
        try:
            # 禁用HCI日志
            self.execute_command(device_id, 'setprop persist.bluetooth.btsnooplogmode disable')
            self.execute_command(device_id, 'stop bluetooth')
            self.execute_command(device_id, 'start bluetooth')
            return True
        except Exception as e:
            print(f"停止采集HCI日志失败: {e}")
            return False

    def pull_hci_log(self, device_id: str, output_file: str) -> bool:
        """拉取HCI日志文件"""
        try:
            import subprocess
            
            result = subprocess.run(
                ['adb', '-s', device_id, 'pull', '/sdcard/btsnoop_hci.log', output_file],
                capture_output=True,
                timeout=60
            )
            
            try:
                stdout = result.stdout.decode('utf-8', errors='ignore')
            except:
                try:
                    stdout = result.stdout.decode('gbk', errors='ignore')
                except:
                    stdout = str(result.stdout)
            
            try:
                stderr = result.stderr.decode('utf-8', errors='ignore')
            except:
                try:
                    stderr = result.stderr.decode('gbk', errors='ignore')
                except:
                    stderr = str(result.stderr)
            
            print(f"adb pull 命令返回码: {result.returncode}")
            print(f"adb pull 输出: {stdout}")
            if stderr:
                print(f"adb pull 错误: {stderr}")
            
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print("拉取日志超时")
            return False
        except Exception as e:
            print(f"拉取日志失败: {e}")
            return False
    
    def add_device_to_group(self, device_id: str, group_name: str):
        """添加设备到分组"""
        if device_id not in self.devices:
            print(f"错误: 设备 {device_id} 未连接")
            return False
        
        if group_name not in self.device_groups:
            self.device_groups[group_name] = []
        
        if device_id not in self.device_groups[group_name]:
            self.device_groups[group_name].append(device_id)
        
        return True
    
    def remove_device_from_group(self, device_id: str, group_name: str):
        """从分组中移除设备"""
        if group_name not in self.device_groups:
            print(f"错误: 分组 {group_name} 不存在")
            return False
        
        if device_id in self.device_groups[group_name]:
            self.device_groups[group_name].remove(device_id)
        
        return True
    
    def get_devices_in_group(self, group_name: str) -> List[str]:
        """获取分组中的设备"""
        if group_name not in self.device_groups:
            return []
        
        return self.device_groups[group_name]
    
    def add_tag_to_device(self, device_id: str, tag: str):
        """添加标签到设备"""
        if device_id not in self.devices:
            print(f"错误: 设备 {device_id} 未连接")
            return False
        
        if device_id not in self.device_tags:
            self.device_tags[device_id] = []
        
        if tag not in self.device_tags[device_id]:
            self.device_tags[device_id].append(tag)
        
        return True
    
    def remove_tag_from_device(self, device_id: str, tag: str):
        """从设备中移除标签"""
        if device_id not in self.device_tags:
            return False
        
        if tag in self.device_tags[device_id]:
            self.device_tags[device_id].remove(tag)
        
        return True
    
    def get_device_tags(self, device_id: str) -> List[str]:
        """获取设备的标签"""
        if device_id not in self.device_tags:
            return []
        
        return self.device_tags[device_id]
    
    def check_device_health(self, device_id: str) -> dict:
        """检查设备健康状态"""
        health_info = {}
        
        try:
            # 检查电池状态
            battery_info = self.execute_command(device_id, 'dumpsys battery')
            health_info['battery'] = battery_info
            
            # 检查存储空间
            storage_info = self.execute_command(device_id, 'df -h')
            health_info['storage'] = storage_info
            
            # 检查内存使用
            memory_info = self.execute_command(device_id, 'free -m')
            health_info['memory'] = memory_info
            
            # 检查CPU使用
            cpu_info = self.execute_command(device_id, 'top -n 1')
            health_info['cpu'] = cpu_info
            
        except Exception as e:
            health_info['error'] = str(e)
        
        return health_info
    
    def get_error_code(self, error_message: str) -> int:
        """获取错误码"""
        error_codes = {
            "Device not found": 1001,
            "Connection failed": 1002,
            "Command execution failed": 1003,
            "Permission denied": 1004,
            "Timeout": 1005,
        }
        
        for key, code in error_codes.items():
            if key in error_message:
                return code
        
        return 9999  # 未知错误
