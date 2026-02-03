"""
セットアップスクリプト
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="web-pdf-verification",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Web vs PDF 整合性検証システム - 高度なクラスタリングアルゴリズムを使用",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/web-pdf-verification",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.9",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "web-pdf-verify=main:main",
        ],
    },
)

