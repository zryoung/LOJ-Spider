import json
import random
import os, re, requests, sys, yaml
import time
import threading
from json import dumps
from requests import packages
from urllib.parse import urlparse
import traceback
from tenacity import retry, stop_after_attempt, wait_random


# @retry(stop=stop_after_attempt(5))
# @retry(stop=stop_after_attempt(5), wait=wait_random(1, 3), reraise=True)
def resume_download(url, file_path, retry=3):
    try:
        # 第一次请求是为了得到文件总大小
        r1 = requests.get(url, stream=True, verify=False)
        
        # 有些文件没有conteng-length这个信息
        if not r1.headers.get("Content-Length"):
            print('hi')
            with open(file_path, 'ab') as file:
                file.write(r1.content)

            print(f'{file_path}下载完成')
            return
        
        total_size = int(r1.headers["Content-Length"])
        # print(r1.headers)

        # 这重要了，先看看本地文件下载了多少
        if os.path.exists(file_path):
            temp_size = os.path.getsize(file_path)  # 本地已经下载的文件大小
        else:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            temp_size = 0
        # 显示一下下载了多少
        # print(f'已下载:{temp_size}')
        # print(f'文件总大小:{total_size}')

        if temp_size >= total_size:
            return
        # 核心部分，这个是请求下载时，从本地文件已经下载过的后面下载
        headers = {"Range": f"bytes={temp_size}-"}
        res = requests.get(url, stream=True, headers=headers,timeout=(6.1,21.1))

        with open(file_path, "ab") as file:
            for chunk in res.iter_content(chunk_size=1024):
                if chunk:
                    temp_size += len(chunk)
                    file.write(chunk)
                    file.flush()

                    ###这是下载实现进度显示####
                    done = int(50 * temp_size / total_size)
                    sys.stdout.write(
                        f"\r[{'█' * done}{' ' * (50 - done)}] {int(100 * temp_size / total_size)}% {file_path} "
                    )
                    sys.stdout.flush()
        print()  # 避免上面\r 回车符
        print(f'{file_path}下载完成')
    except Exception as e:
        data={
            "message":str(e),
            "file": file_path,
            "download_url":url
        }
        # file_writer('fail.json', json.dumps(data, ensure_ascii=False))
        print(f'{file_path}出错重试')
        # raise Exception(f'{file_path}出错重试')
        raise Exception(r1.headers)
        # print(f'Error:"message:"{e},"file:"{file_path},"url:"{url}')

def file_writer(filename, content):
    with open(os.path.join('..\downloads',filename), 'a', encoding='utf-8') as file:
        yaml.dump(
            data=content,
            stream=file,
            indent=2,
            encoding='utf-8'
        )


# @retry(stop=stop_after_attempt(3))
# def do_something():
#     print("Doing something...")
#     raise Exception("Something went wrong!")

# try:
#     do_something()
# except Exception as e:
#     print(f"Exception: {e}")



if __name__ == '__main__':
    url = 'https://files.loj.ac/libreoj-data/ecb25876-fe33-5fb8-9a56-14872c3a4fea?response-content-disposition=attachment%3B%20filename%3D%22sample.subtask3.in%22&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=5d9c40ebc7ca054399154bcebc5c3a5c%2F20240809%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20240809T052301Z&X-Amz-Expires=72000&X-Amz-SignedHeaders=host&X-Amz-Signature=d0443f41dc836588cf2b957fa6459926de4a7a0f39d028d82be5a9c3de5cc709'
    file_path = fr'..\downloads\loj.ac\507\additional_file\sample.subtask3.in'
    resume_download(url,file_path)
    # do_something()