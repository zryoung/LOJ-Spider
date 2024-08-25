## loj-download的python版


import json
import random
import os, re, requests, sys, yaml, time
import time
import threading
from json import dumps
from requests import packages
from urllib.parse import urlparse
import traceback
from tenacity import retry, stop_after_attempt, wait_random
from loguru import logger

from config import DOWNLOAD_PATH
from util import request_get, request_post

packages.urllib3.disable_warnings()  # 去除警告信息


RE_SYZOJ = re.compile(r'(https?):\/\/([^/]+)\/(problem|p)\/([0-9]+)\/?', re.IGNORECASE)
__dirname = DOWNLOAD_PATH  # 下载目录放到项目目录的父目录


ScoreTypeMap = {
    "GroupMin": "min",
    "Sum": "sum",
    "GroupMul": "max",
}
LanguageMap = {
    "cpp": "cc",
}


@retry(stop=stop_after_attempt(5), wait=wait_random(1, 3), reraise=True)
def resume_download(url, file_path, retry=3):
    # try:
    # 第一次请求是为了得到文件总大小
    r1 = request_get(url, stream=True, verify=False)
    # 有些文件没有conteng-length这个信息
    if not r1.headers.get("Content-Length"):
        # print('hi')
        with open(file_path, 'ab') as file:
            file.write(r1.content)

        # print(f'{file_path}下载完成')
        return
    
    total_size = int(r1.headers["Content-Length"])

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
    # print(f'{file_path}下载完成')
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
    # print(img_arr)
    for img_url in img_arr:
        filename, extension = get_filename_and_extension(url=img_url)
        pic_file_path = os.path.join(picpath, f'{filename}.{extension}')
        try:
            resume_download(url=img_url, file_path=pic_file_path)
        except Exception as e:
            logger.error(f'图片下载出错：{img_url},错误信息：{e}')
        content = content.replace(img_url, f'file://{filename}.{extension}?type=additional_file')

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

@retry(stop=stop_after_attempt(5),wait=wait_random(1, 3),reraise=True)
def get_problem(protocol, host, pid):

    url = f"{protocol}://{'api.loj.ac' if host=='loj.ac' else host}/api/problem/getProblem"    
    result = request_post(
        url,
        stream=True,
        verify=False,
        timeout=(5, 5),
        headers={
            "Content-Type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10",
        },
        data=dumps(
            {
                "displayId": pid,
                "testData": True,
                "additionalFiles": True,
                "localizedContentsOfAllLocales": True,
                "tagsOfLocale": "zh_CN",
                "judgeInfo": True,
                "judgeInfoToBePreprocessed": True, # 获取subtasks需要这个开关
                "samples": True,
            }
        ),
    ).json()
    
    if not result.get('localizedContentsOfAllLocales'):
        return f'{pid}没有该题'
    
    writer = create_writer(os.path.join(host,str(pid)))
    for c in result['localizedContentsOfAllLocales']:
        content = ''
        sections = c['contentSections']
        add = False
        sample_title = False

        for section in sections:
            if section['type'] == 'Sample':
                if not sample_title:
                    content += f'\n## 样例\n\n'
                    sample_title = True
                if section['sampleId'] == 0:
                    add = True
                content += f'''
```input{section['sampleId']+1 if add else section['sampleId']}
{result['samples'][section['sampleId']]['inputData']}
```

```output{section['sampleId']+1 if add else section['sampleId']}
{result['samples'][section['sampleId']]['outputData']}
```
                '''                
            else:
                content += f'\n## {section["sectionTitle"]}\n'
                # TODO: 下载图片 LOJ6610,4175有图片,LOJ4174多图
                
            pic_path = os.path.join(__dirname, host, str(pid), 'additional_file')

            new_content = get_and_replace_images(content=section["text"], picpath=pic_path)
            content += f'\n{new_content}\n\n'
        
        locale = c['locale']
        if locale == 'en_US':
            locale = 'en'
        elif locale == 'zh_CN':
            locale = 'zh'
        writer(f'problem_{locale}.md', content=content)
    
    tags = [ node['name'] for node in result['tagsOfLocale'] ]
    
    title = [
        *filter(lambda x: x['locale'] == 'zh_CN', result['localizedContentsOfAllLocales'])
    ][0]['title']
    writer('problem.yaml', ordered_yaml_dump({
        "title": title,
        "owner": 1,
        "tag": tags, 
        # "pid": f"P{pid}",
        # "nSubmit": result["meta"]["submissionCount"],
        # "nAccept": result["meta"]["acceptedSubmissionCount"],
    },
    allow_unicode=True,
    ))

    judge = result['judgeInfo']

    rename = dict()
    if judge:
        config = dict()
        if judge.get("timeLimit"):
            config["time"] = f'{judge["timeLimit"]}ms'
        elif judge.get("checker").get("timeLimit"):
            config["time"] = f'{judge["checker"]["timeLimit"]}ms'
        if judge.get("memoryLimit"):
            config["memory"] = f'{judge["memoryLimit"]}m'
        elif judge.get("checker").get("memoryLimit"):
            config["memory"] = f'{judge["checker"]["memoryLimit"]}m'

        if judge.get("extraSourceFiles"):
            files = []
            for key in judge["extraSourceFiles"]:
                for file in judge["extraSourceFiles"][key]:
                    files.append(file)
            config["user_extra_files"] = files
        if judge.get("checker") and judge["checker"]["type"] == "custom":
            config["checker_type"] = "syzoj" if judge["checker"].get("interface") == "legacy" else judge["checker"]["interface"]
            if LanguageMap[judge["checker"]["language"]]:
                rename[judge["checker"]["filename"]] = f"chk.{LanguageMap[judge['checker']['language']]}"
                config["checker"] = f"chk.{LanguageMap[judge['checker']['language']]}"
            else:
                config["checker"] = judge["checker"]["filename"]
        if judge.get("fileIo") and judge["fileIo"].get("inputFilename"):
            config["filename"] = judge["fileIo"]["inputFilename"].split(".")[0]

        if judge.get("subtasks"):
            config["subtasks"] = []
            for subtask in judge["subtasks"]:
                # current = OrderedDict()
                current = dict()
                if subtask.get("points"):
                    current["score"] = subtask["points"]
                current["type"] = ScoreTypeMap[subtask["scoringType"]]
                # TODO:559,交互题，没有output,出错
                # current["cases"] = [{"input": item["inputFile"], "output": item["outputFile"]} for item in subtask["testcases"]]
                current["cases"] = []
                current_case = []
                for item in subtask.get("testcases", []):
                    if "inputFile" in item:
                        current["cases"].append({"input": item["inputFile"]})
                    if "outputFile" in item:
                        current["cases"].append({"output": item["outputFile"]})
                
                if subtask.get("dependencies"):
                    current["if"] = subtask["dependencies"]
                config["subtasks"].append(current)
        writer('testdata/config.yaml', ordered_yaml_dump(config))

    try:
        url = f"{protocol}://{'api.loj.ac' if host=='loj.ac' else host}/api/problem/downloadProblemFiles"  
        # testData
        data = dumps(
                {
                "problemId": result["meta"]["id"],
                "type": "TestData",
                "filenameList": [node["filename"] for node in result["testData"]],
                }
            )
        r = request_post(
            url,
            stream=True,
            verify=False,
            timeout=(5, 5),
            headers={
                "Content-Type": "application/json",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10",
            },
            data=data,
        )

        tasks = []  # 数据下载任务
        for f in r.json()["downloadInfo"]:
            if rename.get(f['filename']):
                filename = rename[f['filename']]
            else:
                filename = f['filename']
            size = [*filter(lambda x: x['filename']==f['filename'], result['testData'])][0]['size']
            tasks.append([ filename , 'testdata', f['downloadUrl'], size])

        # additionalFiles
        data = dumps(
                {
                "problemId": result["meta"]["id"],
                "type": "AdditionalFile",
                "filenameList": [node["filename"] for node in result["additionalFiles"]],
                }
            )
        r = request_post(
            url,
            stream=True,
            verify=False,
            timeout=(5, 5),
            headers={
                "Content-Type": "application/json",
                "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10",
            },
            data=data,
        )
        for f in r.json()["downloadInfo"]:
            if rename.get(f['filename']):
                filename = rename[f['filename']]
            else:
                filename = f['filename']
            size = [*filter(lambda x: x['filename']==f['filename'], result['additionalFiles'])][0]['size']
            tasks.append([ filename , 'additional_file', f['downloadUrl'], size])
    except Exception as e:
        logger.error(f'{pid} 获取测试数据出错。原因：{e}')
    
    # 多线程下载
    threads = []
    for name, type, url, expected_size in tasks:
        try:
            
            filepath = os.path.join(__dirname,host,str(pid),type,name)

            thread = threading.Thread(target=resume_download, args=(url, filepath))
            thread.start()
            threads.append(thread)            
        except Exception as e:
            logger.error(f'{pid} 数据下载出错。错误原因：{e}')
            # raise Exception(f'{pid} 数据下载出错。错误原因：{e}')
    for thread in threads:
        thread.join()

    message = f'{pid}下载完成。{time.strftime("%Y-%m-%d %H:%M", time.localtime())}'
    print(message)
    return message
   

def run(url: str):
    if re.match(r'^(.+)/(\d+)\.\.(\d+)$', url):
        res = re.match(r'^(.+)/(\d+)\.\.(\d+)$', url)
        prefix = res.group(1)
        start = int(res.group(2))
        end = int(res.group(3))
        if not (isinstance(start, int) and isinstance(end, int) and start <= end):
            raise ValueError('end')
        version = 2
        if not prefix.endswith('/'):
            prefix += '/'
        if prefix.endswith('/p/'):
            version = 3
        else:
            prefix = f"{prefix.split('/problem/')[0]}/problem/"
        base = f"{prefix}{start}/"
        assert re.match(RE_SYZOJ, base), 'prefix'
        protocol, host = urlparse(base).scheme, urlparse(base).netloc

        for i in range(start, end + 1):
            if version == 3:
                try:
                    time.sleep(random.random()*5)
                    message = get_problem(protocol, host, i)
                    print(message)
                except Exception as e:
                    print(f'{i}出错，出错原因：{e}')
                    print('=' * 64)
                    print(traceback.format_exc())
            # else:
            #     await v2(f"{prefix}{i}/")
        return
    assert re.match(RE_SYZOJ, url), 'This is not a valid SYZOJ/Lyrio problem detail page link.'
    if not url.endswith('/'):
        url += '/'
    protocol, host, n, pid = urlparse(url).scheme, urlparse(url).netloc, urlparse(url).path.split('/')[-2], urlparse(url).path.split('/')[-1]
    if n == 'p':
        get_problem(protocol, host, int(pid))
    # else:
    #     await v2(url)



if __name__ == "__main__":
    
    # print(sys.argv)
    if len(sys.argv) < 2:
        print("loj-download <url>")
    else:
        try:
            run(sys.argv[1])
            # 以下报错：a coroutine was expected, got None
            # asyncio.run(run(sys.argv[1]))
        except Exception as e:
            print(e)            
            print('=' * 16)
            print(traceback.format_exc())

            time.sleep(1)
            sys.exit(1)
    # 测试get_problem
    # get_problem('https','loj.ac', 6930)
    # 测试下载
    # url = "https://files.loj.ac/libreoj-data/25cb5d69-054a-42c8-9bcf-fcac8880c58c?response-content-disposition=attachment%3B%20filename%3D%22secret-41-gen.in%22&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=5d9c40ebc7ca054399154bcebc5c3a5c%2F20240807%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20240807T014707Z&X-Amz-Expires=72000&X-Amz-SignedHeaders=host&X-Amz-Signature=19fefee1ee340a4d06a99f5042316e41645a37cd1cacd2f0df4fe06f09fd695d"
    # path = os.path.join(__dirname, "data.in")
    # resume_download(url, file_path=path)
