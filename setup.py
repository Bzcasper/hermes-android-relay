from setuptools import setup, find_packages

setup(
    name="hermes-android-relay",
    version="0.3.0",
    packages=find_packages(),
    install_requires=[
        "aiohttp>=3.9.0",
        "websockets>=12.0",
    ],
    entry_points={
        "console_scripts": [
            "hermes-android-relay=hermes_android_relay.relay:main",
        ]
    },
)
