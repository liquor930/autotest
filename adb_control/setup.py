"""ADB控制模块安装配置"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="adb_control",
    version="1.0.0",
    author="AutoTest Team",
    author_email="autotest@example.com",
    description="ADB控制模块，负责通过WiFi ADB与Android手机设备进行通信",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/autotest/adb_control",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.8",
    install_requires=[
        "adb-shell>=0.4.3",
        "typer>=0.7.0",
    ],
    entry_points={
        "console_scripts": [
            "bt-adb=adb_control.cli:app",
        ],
    },
)
