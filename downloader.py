import os
import requests
import threading
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
import time
import uuid
import logging
from config import USER_AGENTS

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# 随机选择 User-Agent 的函数
def get_random_user_agent():
    return USER_AGENTS[uuid.uuid4().int % len(USER_AGENTS)]

class Downloader:
    def __init__(self, url, file_path, num_chunks=4, enable_progress=False):
        self.url = url
        self.file_path = file_path
        self.num_chunks = num_chunks
        self.file_size = 0
        self.support_range = False
        # 使用 uuid 生成唯一的临时目录名
        self.temp_dir = f"temp_parts_{uuid.uuid4().hex}"
        self.headers = {'User-Agent': get_random_user_agent()}
        
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
        
        try:
            
            with requests.head(self.url, allow_redirects=True, headers=self.headers) as response:
                self.support_range = 'bytes' in response.headers.get('Accept-Ranges', '')
                self.file_size = int(response.headers.get('Content-Length', 0))
        except requests.RequestException as e:
            logging.error(f"获取文件信息失败: {e}")
            raise
        
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

    def _download_chunk(self, start, end, chunk_id):
        """下载指定分块"""
        temp_path = os.path.join(self.temp_dir, f"part_{chunk_id}")
        if os.path.exists(temp_path):
            chunk_downloaded = os.path.getsize(temp_path)
            start += chunk_downloaded

        headers = {'Range': f'bytes={start}-{end}', 'User-Agent': get_random_user_agent()}
        try:
            with requests.get(self.url, headers=headers, stream=True) as response:
                response.raise_for_status()

                if not os.path.exists(self.temp_dir):
                    os.makedirs(self.temp_dir)

                with open(temp_path, 'ab') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            self._update_progress(len(chunk))
        except requests.RequestException as e:
            logging.error(f"分块 {chunk_id} 下载失败: {e}")
            raise

    def _merge_temp_files(self):
        """合并临时分块文件"""
        try:
            with open(self.file_path, 'wb') as main_file:
                for i in range(self.num_chunks):
                    temp_path = os.path.join(self.temp_dir, f"part_{i}")
                    if os.path.exists(temp_path):
                        with open(temp_path, 'rb') as temp_file:
                            main_file.write(temp_file.read())
                        os.remove(temp_path)
                    else:
                        logging.warning(f"警告: 临时文件 {temp_path} 不存在，可能下载失败。")
            
            if os.path.exists(self.temp_dir) and not os.listdir(self.temp_dir):
                os.rmdir(self.temp_dir)
        except Exception as e:
            logging.error(f"合并临时文件失败: {e}")
            raise

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

    def _should_retry(self, retries, max_retries):
        return retries < max_retries

    def download(self):
        """下载主逻辑"""
        max_retries = 3
        retries = 0
        
        while self._should_retry(retries, max_retries):
            if self.enable_progress:
                speed_thread = threading.Thread(target=self._show_speed, daemon=True)
                speed_thread.start()

            try:
                if os.path.exists(self.file_path):
                    actual_size = os.path.getsize(self.file_path)
                    if actual_size > self.file_size:
                        logging.info("已下载文件大小超过真实大小，删除文件并重新下载")
                        os.remove(self.file_path)
                        self.downloaded = 0
                        if self.enable_progress:
                            self.progress_bar.reset(total=self.file_size)

                if self.support_range and self.file_size > 0:
                    if self.downloaded == self.file_size:
                        logging.info("文件已完整下载")
                        return

                    remaining_size = self.file_size - self.downloaded
                    chunk_size = remaining_size // self.num_chunks
                    start_offset = self.downloaded
                    ranges = [(start_offset + i*chunk_size, start_offset + (i+1)*chunk_size-1 if i<self.num_chunks-1 else self.file_size-1, i) 
                              for i in range(self.num_chunks)]
                    
                    with ThreadPoolExecutor(max_workers=self.num_chunks) as executor:
                        futures = [executor.submit(self._download_chunk, start, end, i) 
                                  for start, end, i in ranges]
                        for future in futures:
                            future.result()
                    
                    self._merge_temp_files()
                else:
                    headers = {"User-Agent": get_random_user_agent()}
                    if self.downloaded > 0:
                        headers['Range'] = f'bytes={self.downloaded}-'
                    with requests.get(self.url, headers=headers, stream=True) as response:
                        with open(self.file_path, 'ab') as f:
                            for chunk in response.iter_content(chunk_size=8192):
                                if chunk:
                                    f.write(chunk)
                                    self._update_progress(len(chunk))
                
                if os.path.exists(self.file_path) and os.path.getsize(self.file_path) == self.file_size:
                    if self.enable_progress:
                        self.progress_bar.close()
                    logging.info("下载完成")
                    return
                else:
                    logging.info(f"下载的文件可能不完整，尝试重新下载 (重试次数: {retries + 1}/{max_retries})")
                    if os.path.exists(self.file_path):
                        os.remove(self.file_path)
                    self.downloaded = 0
                    if self.enable_progress:
                        self.progress_bar.reset(total=self.file_size)

            except Exception as e:
                if self.enable_progress:
                    self.progress_bar.close()
                logging.error(f"下载过程中出现错误: {e}，尝试重新下载 (重试次数: {retries + 1}/{max_retries})")
            
            retries += 1
        
        logging.error("达到最大重试次数，下载失败")
        if self.enable_progress:
            self.progress_bar.close()
        raise Exception("下载失败，达到最大重试次数")

if __name__ == "__main__":
    url = "http://lg-sin.fdcservers.net/10GBtest.zip"  # 10GB测试文件
    file_path = "largefile.zip"
    downloader = Downloader(url, file_path, num_chunks=4)
    downloader.download()