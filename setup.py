"""蓝牙自动化测试平台安装配置"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="bluetooth-test-platform",
    version="1.0.0",
    author="AutoTest Team",
    description="蓝牙自动化测试平台 - PC端测试工具",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(exclude=["tests", "tests.*"]),
    python_requires=">=3.8",
    install_requires=[
        "typer>=0.7.0",
        "adb-shell>=0.4.3",
    ],
    entry_points={
        "console_scripts": [
            "bt-adb=cli.bt_adb.cli:app",
            "bt-logger=cli.bt_logger.cli:app",
            "bt-serial=cli.bt_serial.cli:app",
            "bt-test=cli.bt_test.cli:app",
        ],
    },
)
