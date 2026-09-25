"""py2app 打包配置：python setup.py py2app"""

from setuptools import setup

APP = ["run_app.py"]
DATA_FILES = ["assets/AppIcon.icns"]

OPTIONS = {
    "packages": ["rumps", "portpilot"],
    "iconfile": "assets/AppIcon.icns",
    "plist": {
        "CFBundleName": "PortPilot",
        "CFBundleDisplayName": "PortPilot",
        "CFBundleIdentifier": "cn.heerdy.portpilot",
        "CFBundleShortVersionString": "1.0.1",
        "CFBundleVersion": "1.0.1",
        "LSMinimumSystemVersion": "10.15",
        "LSUIElement": True,  # 菜单栏应用，不占 Dock
        "NSHumanReadableCopyright": "MIT License",
    },
    # 缩小体积：不打包测试依赖
    "excludes": ["tkinter", "unittest", "pydoc_data"],
}

setup(
    app=APP,
    name="PortPilot",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
