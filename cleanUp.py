#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
清理历史数据脚本
用于清理指定天数以前的下载数据和历史记录文件
"""

import os
import sys
import time
import argparse
from datetime import datetime, timedelta
import shutil


def get_file_modify_time(file_path):
    """
    获取文件的修改时间
    :param file_path: 文件路径
    :return: datetime对象
    """
    try:
        mtime = os.path.getmtime(file_path)
        return datetime.fromtimestamp(mtime)
    except Exception as e:
        print(f"获取文件{file_path}修改时间失败: {e}")
        return None


def clean_old_data(base_dir, days_to_keep):
    """
    清理指定天数以前的数据
    :param base_dir: 基础目录
    :param days_to_keep: 保留的天数
    :return: 清理的文件数和目录数
    """
    if not os.path.exists(base_dir):
        print(f"目录不存在: {base_dir}")
        return 0, 0
    
    cutoff_date = datetime.now() - timedelta(days=days_to_keep)
    print(f"清理{cutoff_date}之前的文件 (保留最近{days_to_keep}天的数据)")
    
    cleaned_files = 0
    cleaned_dirs = 0
    
    # 遍历目录，先清理文件
    for root, dirs, files in os.walk(base_dir, topdown=False):
        # 清理文件
        for file in files:
            file_path = os.path.join(root, file)
            file_time = get_file_modify_time(file_path)
            if file_time and file_time < cutoff_date:
                try:
                    os.remove(file_path)
                    cleaned_files += 1
                    print(f"删除文件: {file_path}")
                except Exception as e:
                    print(f"删除文件{file_path}失败: {e}")
        
        # 清理空目录
        for dir_name in dirs:
            dir_path = os.path.join(root, dir_name)
            if not os.listdir(dir_path):
                try:
                    os.rmdir(dir_path)
                    cleaned_dirs += 1
                    print(f"删除空目录: {dir_path}")
                except Exception as e:
                    print(f"删除目录{dir_path}失败: {e}")
    
    # 检查并清理主目录中的旧的日期子目录
    for item in os.listdir(base_dir):
        item_path = os.path.join(base_dir, item)
        if os.path.isdir(item_path) and item.startswith("雅俗共赏_"):
            # 检查目录名称中的日期
            try:
                # 提取日期部分 YYYYMMDD
                date_str = item.split('_')[1]
                dir_date = datetime.strptime(date_str, "%Y%m%d")
                if dir_date < cutoff_date:
                    # 递归删除整个目录
                    shutil.rmtree(item_path)
                    cleaned_dirs += 1
                    print(f"删除日期目录: {item_path}")
            except Exception as e:
                print(f"处理目录{item_path}时出错: {e}")
    
    return cleaned_files, cleaned_dirs


def main():
    parser = argparse.ArgumentParser(description='清理历史下载数据')
    parser.add_argument('-d', '--days', type=int, default=7,
                        help='保留最近多少天的数据 (默认: 7天)')
    parser.add_argument('-p', '--path', type=str, default='downloads',
                        help='要清理的数据目录 (默认: downloads)')
    
    args = parser.parse_args()
    
    # 获取绝对路径
    base_dir = os.path.abspath(args.path)
    
    print(f"开始清理数据...")
    print(f"清理目录: {base_dir}")
    print(f"保留天数: {args.days}天")
    
    start_time = time.time()
    
    try:
        cleaned_files, cleaned_dirs = clean_old_data(base_dir, args.days)
        
        elapsed_time = time.time() - start_time
        print(f"\n清理完成!")
        print(f"删除的文件数: {cleaned_files}")
        print(f"删除的目录数: {cleaned_dirs}")
        print(f"总耗时: {elapsed_time:.2f}秒")
        
    except Exception as e:
        print(f"清理过程中发生错误: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()