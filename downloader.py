import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import time

class Downloader:
    def __init__(self, url, file_path, num_chunks=4):
        self.url = url
        self.file_path = file_path
        self.num_chunks = num_chunks
        self.file_size = 0
        self.support_range = False
        self.temp_dir = "temp_parts"
        
        # 进度相关属性
        self.downloaded = 0  # 已下载字节数
        self.lock = threading.Lock()
        self.progress_bar = None
        self.last_update_time = time.time()
        
        self._get_file_info()

    def _get_file_info(self):
        """获取文件信息并初始化进度"""
        # 初始化已下载量
        if os.path.exists(self.file_path):
            self.downloaded = os.path.getsize(self.file_path)
        
        response = requests.head(self.url, allow_redirects=True)
        self.support_range = 'bytes' in response.headers.get('Accept-Ranges', '')
        self.file_size = int(response.headers.get('Content-Length', 0))
        
        # 初始化进度条
        if self.progress_bar is None:
            self.progress_bar = tqdm(
                total=self.file_size,
                unit='B',
                unit_scale=True,
                unit_divisor=1024,
                initial=self.downloaded,
                desc="下载进度"
            )

    def _update_progress(self, chunk_size):
        """更新进度（线程安全）"""
        with self.lock:
            self.downloaded += chunk_size
            self.progress_bar.update(chunk_size)

    def _download_chunk(self, start, end, chunk_id):
        """下载指定分块并更新进度"""
        headers = {'Range': f'bytes={start}-{end}'}
        response = requests.get(self.url, headers=headers, stream=True)
        response.raise_for_status()

        temp_path = os.path.join(self.temp_dir, f"part_{chunk_id}")
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    self._update_progress(len(chunk))  # 更新进度

    def _show_speed(self):
        """单独线程显示实时速度"""
        prev_downloaded = self.downloaded
        while not self.progress_bar.disable:
            time.sleep(0.5)
            with self.lock:
                current = self.downloaded
                speed = (current - prev_downloaded) / (time.time() - self.last_update_time)
                self.last_update_time = time.time()
                prev_downloaded = current
                
                # 更新进度条后缀
                self.progress_bar.set_postfix({
                    'speed': f"{speed/1024:.2f}KB/s"
                })

    def download(self):
        """执行下载"""
        # 速度显示线程
        speed_thread = threading.Thread(target=self._show_speed, daemon=True)
        speed_thread.start()

        try:
            # 原有下载逻辑...
            if self.support_range and self.file_size > 0:
                # 分块下载逻辑
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
                # 单线程下载逻辑
                with requests.get(self.url, stream=True) as response:
                    with open(self.file_path, 'ab') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            if chunk:
                                f.write(chunk)
                                self._update_progress(len(chunk))
            
            # 关闭进度条
            self.progress_bar.close()
            print("下载完成")
        except Exception as e:
            self.progress_bar.close()
            raise e

if __name__ == "__main__":
    url = "http://lg-sin.fdcservers.net/10GBtest.zip"
    file_path = "largefile.zip"
    downloader = Downloader(url, file_path, num_chunks=4)
    downloader.download()