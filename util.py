import json
import os
import re
import sys
import base64
from urllib.parse import urlparse
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_random
import yaml

from downloader import Downloader

BASE64 = r"^data:\S+/(\S+);base64,?(([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{4}|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)){1}"

def log_while_last_retry(retry_state):
    logger.error(retry_state.outcome.result())  # 打印原函数的返回值

# @logger.catch
@retry(stop=stop_after_attempt(5), retry_error_callback=log_while_last_retry, wait=wait_random(1, 3), reraise=True)
def request_post(url, headers=None, data=None, json=None, stream=True,verify=False, timeout=(5, 5)):
    return requests.post(
        url,
        stream=stream,
        verify=verify,
        timeout=timeout, 
        headers=headers,
        data=data,
        json=json,
    )

# @logger.catch
@retry(stop=stop_after_attempt(5), retry_error_callback=log_while_last_retry,wait=wait_random(1, 3),reraise=True)
def request_get(url, params=None, headers=None, stream=False,verify=False, timeout=(5, 5)):
    return requests.get(
        url, 
        params=params,
        headers=headers,
        stream=stream,
        verify=verify,
        timeout=timeout,
    )



@retry(stop=stop_after_attempt(5), retry_error_callback=log_while_last_retry, wait=wait_random(1, 3), reraise=True)
def resume_download(url, file_path):
    # os.makedirs(os.path.dirname(file_path), exist_ok=True)
    # downloader = Downloader(url, file_path)
    # downloader.download()
    import json
import os
import re
import sys
import base64
from urllib.parse import urlparse
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_random
import yaml

BASE64 = r"^data:\S+/(\S+);base64,?(([A-Za-z0-9+/]{4})*([A-Za-z0-9+/]{4}|[A-Za-z0-9+/]{3}=|[A-Za-z0-9+/]{2}==)){1}"

def log_while_last_retry(retry_state):
    logger.error(retry_state.outcome.result())  # 打印原函数的返回值

# @logger.catch
@retry(stop=stop_after_attempt(5), retry_error_callback=log_while_last_retry, wait=wait_random(1, 3), reraise=True)
def request_post(url, headers=None, data=None, json=None, stream=True,verify=False, timeout=(5, 5)):
    return requests.post(
        url,
        stream=stream,
        verify=verify,
        timeout=timeout, 
        headers=headers,
        data=data,
        json=json,
    )

# @logger.catch
@retry(stop=stop_after_attempt(5), retry_error_callback=log_while_last_retry,wait=wait_random(1, 3),reraise=True)
def request_get(url, params=None, headers=None, stream=False,verify=False, timeout=(5, 5)):
    return requests.get(
        url, 
        params=params,
        headers=headers,
        stream=stream,
        verify=verify,
        timeout=timeout,
    )



@retry(stop=stop_after_attempt(5), retry_error_callback=log_while_last_retry, wait=wait_random(1, 3), reraise=True)
def resume_download(url, file_path):
    
    # 这重要了，先看看本地文件下载了多少
    if os.path.exists(file_path):
        temp_size = os.path.getsize(file_path)  # 本地已经下载的文件大小
    else:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        temp_size = 0
        
    # try:
    # 第一次请求是为了得到文件总大小
    r1 = requests.head(url, stream=True, verify=False)
    # 有些文件没有conteng-length这个信息
    if not r1.headers.get("Content-Length"):
        r = requests.get(url, stream=True, verify=False)
        with open(file_path, 'ab') as file:
            file.write(r.content)
        return
    
    total_size = int(r1.headers["Content-Length"])


    # print(f"{temp_size=}\t{total_size=}\t剩余：{total_size-temp_size}")

    if temp_size > total_size:
        os.remove(file_path)
        temp_size = 0
    elif temp_size == total_size:
        return
    # 核心部分，这个是请求下载时，从本地文件已经下载过的后面下载
    headers = {"Range": f"bytes={temp_size}-"}
    res = request_get(url, stream=True, headers=headers,timeout=(6.1,21.1))

    with open(file_path, "ab") as file:
        for chunk in res.iter_content(chunk_size=1024):
            if chunk:
                temp_size += len(chunk)
                file.write(chunk)
                file.flush()

                ###这是下载实现进度显示####
                done = int(50 * temp_size / total_size)
                sys.stdout.write(
                    f"\r[{'█' * done}{' ' * (50 - done)}] {int(100 * temp_size / total_size):3d}% \t{file_path} "
                )
                sys.stdout.flush()
    print()  # 避免上面\r 回车符

def file_writer(file_path, content):
    with open(file_path, 'a', encoding='utf-8') as file:
        yaml.dump(
            data=content,
            stream=file,
            indent=2,
            encoding='utf-8'
        )

def create_writer(file_path):
    path = os.path.join(str(file_path))

    def writer(filname, content=None):
        target = os.path.join(path, filname)
        target_dir = os.path.dirname(target)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        if content==None:
            return target
        with open(target, 'w', encoding='utf-8') as file:
            file.write(content)
    
    return writer

def get_filename_and_extension(url):
    parsed_url = urlparse(url)
    path = parsed_url.path
    filename_with_extension = path.split('/')[-1]
    filename = filename_with_extension.split('.')[0]
    extension = filename_with_extension.split('.')[-1]
    return filename, extension

def get_and_replace_images(content, picpath, host=None):
        
    # TODO:以下修复可能不完善
    # 后面的"230"不获取，不然导致下载url出错
    # ![example.png](https://img.loj.ac.cn/2024/09/06/bc7efceff875c.png "230")
    img_arr = re.findall(r'!\[.*?\]\((.*?) \".*?\"\)', content)
    img_arr += re.findall(r'!\[.*?\]\((.*?)\)', content)

    if img_arr:
        os.makedirs(picpath, exist_ok=True)
    for img_url in img_arr:
        if not img_url.startswith('http'):
            if host:
                img_url = host + img_url
            else:
                logger.error(f'图片地址不完整：{img_url}')
                continue
        filename, extension = get_filename_and_extension(url=img_url)
        pic_file_path = os.path.join(picpath, f'{filename}.{extension}')
        try:
            resume_download(url=img_url, file_path=pic_file_path)
            content = content.replace(img_url, f'file://{filename}.{extension}?type=additional_file')
        except Exception as e:
            logger.error(f'图片下载出错：{picpath}-{img_url},错误信息：{e}') 
    return content

def ordered_yaml_dump(data, stream=None, Dumper=yaml.SafeDumper, **kwds):
    class OrderedDumper(Dumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())

    OrderedDumper.add_representer(dict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)

def read_json_file(path):
    # return json file
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_file(path, mode, data):
    # write json file
    with open(path, mode, encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def base64_to_img(bstr, file_path):
    imgdata = base64.b64decode(bstr)
    file = open(file_path, 'wb')
    file.write(imgdata)
    file.close()
    
def file_writer(file_path, content):
    with open(file_path, 'a', encoding='utf-8') as file:
        yaml.dump(
            data=content,
            stream=file,
            indent=2,
            encoding='utf-8'
        )

def create_writer(file_path):
    path = os.path.join(str(file_path))

    def writer(filname, content=None):
        target = os.path.join(path, filname)
        target_dir = os.path.dirname(target)
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
        if content==None:
            return target
        with open(target, 'w', encoding='utf-8') as file:
            file.write(content)
    
    return writer

def get_filename_and_extension(url):
    parsed_url = urlparse(url)
    path = parsed_url.path
    filename_with_extension = path.split('/')[-1]
    filename = filename_with_extension.split('.')[0]
    extension = filename_with_extension.split('.')[-1]
    return filename, extension

def ordered_yaml_dump(data, stream=None, Dumper=yaml.SafeDumper, **kwds):
    class OrderedDumper(Dumper):
        pass

    def _dict_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())

    OrderedDumper.add_representer(dict, _dict_representer)
    return yaml.dump(data, stream, OrderedDumper, **kwds)

def read_json_file(path):
    # return json file
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_file(path, mode, data):
    # write json file
    with open(path, mode, encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


def base64_to_img(bstr, file_path):
    imgdata = base64.b64decode(bstr)
    file = open(file_path, 'wb')
    file.write(imgdata)
    file.close()