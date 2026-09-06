from setuptools import setup, find_packages

setup(
    name="jvmsim",
    version="1.0.0",
    description="A pure-Python simulator for a small subset of JVM bytecode",
    packages=find_packages(include=["jvmsim", "jvmsim.*"]),
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "jvmsim=jvmsim.cli:main",
        ],
    },
)
