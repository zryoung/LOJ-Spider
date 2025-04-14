import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import time
import uuid

class Downloader:
    def __init__(self, url, file_path, num_chunks=4, enable_progress=False):
        self.url = url
        self.file_path = file_path
        self.num_chunks = num_chunks
        self.file_size = 0
        self.support_range = False
        # 使用 uuid 生成唯一的临时目录名
        self.temp_dir = f"temp_parts_{uuid.uuid4().hex}"
        
        # 进度控制相关
        self.enable_progress = enable_progress  # 新增控制开关
        self.downloaded = 0
        self.lock = threading.Lock()
        self.progress_bar = None
        self.last_update_time = time.time()
        
        self._get_file_info()

    def _get_file_info(self):
        """获取文件信息（含进度条初始化）"""
        if os.path.exists(self.file_path):
            self.downloaded = os.path.getsize(self.file_path)
        
        response = requests.head(self.url, allow_redirects=True)
        self.support_range = 'bytes' in response.headers.get('Accept-Ranges', '')
        self.file_size = int(response.headers.get('Content-Length', 0))
        
        # 根据开关初始化进度条
        if self.enable_progress and self.progress_bar is None:
            self.progress_bar = tqdm(
                total=self.file_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                initial=self.downloaded,
                desc="下载进度",
                disable=not self.enable_progress  # 关键修改点
            )

    def _update_progress(self, chunk_size):
        """条件更新进度"""
        if not self.enable_progress:
            return
        
        with self.lock:
            self.downloaded += chunk_size
            self.progress_bar.update(chunk_size)

    def _show_speed(self):
        """条件启动速度显示"""
        if not self.enable_progress:
            return
        
        prev_downloaded = self.downloaded
        while hasattr(self, 'progress_bar') and not self.progress_bar.disable:
            time.sleep(0.5)
            with self.lock:
                current = self.downloaded
                speed = (current - prev_downloaded) / (time.time() - self.last_update_time)
                self.last_update_time = time.time()
                prev_downloaded = current
                self.progress_bar.set_postfix({'speed': f"{speed/1024:.2f}KB/s"})

    def _download_chunk(self, start, end, chunk_id):  # 新增修复的下载分块方法
        """下载指定分块"""
        headers = {'Range': f'bytes={start}-{end}'}
        response = requests.get(self.url, headers=headers, stream=True)
        response.raise_for_status()

        # 创建临时目录
        if not os.path.exists(self.temp_dir):
            os.makedirs(self.temp_dir)

        temp_path = os.path.join(self.temp_dir, f"part_{chunk_id}")
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    self._update_progress(len(chunk))  # 更新进度

    def _merge_temp_files(self):  # 新增修复的合并文件方法
        """合并临时分块文件"""
        with open(self.file_path, 'wb') as main_file:
            for i in range(self.num_chunks):
                temp_path = os.path.join(self.temp_dir, f"part_{i}")
                with open(temp_path, 'rb') as temp_file:
                    main_file.write(temp_file.read())
                os.remove(temp_path)
        os.rmdir(self.temp_dir)
                   
    def download(self):
        """下载主逻辑"""
        if self.enable_progress:
            speed_thread = threading.Thread(target=self._show_speed, daemon=True)
            speed_thread.start()

        try:
            # 原有下载逻辑保持不变...
            if self.support_range and self.file_size > 0:
                chunk_size = self.file_size // self.num_chunks
                ranges = [(i*chunk_size, (i+1)*chunk_size-1 if i<self.num_chunks-1 else self.file_size-1, i) 
                          for i in range(self.num_chunks)]
                
                with ThreadPoolExecutor(max_workers=self.num_chunks) as executor:
                    futures = [executor.submit(self._download_chunk, start, end, i) 
                              for start, end, i in ranges]
                    for future in futures:
                        future.result()
                
                self._merge_temp_files()
            else:
                with requests.get(self.url, stream=True) as response:
                    with open(self.file_path, 'ab') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                self._update_progress(len(chunk))
            
            if self.enable_progress:
                self.progress_bar.close()
            # print(f"下载完成")
        except Exception as e:
            if self.enable_progress:
                self.progress_bar.close()
            raise e

if __name__ == "__main__":
    url = "http://lg-sin.fdcservers.net/10GBtest.zip"  # 10GB测试文件
    file_path = "largefile.zip"
    downloader = Downloader(url, file_path, num_chunks=4)
    downloader.download()