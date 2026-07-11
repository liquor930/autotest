"""语法检查 + 核心引擎快速验证"""
import ast, os

# 1. 语法检查
files = [
    'core/models.py', 'core/database.py', 'core/event_bus.py',
    'core/resource_manager.py', 'core/execution_engine.py',
    'core/result_manager.py', 'core/test_manager.py', 'core/__init__.py',
    'modules/adb/manager.py', 'cli/bt_adb/cli.py',
]

ok = fail = 0
for f in files:
    try:
        with open(f, encoding='utf-8') as fh:
            ast.parse(fh.read())
        ok += 1
    except SyntaxError as e:
        fail += 1
        print(f'SYNTAX ERROR: {f} line {e.lineno}: {e.msg}')

print(f'\n【语法检查】{ok}/{ok+fail} 通过')

# 2. 核心引擎快速验证
if ok == len(files):
    print('\n【核心引擎验证】')
    from core import (
        TestManager, TestConfig, TestCase, TestStep,
        DatabaseManager, EventBus, ResourceManager,
        SessionStatus, ResultStatus, EventType,
    )

    # EventBus 单例
    bus = EventBus()
    events = []
    def handler(e):
        events.append(e.event_type.value)
    bus.subscribe(EventType.SESSION_STARTED, handler)
    bus.publish(type('E', (), {'event_type': EventType.SESSION_STARTED, 'data': {}, 'timestamp': None, 'source': ''})())
    assert len(events) == 1, 'EventBus failed'
    print('✓ EventBus 单例 + 订阅/发布')

    # DatabaseManager
    db = DatabaseManager(':memory:')
    db.execute_query("SELECT 1")
    print('✓ DatabaseManager (in-memory SQLite)')

    # ResourceManager
    rm = ResourceManager()
    from core import CoreDeviceInfo, DeviceType, DeviceStatus
    rm.register_device(CoreDeviceInfo(device_id='test:5555', name='TestPhone'))
    allocated = rm.allocate_device()
    assert allocated is not None and allocated.status == DeviceStatus.BUSY
    rm.release_device('test:5555')
    print('✓ ResourceManager 注册/分配/释放')

    # TestManager 完整流程
    tm = TestManager()
    sid = tm.create_session(name='快速冒烟测试')
    assert sid and len(sid) > 8, 'Session ID generation failed'
    print(f'✓ create_session → {sid}')

    started = tm.start_test(sid)
    assert started, 'Failed to start test'
    import time; time.sleep(2)
    status = tm.get_session_status(sid)
    assert status is not None, 'get_session_status failed'
    print(f'✓ start_test + get_session_status → {status.status.value} ({status.progress:.0f}%)')

    # 结果报告生成
    report = tm.results.generate_report(sid, 'html')
    assert os.path.exists(report), f'Report not found: {report}'
    print(f'✓ generate_report → {report}')

    tm.cleanup_session(sid)
    print('✓ cleanup_session')

    print('\n🎉 全部通过!')
