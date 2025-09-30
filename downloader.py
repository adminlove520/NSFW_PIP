import requests
import threading
import os
import time
import hashlib
import json
from urllib.parse import urlparse
from datetime import datetime, timezone

# 定义UTC常量以兼容Python 3.10
UTC = timezone.utc
import signal
import sys
import argparse
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import uuid
import re
import random

# 禁用SSL警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class VideoDownloader:
    def __init__(self, output_dir="downloads", max_workers=3, max_downloads=None):
        self.output_dir = self.sanitize_path(output_dir)
        self.max_workers = max_workers
        self.max_downloads = max_downloads  # 添加最大下载数量限制
        self.downloaded_count = 0
        self.duplicate_count = 0
        self.error_count = 0
        self.total_size = 0
        self.downloaded_hashes = set()
        self.downloaded_urls = set()
        self.running = True
        self.lock = threading.Lock()
        self.api_failures = {}
        self.filename_counter = 0
        
        # 每个线程独立的会话
        self.thread_local = threading.local()
        
        # 只使用稳定的API
        self.api_urls = [
            # HTTP接口（更稳定）
            'http://api.xingchenfu.xyz/API/hssp.php',
            'http://api.xingchenfu.xyz/API/wmsc.php',
            'http://api.xingchenfu.xyz/API/tianmei.php',
            'http://api.xingchenfu.xyz/API/cdxl.php',
            'http://api.xingchenfu.xyz/API/yzxl.php',
            'http://api.xingchenfu.xyz/API/rwsp.php',
            'http://api.xingchenfu.xyz/API/nvda.php',
            'http://api.xingchenfu.xyz/API/bsxl.php',
            'http://api.xingchenfu.xyz/API/zzxjj.php',
            'http://api.xingchenfu.xyz/API/qttj.php',
            'http://api.xingchenfu.xyz/API/xqtj.php',
            'http://api.xingchenfu.xyz/API/sktj.php',
            'http://api.xingchenfu.xyz/API/cossp.php',
            'http://api.xingchenfu.xyz/API/xiaohulu.php',
            'http://api.xingchenfu.xyz/API/manhuay.php',
            'http://api.xingchenfu.xyz/API/bianzhuang.php',
            'http://api.xingchenfu.xyz/API/jk.php',
            # 相对稳定的HTTPS接口
            'https://www.hhlqilongzhu.cn/api/MP4_xiaojiejie.php',
            'https://v.api.aa1.cn/api/api-video-qing-chun/index.php',
            'https://api.yujn.cn/api/zzxjj.php?type=video',
            'https://api.jkyai.top/API/jxhssp.php',
            'https://api.jkyai.top/API/jxbssp.php',
            'https://api.jkyai.top/API/rmtmsp/api.php',
            'https://api.jkyai.top/API/qcndxl.php',
        ]
        
        # 创建下载目录
        self.ensure_directory(self.output_dir)
        
        # 加载已下载记录
        self.load_download_history()
        
        # 设置信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def sanitize_path(self, path):
        """清理路径中的特殊字符"""
        path = re.sub(r'[<>:"|?*]', '_', path)
        path = path.replace(' ', '_')
        return path

    def ensure_directory(self, directory):
        """确保目录存在且可写"""
        try:
            os.makedirs(directory, exist_ok=True)
            test_file = os.path.join(directory, 'test_write.tmp')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            print(f"✓ 输出目录: {os.path.abspath(directory)}")
        except Exception as e:
            print(f"❌ 目录创建失败: {e}")
            fallback_dir = os.path.join(os.getcwd(), 'video_downloads')
            print(f"使用备用目录: {fallback_dir}")
            os.makedirs(fallback_dir, exist_ok=True)
            self.output_dir = fallback_dir

    def get_session(self):
        """获取线程本地的session"""
        if not hasattr(self.thread_local, 'session'):
            session = requests.Session()
            
            retry_strategy = Retry(
                total=1,
                backoff_factor=0.3,
                status_forcelist=[429, 500, 502, 503, 504],
                allowed_methods=["HEAD", "GET", "OPTIONS"]
            )
            
            adapter = HTTPAdapter(
                max_retries=retry_strategy,
                pool_maxsize=10,
                pool_block=False
            )
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            
            session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Accept': '*/*',
                'Connection': 'keep-alive',
            })
            
            self.thread_local.session = session
            
        return self.thread_local.session

    def get_unique_filename(self, extension='.mp4'):
        """生成唯一的文件名"""
        with self.lock:
            self.filename_counter += 1
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            thread_id = threading.current_thread().ident % 1000
            unique_id = f"{timestamp}_{thread_id}_{self.filename_counter:06d}"
            
        filename = f"video_{unique_id}{extension}"
        return filename

    def is_api_available(self, api_url):
        """检查API是否可用"""
        failure_count = self.api_failures.get(api_url, 0)
        return failure_count < 5

    def mark_api_failure(self, api_url):
        """标记API失败"""
        with self.lock:
            self.api_failures[api_url] = self.api_failures.get(api_url, 0) + 1

    def mark_api_success(self, api_url):
        """标记API成功"""
        with self.lock:
            if api_url in self.api_failures and self.api_failures[api_url] > 0:
                self.api_failures[api_url] -= 1

    def load_download_history(self):
        """加载下载历史记录"""
        history_file = os.path.join(self.output_dir, 'download_history.json')
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.downloaded_hashes = set(data.get('hashes', []))
                    self.downloaded_urls = set(data.get('urls', []))
                print(f"✓ 已加载 {len(self.downloaded_hashes)} 个历史记录")
            except Exception as e:
                print(f"⚠ 加载历史失败: {e}")

    def save_download_history(self):
        """保存下载历史记录"""
        history_file = os.path.join(self.output_dir, 'download_history.json')
        try:
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'hashes': list(self.downloaded_hashes),
                    'urls': list(self.downloaded_urls)
                }, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"⚠ 保存历史失败: {e}")

    def signal_handler(self, signum, frame):
        """信号处理函数"""
        print("\n\n📍 正在停止...")
        self.running = False
        self.save_download_history()
        print(f"📊 最终统计 - 成功: {self.downloaded_count} | 重复: {self.duplicate_count} | 错误: {self.error_count}")
        sys.exit(0)

    def get_video_url(self, api_url):
        """从API获取视频URL"""
        if not self.is_api_available(api_url):
            return None
            
        try:
            session = self.get_session()
            
            # 根据URL决定是否验证SSL
            verify_ssl = not any(domain in api_url for domain in [
                'api.jrsg.top', 'api.emoao.com', 'api.caonm.net', 
                'api.linhun.pro', 'api.lolimi.cn'
            ])
            
            response = session.get(
                api_url, 
                timeout=(2, 5),
                allow_redirects=True,
                verify=verify_ssl
            )
            
            if response.status_code == 200:
                self.mark_api_success(api_url)
                
                # 解析JSON响应
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        for key in ['url', 'video_url', 'data', 'video', 'mp4']:
                            if key in data and isinstance(data[key], str):
                                video_url = data[key].strip()
                                if video_url.startswith('http'):
                                    return video_url
                except:
                    pass
                
                # 检查直接文本响应
                content = response.text.strip()
                if content.startswith('http') and len(content) < 500:
                    return content
                
                # 检查是否是视频文件重定向
                content_type = response.headers.get('content-type', '').lower()
                if 'video' in content_type:
                    return response.url
                    
            else:
                self.mark_api_failure(api_url)
                
            return None
            
        except Exception:
            self.mark_api_failure(api_url)
            return None

    def download_video(self, video_url):
        """下载视频"""
        if not self.running or video_url in self.downloaded_urls:
            if video_url in self.downloaded_urls:
                with self.lock:
                    self.duplicate_count += 1
            return False

        try:
            session = self.get_session()
            
            # HEAD请求获取文件信息
            head_response = session.head(
                video_url, 
                timeout=(3, 8), 
                allow_redirects=True
            )
            
            if head_response.status_code not in [200, 206]:
                return False
                
            content_length = int(head_response.headers.get('content-length', 0))
            content_type = head_response.headers.get('content-type', '')
            
            # 确定文件扩展名
            extension = '.mp4'
            if 'avi' in content_type.lower():
                extension = '.avi'
            elif 'mov' in content_type.lower():
                extension = '.mov'
            elif 'webm' in content_type.lower():
                extension = '.webm'
                
            filename = self.get_unique_filename(extension)
            file_path = os.path.join(self.output_dir, filename)
            temp_path = file_path + '.tmp'
            
            # 检查断点续传
            resume_pos = 0
            if os.path.exists(temp_path):
                resume_pos = os.path.getsize(temp_path)
                if content_length > 0 and resume_pos >= content_length:
                    os.remove(temp_path)
                    resume_pos = 0
            
            # 下载请求
            headers = {}
            if resume_pos > 0:
                headers['Range'] = f'bytes={resume_pos}-'
            
            response = session.get(
                video_url, 
                headers=headers, 
                stream=True, 
                timeout=(5, 30)
            )
            
            if response.status_code not in [200, 206]:
                return False
            
            # 写入文件
            downloaded_size = resume_pos
            with open(temp_path, 'ab' if resume_pos > 0 else 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if not self.running:
                        return False
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)
            
            # 检查文件完整性
            if content_length > 0 and downloaded_size < content_length * 0.8:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
            
            # 移动到最终位置
            try:
                os.rename(temp_path, file_path)
            except OSError:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                return False
            
            # 检查重复
            file_hash = self.get_file_hash(file_path)
            if file_hash and file_hash in self.downloaded_hashes:
                os.remove(file_path)
                with self.lock:
                    self.duplicate_count += 1
                return False
            
            # 记录成功
            with self.lock:
                self.downloaded_count += 1
                self.total_size += downloaded_size
                if file_hash:
                    self.downloaded_hashes.add(file_hash)
                self.downloaded_urls.add(video_url)
            
            print(f"✓ {filename} ({self.format_size(downloaded_size)})")
            return True
            
        except Exception as e:
            # 清理临时文件
            if 'temp_path' in locals() and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass
            
            with self.lock:
                self.error_count += 1
            return False

    def get_file_hash(self, file_path):
        """计算文件MD5哈希"""
        try:
            hasher = hashlib.md5()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except:
            return None

    def format_size(self, size_bytes):
        """格式化文件大小"""
        if size_bytes == 0:
            return "0 B"
        size_names = ["B", "KB", "MB", "GB"]
        i = 0
        while size_bytes >= 1024 and i < len(size_names) - 1:
            size_bytes /= 1024.0
            i += 1
        return f"{size_bytes:.1f} {size_names[i]}"

    def get_available_apis(self):
        """获取可用API列表"""
        return [api for api in self.api_urls if self.is_api_available(api)]

    def worker_thread(self, thread_id):
        """工作线程 - 每个线程独立工作，不等待其他线程"""
        print(f"🎯 线程 {thread_id} 启动")
        
        while self.running:
            # 检查是否达到最大下载数量
            with self.lock:
                if self.max_downloads is not None and self.downloaded_count >= self.max_downloads:
                    self.running = False
                    break
            
            try:
                # 获取可用API
                available_apis = self.get_available_apis()
                if not available_apis:
                    # 如果没有可用API，重置失败计数器并短暂等待
                    time.sleep(2)
                    with self.lock:
                        self.api_failures = {k: max(0, v-1) for k, v in self.api_failures.items()}
                    continue
                
                # 随机选择API并获取视频URL
                api_url = random.choice(available_apis)
                video_url = self.get_video_url(api_url)
                
                if video_url and self.running:
                    # 立即下载，不等待其他线程
                    self.download_video(video_url)
                    # 下载完成后立即继续下一个，只有很短的间隔避免过于频繁
                    time.sleep(0.1)
                else:
                    # 如果获取URL失败，稍微等待一下再试下一个API
                    time.sleep(0.5)
                
            except Exception:
                # 出现异常时短暂等待
                time.sleep(1)

    def print_status(self):
        """状态显示"""
        while self.running:
            available_count = len(self.get_available_apis())
            with self.lock:
                print(f"\r📊 成功:{self.downloaded_count} 重复:{self.duplicate_count} "
                      f"错误:{self.error_count} 大小:{self.format_size(self.total_size)} "
                      f"API:{available_count}/{len(self.api_urls)}", end='', flush=True)
            time.sleep(1)

    def start_download(self):
        """开始下载"""
        print(f"🚀 启动下载器 (线程数: {self.max_workers})")
        print("⏹ Ctrl+C 停止")
        print("🔄 每个线程独立工作，下完立即继续\n")
        
        # 启动状态显示线程
        status_thread = threading.Thread(target=self.print_status, daemon=True)
        status_thread.start()
        
        # 启动工作线程，每个线程独立工作
        threads = []
        for i in range(self.max_workers):
            thread = threading.Thread(target=self.worker_thread, args=(i+1,), daemon=True)
            thread.start()
            threads.append(thread)
        
        try:
            # 主线程等待，但不干预工作线程
            while self.running:
                time.sleep(1)
                # 检查是否所有线程都还活着
                if not any(t.is_alive() for t in threads):
                    print("\n所有线程已结束")
                    break
        except KeyboardInterrupt:
            self.signal_handler(signal.SIGINT, None)
        finally:
            # 确保在任何情况下都保存历史记录
            if not self.running:  # 如果是正常结束或达到下载限制
                self.save_download_history()
                print(f"\n📍 下载完成，已保存历史记录")
                print(f"📊 最终统计 - 成功: {self.downloaded_count} | 重复: {self.duplicate_count} | 错误: {self.error_count}")

def main():
    parser = argparse.ArgumentParser(description='🎬 多线程视频下载器')
    parser.add_argument('-o', '--output', default='downloads', help='输出目录')
    parser.add_argument('-t', '--threads', type=int, default=3, help='线程数 (默认: 3)')
    parser.add_argument('-n', '--max-downloads', type=int, default=None, help='最大下载数量')
    parser.add_argument('--date-subdir', action='store_true', help='是否在输出目录下创建日期子目录')
    
    args = parser.parse_args()
    
    if args.threads < 1 or args.threads > 16:
        print("❌ 线程数应在1-16之间")
        return
    
    # 处理日期子目录
    output_dir = args.output
    if args.date_subdir:
        date_str = datetime.now(UTC).strftime("%Y%m%d")
        output_dir = os.path.join(output_dir, f"雅俗共赏_{date_str}")
    
    try:
        downloader = VideoDownloader(
            output_dir=output_dir, 
            max_workers=args.threads,
            max_downloads=args.max_downloads
        )
        downloader.start_download()
    except Exception as e:
        print(f"❌ 程序错误: {e}")

if __name__ == "__main__":
    main()