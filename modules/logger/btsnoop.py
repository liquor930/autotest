"""
Btsnoop HCI 日志解析器

解析 Android 生成的 btsnoop_hci.log（btsnoop 格式），
提取 HCI 命令/事件/数据包，归类分析。

Btsnoop 文件格式:
    - Header (16 bytes): identification (8) + version (4) + datalink_type (4)
    - Packet records: length (4) + original_length (4) + timestamp (8) + data

HCI data link types:
    1002: HCI UART (H4)
    1003: HCI BCSP
    1004: HCI UART (H4) with timestamp
"""

import struct
from datetime import datetime, timedelta
from typing import List, Iterator, Tuple, Optional

from core.models import LogEntry, LogLevel, LogStatistics, KeyEvent, LogParserResult


# ==================== 常量 ====================

BTSNOOP_ID = b'btsnoop\x00'
BTSNOOP_VERSION = 1

# HCI 数据链路类型
DATA_LINK_HCI_UART = 1002       # H4: cmd/event/data
DATA_LINK_HCI_UART_TS = 1004    # H4 with timestamp

# HCI 包类型（H4）
H4_CMD      = 0x01
H4_ACL_DATA = 0x02
H4_SCO_DATA = 0x03
H4_EVENT    = 0x04
H4_ISO_DATA = 0x05

H4_TYPE_NAMES = {
    H4_CMD:      "CMD",
    H4_ACL_DATA: "ACL",
    H4_SCO_DATA: "SCO",
    H4_EVENT:    "EVT",
    H4_ISO_DATA: "ISO",
}

# HCI 命令 OGF (Opcode Group Field)
OGF_LINK_CONTROL     = 0x01
OGF_LINK_POLICY      = 0x02
OGF_CONTROLLER_BB    = 0x03
OGF_INFORMATIONAL    = 0x04
OGF_STATUS           = 0x05
OGF_LE_CONTROLLER    = 0x08

OGF_NAMES = {
    OGF_LINK_CONTROL:    "Link_Control",
    OGF_LINK_POLICY:     "Link_Policy",
    OGF_CONTROLLER_BB:   "Controller_BB",
    OGF_INFORMATIONAL:   "Informational",
    OGF_STATUS:          "Status",
    OGF_LE_CONTROLLER:   "LE_Controller",
}

# 关键 HCI 事件码
EVT_INQUIRY_COMPLETE         = 0x01
EVT_INQUIRY_RESULT           = 0x02
EVT_CONNECTION_COMPLETE      = 0x03
EVT_CONNECTION_REQUEST       = 0x04
EVT_DISCONNECTION_COMPLETE   = 0x05
EVT_AUTHENTICATION_COMPLETE  = 0x06
EVT_REMOTE_NAME_REQ_COMPLETE = 0x07
EVT_ENCRYPTION_CHANGE        = 0x08
EVT_LE_META                  = 0x3E

EVT_NAMES = {
    EVT_INQUIRY_COMPLETE:        "Inquiry_Complete",
    EVT_INQUIRY_RESULT:          "Inquiry_Result",
    EVT_CONNECTION_COMPLETE:     "Connection_Complete",
    EVT_CONNECTION_REQUEST:      "Connection_Request",
    EVT_DISCONNECTION_COMPLETE:  "Disconnection_Complete",
    EVT_AUTHENTICATION_COMPLETE: "Authentication_Complete",
    EVT_REMOTE_NAME_REQ_COMPLETE: "Remote_Name_Request_Complete",
    EVT_ENCRYPTION_CHANGE:       "Encryption_Change",
    EVT_LE_META:                 "LE_Meta",
}

# LE 子事件码
LE_CONNECTION_COMPLETE       = 0x01
LE_ADVERTISING_REPORT        = 0x02
LE_CONNECTION_UPDATE_COMPLETE = 0x03

LE_EVENT_NAMES = {
    LE_CONNECTION_COMPLETE:       "LE_Connection_Complete",
    LE_ADVERTISING_REPORT:        "LE_Advertising_Report",
    LE_CONNECTION_UPDATE_COMPLETE: "LE_Connection_Update_Complete",
}

# 连接状态
STATUS_SUCCESS = 0x00


def _mac_str(b: bytes) -> str:
    """bytes 转 MAC 地址字符串"""
    return ':'.join(f'{x:02x}' for x in reversed(b))


class BtsnoopParser:
    """
    Btsnoop HCI 日志解析器

    用法:
        parser = BtsnoopParser()
        result = parser.parse('btsnoop_hci.log')
        print(result.statistics)
    """

    def parse(self, file_path: str) -> LogParserResult:
        """解析 btsnoop 文件，返回 LogParserResult"""
        try:
            with open(file_path, 'rb') as f:
                raw = f.read()
        except FileNotFoundError:
            return LogParserResult(log_type="btsnoop_hci", error_count=1)

        result = LogParserResult(log_type="btsnoop_hci")
        if len(raw) < 16:
            result.error_count = 1
            result.entries.append(LogEntry(
                level=LogLevel.ERROR, message="File too small for btsnoop header"
            ))
            return result

        # --- 解析 Header ---
        header = raw[:16]
        ident = header[:8]
        version = struct.unpack('>I', header[8:12])[0]
        datalink = struct.unpack('>I', header[12:16])[0]

        if ident != BTSNOOP_ID:
            result.error_count = 1
            result.entries.append(LogEntry(
                level=LogLevel.ERROR, message=f"Invalid btsnoop header: {ident[:4]}"
            ))
            return result

        result.entries.append(LogEntry(
            level=LogLevel.INFO,
            message=f"Btsnoop version={version}, datalink_type={datalink} ({_datalink_name(datalink)})"
        ))

        # --- 解析 Packet Records ---
        pos = 16
        packet_count = 0
        error_packets = 0
        cmd_count = acl_count = sco_count = evt_count = 0
        disconnections = 0
        auth_failures = 0
        key_events = []

        while pos + 24 <= len(raw):
            # Packet header: original_length(4) + included_length(4) + flags(4) + cum_drops(4) + ts_sec(4) + ts_usec(4)
            orig_len = struct.unpack('>I', raw[pos:pos+4])[0]
            incl_len = struct.unpack('>I', raw[pos+4:pos+8])[0]
            flags = struct.unpack('>I', raw[pos+8:pos+12])[0]
            _cum_drops = struct.unpack('>I', raw[pos+12:pos+16])[0]
            ts_sec = struct.unpack('>I', raw[pos+16:pos+20])[0]
            ts_usec = struct.unpack('>I', raw[pos+20:pos+24])[0]

            pos += 24
            packet_data = raw[pos:pos+incl_len]
            pos += incl_len
            packet_count += 1

            ts = datetime(1970, 1, 1) + timedelta(seconds=ts_sec, microseconds=ts_usec)

            if not packet_data:
                continue

            h4_type = packet_data[0]
            payload = packet_data[1:] if len(packet_data) > 1 else b''

            if h4_type == H4_CMD:
                cmd_count += 1
            elif h4_type == H4_ACL_DATA:
                acl_count += 1
            elif h4_type == H4_SCO_DATA:
                sco_count += 1
            elif h4_type == H4_EVENT:
                evt_count += 1
                self._parse_event(payload, ts, result.entries, key_events, disconnections, auth_failures)

        # --- 统计 ---
        stats = LogStatistics(
            total_entries=len(result.entries),
            error_count=result.error_count,
        )

        result.entries.append(LogEntry(
            level=LogLevel.INFO,
            message=f"Total packets: {packet_count} (CMD={cmd_count}, ACL={acl_count}, SCO={sco_count}, EVT={evt_count})"
        ))

        for evt in key_events:
            result.key_events.append(KeyEvent(
                timestamp=evt.get('ts', datetime.now()),
                event_type=evt.get('type', ''),
                details=evt,
            ))

        return result

    def _parse_event(self, payload: bytes, ts: datetime, entries: List, key_events: List, 
                     disconnections: int, auth_failures: int):
        """解析 HCI Event 包"""
        if not payload:
            return

        evt_code = payload[0]
        evt_name = EVT_NAMES.get(evt_code, f"Unknown(0x{evt_code:02x})")
        evt_params = payload[2:] if len(payload) >= 3 else b''

        msg = f"[{ts.strftime('%H:%M:%S.%f')}] HCI_EVT: {evt_name} (0x{evt_code:02x})"

        if evt_code == EVT_CONNECTION_COMPLETE and len(evt_params) >= 7:
            status = evt_params[0]
            handle = struct.unpack('<H', evt_params[1:3])[0]
            mac = _mac_str(evt_params[3:9]) if len(evt_params) >= 9 else "??"
            if status == STATUS_SUCCESS:
                msg += f" → Connected to {mac} (handle=0x{handle:04x})"
                key_events.append({'type': 'CONNECT', 'mac': mac, 'ts': ts})
            else:
                msg += f" → Connection FAILED ({mac}) status=0x{status:02x}"
                key_events.append({'type': 'CONNECT_FAIL', 'mac': mac, 'ts': ts})

        elif evt_code == EVT_DISCONNECTION_COMPLETE and len(evt_params) >= 4:
            status = evt_params[0]
            handle = struct.unpack('<H', evt_params[1:3])[0]
            reason = evt_params[3]
            msg += f" → Disconnected handle=0x{handle:04x} reason=0x{reason:02x}"
            key_events.append({'type': 'DISCONNECT', 'handle': handle, 'reason': reason, 'ts': ts})

        elif evt_code == EVT_INQUIRY_RESULT:
            if len(evt_params) >= 1:
                num = min(evt_params[0], (len(evt_params) - 1) // 14) if len(evt_params) >= 2 else 0
                msg += f" → Found {num} device(s)"
                key_events.append({'type': 'INQUIRY_RESULT', 'count': num, 'ts': ts})

        elif evt_code == EVT_AUTHENTICATION_COMPLETE:
            status = evt_params[0] if evt_params else 0xFF
            if status == STATUS_SUCCESS:
                msg += " → Authentication OK"
                key_events.append({'type': 'AUTH_SUCCESS', 'ts': ts})
            else:
                msg += f" → Authentication FAILED (status=0x{status:02x})"
                key_events.append({'type': 'AUTH_FAIL', 'ts': ts})

        elif evt_code == EVT_LE_META and len(evt_params) >= 1:
            sub_evt = evt_params[0]
            sub_name = LE_EVENT_NAMES.get(sub_evt, f"LE_Sub(0x{sub_evt:02x})")
            msg += f" [LE] {sub_name}"

            if sub_evt == LE_ADVERTISING_REPORT and len(evt_params) >= 2:
                num_reports = evt_params[1]
                msg += f" ({num_reports} report(s))"
                key_events.append({'type': 'LE_ADVERTISING', 'count': num_reports, 'ts': ts})

            elif sub_evt == LE_CONNECTION_COMPLETE:
                key_events.append({'type': 'LE_CONNECT', 'ts': ts})

        entries.append(LogEntry(
            timestamp=ts, level=LogLevel.INFO, message=msg,
        ))

    def quick_analyze(self, file_path: str) -> dict:
        """快速分析日志，返回摘要"""
        result = self.parse(file_path)
        return {
            "total_events": len(result.entries),
            "key_events": len(result.key_events),
            "connects": sum(1 for e in result.key_events if e.event_type in ('CONNECT', 'LE_CONNECT')),
            "disconnects": sum(1 for e in result.key_events if e.event_type == 'DISCONNECT'),
            "auth_ok": sum(1 for e in result.key_events if e.event_type == 'AUTH_SUCCESS'),
            "auth_fail": sum(1 for e in result.key_events if e.event_type == 'AUTH_FAIL'),
            "connect_fails": sum(1 for e in result.key_events if e.event_type == 'CONNECT_FAIL'),
            "advertising_reports": sum(e.details.get('count', 0) for e in result.key_events if e.event_type == 'LE_ADVERTISING'),
            "inquiry_results": sum(e.details.get('count', 0) for e in result.key_events if e.event_type == 'INQUIRY_RESULT'),
        }


def _datalink_name(t: int) -> str:
    return {
        1002: "HCI UART (H4)",
        1003: "HCI BCSP",
        1004: "HCI UART (H4) with timestamp",
    }.get(t, "Unknown")
