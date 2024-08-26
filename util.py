import os
import re
import sys
from urllib.parse import urlparse
import requests
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_random
import yaml

from config import DOWNLOAD_PATH


@logger.catch
@retry(stop=stop_after_attempt(5),wait=wait_random(1, 3), reraise=True)
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

@logger.catch
@retry(stop=stop_after_attempt(5),wait=wait_random(1, 3),reraise=True)
def request_get(url, params=None, headers=None, stream=False,verify=False, timeout=(5, 5)):
    return requests.get(
        url, 
        params=params,
        headers=headers,
        stream=stream,
        verify=verify,
        timeout=timeout,
    )



@retry(stop=stop_after_attempt(5), wait=wait_random(1, 3), reraise=True)
def resume_download(url, file_path):
    # try:
    # 第一次请求是为了得到文件总大小
    r1 = request_get(url, stream=True, verify=False)
    # 有些文件没有conteng-length这个信息
    if not r1.headers.get("Content-Length"):
        with open(file_path, 'ab') as file:
            file.write(r1.content)
        return
    
    total_size = int(r1.headers["Content-Length"])

    # 这重要了，先看看本地文件下载了多少
    if os.path.exists(file_path):
        temp_size = os.path.getsize(file_path)  # 本地已经下载的文件大小
    else:
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        temp_size = 0

    if temp_size >= total_size:
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
    # except Exception as e:
    #     # data={
    #     #     "time": time.localtime(),
    #     #     "message":str(e),
    #     #     "file": file_path,
    #     #     "download_url":url
    #     # }
    #     # file_writer('fail.json', json.dumps(data, ensure_ascii=False))
    #     logger.error(f'{file_path}出错重试.{e}')
    #     raise Exception(f'{file_path}出错重试.{e}')
    #     # print(f'Error:"message:"{e},"file:"{file_path},"url:"{url}')

def file_writer(filename, content):
    with open(os.path.join(__dirname,filename), 'a', encoding='utf-8') as file:
        yaml.dump(
            data=content,
            stream=file,
            indent=2,
            encoding='utf-8'
        )

__dirname = DOWNLOAD_PATH
def create_writer(id):
    path = os.path.join(__dirname,str(id))

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

def get_and_replace_images(content, picpath):
    img_arr = re.findall(r'!\[.*?\]\((.*?)\)', content)

    if img_arr:
        os.makedirs(picpath, exist_ok=True)
    for img_url in img_arr:
        filename, extension = get_filename_and_extension(url=img_url)
        pic_file_path = os.path.join(picpath, f'{filename}.{extension}')
        try:
            resume_download(url=img_url, file_path=pic_file_path)
            content = content.replace(img_url, f'file://{filename}.{extension}?type=additional_file')
        except Exception as e:
            logger.error(f'图片下载出错：{img_url},错误信息：{e}') 
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