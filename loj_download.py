## loj-download的python版


from concurrent.futures import ThreadPoolExecutor
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
from downloader import Downloader
from util import create_writer, get_and_replace_images, log_while_last_retry, ordered_yaml_dump, request_get, request_post, resume_download

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
    "python": "py",
    "haskell": "hs",
}


@retry(stop=stop_after_attempt(5), retry_error_callback=log_while_last_retry,wait=wait_random(1, 3),reraise=True)
def get_problem(protocol, host, pid):
    logger.info(f'正在获取题目{pid}...')
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
        logger.error(f'{pid}没有该题')
        return f'{pid}没有该题'
    
    title = [*filter(lambda x: x['locale'] == 'zh_CN', result['localizedContentsOfAllLocales'])][0]['title']
    title1 = re.sub(r'[\\/:*?"<>|\.]','-',title).strip()  # 替换掉特殊字符
    # 题目文件夹：“题号+标题”
    problem_path = os.path.join(DOWNLOAD_PATH, host,str(pid) + title1)
    writer = create_writer(problem_path)
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
                
            pic_path = os.path.join(problem_path, 'additional_file')

            new_content = get_and_replace_images(content=section["text"], picpath=pic_path)
            content += f'\n{new_content}\n\n'
        
        locale = c['locale']
        if locale == 'en_US':
            locale = 'en'
        elif locale == 'zh_CN':
            locale = 'zh'
        writer(f'problem_{locale}.md', content=content)
    
    tags = [ node['name'] for node in result['tagsOfLocale'] ]
    
    
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
        try:
            config = dict()
            if judge.get("timeLimit"):
                config["time"] = f'{judge.get("timeLimit", 1000)}ms'
            elif judge.get("checker").get("timeLimit"):
                config["time"] = f'{judge["checker"]["timeLimit"]}ms'
            if judge.get("memoryLimit"):
                config["memory"] = f'{judge.get("memoryLimit", 256)}m'
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
                    # if subtask.get("points"):
                    #     current["score"] = subtask["points"]
                    current["score"] = subtask.get("points", 100)
                    current["type"] = ScoreTypeMap[subtask["scoringType"]]
                    # TODO:559,交互题，没有output,出错
                    # current["cases"] = [{"input": item["inputFile"], "output": item["outputFile"]} for item in subtask["testcases"]]
                    current["cases"] = []
                    for item in subtask.get("testcases", []):
                        case = {}
                        if "inputFile" in item:
                            case["input"] = item["inputFile"]
                        if "outputFile" in item:
                            case["output"] = item["outputFile"]
                        current["cases"].append(case)
                    # current["cases"] =[{'input': i['inputFile'], 'output': i['outputFile']} for i in subtask.get("testcases", [])]
                    
                    # if subtask.get("dependencies"):
                    #     current["if"] = subtask["dependencies"]
                    current["if"] = subtask.get("dependencies", [])
                    config["subtasks"].append(current)
            writer('testdata/config.yaml', ordered_yaml_dump(config))
        except Exception as e:
            logger.error(f'\n{traceback.format_exc()}\n')

    # try:


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
    
    # 使用线程池来管理下载任务
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(download_file, url, os.path.join(problem_path, type, name), size) for name, type, url, size in tasks]
        for future in futures:
            future.result()  # 等待所有任务完成
            
    logger.info(f'{pid}下载完成。')
    return f'{pid}下载完成。'
   
def download_file(url, filepath, expected_size):
    try:
        if os.path.exists(filepath):
            temp_size = os.path.getsize(filepath)  # 本地已经下载的文件大小
            # 如果文件已下载完成，则不下载
            if temp_size == expected_size:
                return
        downloader = Downloader(url, filepath, num_chunks=4, enable_progress=False)
        downloader.download()
    except Exception as e:
        logger.error(f'数据下载出错。错误原因：{e}')
        logger.error(f"\n{traceback.format_exc()}\n")
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

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(get_problem, protocol, host, i) for i in range(start, end + 1)]
            for future in futures:
                future.result()  # 等待所有任务完成

        # for i in range(start, end + 1):
        #     if version == 3:
        #         try:
        #             time.sleep(random.random()*5)
        #             message = get_problem(protocol, host, i)
        #             logger.info(message)
        #         except Exception as e:
        #             logger.error(f'{i}出错，出错原因：{e}')
        #             logger.error(f"\n{traceback.format_exc()}\n")
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
    logger.add(os.path.join(DOWNLOAD_PATH, 'log.txt'))

    if len(sys.argv) < 2:
        print("py loj_download.py <url>") # py loj_download.py https://loj.ac/p/4758..4758
    else:
        try:
            run(sys.argv[1])
            # 以下报错：a coroutine was expected, got None
            # asyncio.run(run(sys.argv[1]))
        except Exception as e:
            logger.error(e)

            time.sleep(1)
            sys.exit(1)
    # 测试get_problem
    # get_problem('https','loj.ac', 6930)
    # 测试下载
    # url = "https://files.loj.ac/libreoj-data/25cb5d69-054a-42c8-9bcf-fcac8880c58c?response-content-disposition=attachment%3B%20filename%3D%22secret-41-gen.in%22&X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=5d9c40ebc7ca054399154bcebc5c3a5c%2F20240807%2Fus-east-1%2Fs3%2Faws4_request&X-Amz-Date=20240807T014707Z&X-Amz-Expires=72000&X-Amz-SignedHeaders=host&X-Amz-Signature=19fefee1ee340a4d06a99f5042316e41645a37cd1cacd2f0df4fe06f09fd695d"
    # path = os.path.join(__dirname, "data.in")
    # resume_download(url, file_path=path)
