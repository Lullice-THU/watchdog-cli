from setuptools import setup, find_packages

setup(
    name="watchdog-cli",
    version="0.1.0",
    description="轻量级API监控工具，支持飞书告警",
    author="Your Name",
    author_email="you@example.com",
    url="https://github.com/yourname/watchdog-cli",
    packages=find_packages(),
    install_requires=[],
    extras_require={
        'yaml': ['pyyaml']
    },
    entry_points={
        'console_scripts': [
            'watchdog=watchdog:main',
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
)
