
from setuptools import setup

setup(
    name="hermes-android-relay",
    version="0.3.0-render",
    package_dir={"hermes_android_relay": "hermes_android_relay"},
    packages=["hermes_android_relay"],
    install_requires=[
        "aiohttp>=3.9.0,<4.0.0",
    ],
    python_requires=">=3.10",
)
