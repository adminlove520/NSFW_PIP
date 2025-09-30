# NSFW_PIP

这是一个用于下载内容的工具，支持断点续传、自动去重功能，以及定时下载和清理功能。

## 功能特性

- **断点续传**：下载中断后可以从上次的位置继续下载，无需重新开始
- **自动去重**：自动检测并跳过已下载的文件，避免重复下载
- **多线程下载**：支持设置线程数量，提高下载速度
- **下载数量限制**：可以限制每次下载的文件数量
- **日期子目录**：支持按日期组织下载文件
- **自动每日下载**：通过GitHub Actions自动执行每日下载任务并发布Release
- **历史数据清理**：自动清理指定天数之前的历史数据，节省存储空间

## 使用方法

```bash
python downloader.py -o [output_folder] -t [thread_num] -n [max_downloads] [--date-subdir]
```

### 参数说明

- `-o` 或 `--output_folder`：指定下载文件的输出目录
- `-t` 或 `--thread_num`：指定下载使用的线程数量
- `-n` 或 `--max_downloads`：指定最大下载文件数量
- `--date-subdir`：启用日期子目录功能，将文件保存到以"雅俗共赏_YYYYMMDD"命名的子目录中

### 示例

```bash
# 使用4个线程下载到downloads文件夹
python downloader.py -o downloads -t 4

# 使用2个线程下载最多10个文件，保存到日期子目录
python downloader.py -o downloads -t 2 -n 10 --date-subdir
```

## 自动清理功能

系统提供了历史数据清理工具，可以自动清理指定天数之前的数据：

```bash
python cleanUp.py -d [days_to_keep] -p [cleanup_path]
```

### 参数说明

- `-d` 或 `--days`：保留最近多少天的数据（默认：7天）
- `-p` 或 `--path`：要清理的数据目录（默认：downloads）

### 示例

```bash
# 清理downloads目录中超过7天的文件
python cleanUp.py

# 清理特定目录中超过30天的文件
python cleanUp.py -d 30 -p custom_downloads

## 安装要求

确保您的系统已安装Python。

依赖包安装：
```bash
pip install -r requirements.txt
```

## GitHub Actions 工作流

本项目包含两个GitHub Actions工作流：

1. **每日下载** (`daily-download.yml`)：
   - 每天UTC时间自动执行
   - 下载10个视频并打包发布到GitHub Release
   - 支持手动触发并自定义下载参数

2. **历史数据清理** (`cleanUp.yml`)：
   - 每天UTC时间自动执行
   - 清理7天前的历史数据
   - 支持手动触发并自定义保留天数和路径

## 注意事项

- 请确保您有足够的磁盘空间用于存储下载内容
- 合理设置线程数量，避免因线程过多导致系统资源占用过高
- 下载内容请遵守相关法律法规和使用条款
- 自动清理功能会永久删除文件，请谨慎设置保留天数