#!/usr/bin/env python
"""
项目初始化脚本，创建MVVM架构所需的目录结构。
"""

import os
import sys


def create_directory(path):
    """创建目录，如果不存在"""
    if not os.path.exists(path):
        os.makedirs(path)
        print(f"创建目录: {path}")
    else:
        print(f"目录已存在: {path}")


def create_init_file(path):
    """创建空的 __init__.py 文件"""
    init_file = os.path.join(path, "__init__.py")
    if not os.path.exists(init_file):
        with open(init_file, "w") as f:
            pass
        print(f"创建文件: {init_file}")
    else:
        print(f"文件已存在: {init_file}")


def main():
    """主函数"""
    # 定义需要创建的目录
    directories = [
        # Model层
        "model",
        # ViewModel层
        "viewmodel",
        # View层
        "view",
        # 服务层及子目录
        "services",
        "services/loaders",
        "services/structurers",
        "services/preprocessors",
        "services/visualizers",
        # 数据目录
        "data",
    ]

    # 创建目录和__init__.py文件
    for directory in directories:
        create_directory(directory)
        create_init_file(directory)

    print("项目目录结构初始化完成！")


if __name__ == "__main__":
    main()
