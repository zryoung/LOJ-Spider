
import os

import zipfile
from superagent import get, proxy
from superagent.errors import ResponseError
from superagent.utils import create_progress_bar
from tempfile import TemporaryDirectory

import aiohttp
import yaml
from pathlib import Path
from typing import List, Dict, Any, Union
import re
import asyncio
from urllib.parse import urlparse

RE_SYZOJ = re.compile(r'(https?):\/\/([^/]+)\/(problem|p)\/([0-9]+)\/?', re.IGNORECASE)

def download_file(url: str, path: str = None, retries: int = 3):
    if path is not None:
        return _download(url, path, retries)
    return get(url).timeout({"response": 3000, "deadline": 60000}).proxy(p).retry(retries)

def _download(url: str, path: str, retries: int):
    with open(path, 'wb') as f:
        response = get(url).retry(retries).timeout({"response": 3000, "deadline": 60000}).proxy(p)
        response.pipe(f)
        response.wait()
    return path

def create_writer(id):
    dir = Path('downloads') / id
    dir.mkdir(parents=True, exist_ok=True)
    return lambda filename, content=None: (dir / filename).write_text(content or '')

async def v2(url: str):
    try:
        response = await get(f'{url}export')
        response.raise_for_status()
    except ResponseError as e:
        raise Exception("Cannot connect to target server") from e

    problem = response.body['obj']
    content = ''
    if problem['description']:
        content += f"## 题目描述\n\n{problem['description']}"
    if problem['input_format']:
        content += f"## 输入格式\n\n{problem['input_format']}"
    if problem['output_format']:
        content += f"## 输出格式\n\n{problem['output_format']}"
    if problem['example']:
        content += f"## 样例\n\n{problem['example']}"
    if problem['hint']:
        content += f"## 提示\n\n{problem['hint']}"
    if problem['limit_and_hint']:
        content += f"## 限制与提示\n\n{problem['limit_and_hint']}"

    parsed_url = urlparse(url)
    pid = parsed_url.path.split('/')[1]
    write = create_writer(f"{parsed_url.netloc}/{pid}")
    write('problem_zh.md', content)
    write('problem.yaml', yaml.dump({
        'title': problem['title'],
        'owner': 1,
        'tag': problem['tags'] or [],
        'pid': f'P{pid}',
        'nSubmit': 0,
        'nAccept': 0,
    }))

    file = Path(os.tmpdir()) / 'hydro' / f'import_{pid}.zip'
    with file.open('wb') as f:
        response = await download_file(f'{url}testdata/download')
        response.pipe(f)
        response.wait()

    with zipfile.ZipFile(file, 'r') as z:
        z.extractall(Path('testdata'))

    config = {
        'time': f"{problem['time_limit']}ms",
        'memory': f"{problem['memory_limit']}m",
        'filename': problem['file_io_input_name'].split('.')[0] if problem['file_io_input_name'] else None,
        'type': 'default' if problem['type'] == 'traditional' else problem['type'],
    }
    write('testdata/config.yaml', yaml.dump(config))

    if problem['have_additional_file']:
        file1 = Path(os.tmpdir()) / 'hydro' / f'import_{pid}_a.zip'
        with file1.open('wb') as f:
            response = await download_file(f'{url}download/additional_file')
            response.pipe(f)
            response.wait()

        with zipfile.ZipFile(file1, 'r') as z:
            z.extractall(Path('additional_file'))





async def v3(protocol: str, host: str, pid: int):
    report2.update(0, 'Fetching info')
    async with aiohttp.ClientSession() as session:
        url = f"{protocol}://{host if host == 'loj.ac' else 'api.loj.ac'}/api/problem/getProblem"
        data = {
            "displayId": pid,
            "localizedContentsOfAllLocales": True,
            "tagsOfLocale": "zh_CN",
            "samples": True,
            "judgeInfo": True,
            "testData": True,
            "additionalFiles": True,
        }
        async with session.post(url, json=data) as response:
            result = await response.json()

    if not result["body"]["localizedContentsOfAllLocales"]:
        # Problem doesn't exist
        return

    def create_writer(path: str):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        return open(path, "w")

    for c in result["body"]["localizedContentsOfAllLocales"]:
        content = ""
        sections = c["contentSections"]
        add = False
        for section in sections:
            if section["type"] == "Sample":
                if section["sampleId"] == 0:
                    add = True
                content += f"\
\`\`\`input{add and section['sampleId'] + 1 or section['sampleId']}\
{result['body']['samples'][section['sampleId']]['inputData']}\
\`\`\`\
\
\`\`\`output{add and section['sampleId'] + 1 or section['sampleId']}\
{result['body']['samples'][section['sampleId']]['outputData']}\
\`\`\`\
\
"
            else:
                content += f"## {section['sectionTitle']}\
\
{section['text']}\
\n\n"
        locale = c["locale"]
        if locale == "en_US":
            locale = "en"
        elif locale == "zh_CN":
            locale = "zh"
        write = create_writer(f"{host}/{pid}/problem_{locale}.md")
        write.write(content)
        write.close()

    tags = [node["name"] for node in result["body"]["tagsOfLocale"]]
    title = [
        *filter(lambda x: x["locale"] == "zh_CN", result["body"]["localizedContentsOfAllLocales"]),
        *result["body"]["localizedContentsOfAllLocales"],
    ][0]["title"]
    write = create_writer(f"{host}/{pid}/problem.yaml")
    write.write(yaml.dump({
        "title": title,
        "owner": 1,
        "tag": tags,
        "pid": f"P{pid}",
        "nSubmit": result["body"]["meta"]["submissionCount"],
        "nAccept": result["body"]["meta"]["acceptedSubmissionCount"],
    }))
    write.close()

    judge = result["body"]["judgeInfo"]
    rename = {}
    if judge:
        report2.update(0, 'Fetching judge config')
        config = {
            "time": f"{judge['timeLimit']}ms",
            "memory": f"{judge['memoryLimit']}m",
        }
        if judge.get("extraSourceFiles"):
            files = []
            for key in judge["extraSourceFiles"]:
                for file in judge["extraSourceFiles"][key]:
                    files.append(file)
            config["user_extra_files"] = files
        if judge.get("checker") and judge["checker"]["type"] == "custom":
            config["checker_type"] = judge["checker"].get("interface") == "legacy" and "syzoj" or judge["checker"]["interface"]
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
                current = {
                    "score": subtask["points"],
                    "type": ScoreTypeMap[subtask["scoringType"]],
                    "cases": [{"input": inputFile, "output": outputFile} for inputFile, outputFile in subtask["testcases"]],
                }
                if subtask.get("dependencies"):
                    current["if"] = subtask["dependencies"]
                config["subtasks"].append(current)
        write = create_writer(f"{host}/{pid}/testdata/config.yaml")
        write.write(Buffer.from(yaml.dump(config)))
        write.close()

    downloaded_size = 0
    total_size = sum(item["size"] for item in result["body"]["testData"]) + sum(item["size"] for item in result["body"]["additionalFiles"])
    downloaded_count = 0
    total_count = len(result["body"]["testData"]) + len(result["body"]["additionalFiles"])
    r, a = await asyncio.gather(
        *[
            session.post(
                f"{protocol}://{host if host == 'loj.ac' else 'api.loj.ac'}/api/problem/downloadProblemFiles",
                json={
                    "problemId": result["body"]["meta"]["id"],
                    "type": "TestData",
                    "filenameList": [node["filename"] for node in result["body"]["testData"]],
                },
                proxy=p,
                timeout=10000,
                retries=5,
            ),
            session.post(
                f"{protocol}://{host if host == 'loj.ac' else 'api.loj.ac'}/api/problem/downloadProblemFiles",
                json={
                    "problemId": result["body"]["meta"]["id"],
                    "type": "AdditionalFile",
                    "filenameList": [node["filename"] for node in result["body"]["additionalFiles"]],
                },
                proxy=p,
                timeout=10000,
                retries=5,
            ),
        ]
    )
    if r.status != 200 or a.status != 200:
        raise Exception(f"Error: {r.status} {a.status}")
    tasks = []
    for f in r.json()["downloadInfo"]:
        tasks.append([rename[f["filename"]] or f["filename"], "testdata", f["downloadUrl"], result["body"]["testData"][f["filename"]]["size"]])
    for f in a.json()["downloadInfo"]:
        tasks.append([rename[f["filename"]] or f["filename"], "additional_file", f["downloadUrl"], result["body"]["additionalFiles"][f["filename"]]["size"]])
    err = None
    for name, type, url, expected_size in tasks:
        try:
            filepath = type + "/" + name
            if Path(f"downloads/{host}/{pid}/{filepath}").exists():
                size = Path(f"downloads/{host}/{pid}/{filepath}").stat().st_size
                if size == expected_size:
                    downloaded_size += size
                    downloaded_count += 1
                    continue
            await download_file(url, write(filepath))
            downloaded_size += expected_size
            downloaded_count += 1
            report2.update(downloaded_size / total_size, f"({size(downloaded_size)}/{size(total_size)}) {name} ({downloaded_count + 1}/{total_count})")
        except Exception as e:
            print(e)
            err = e
    if err:
        raise err
    report2.update(downloaded_size / total_size, "")



async def run(url: str):
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
        count = end - start + 1
        for i in range(start, end + 1):
            report1.update((i - start) / count, prefix + str(i))
            if version == 3:
                try:
                    await v3(protocol, host, i)
                except Exception as e:
                    try:
                        await v3(protocol, host, i)
                    except Exception as e:
                        print(e)
            else:
                await v2(f"{prefix}{i}/")
        report2.update(1, '')
        return
    assert re.match(RE_SYZOJ, url), 'This is not a valid SYZOJ/Lyrio problem detail page link.'
    if not url.endswith('/'):
        url += '/'
    protocol, host, n, pid = urlparse(url).scheme, urlparse(url).netloc, urlparse(url).path.split('/')[-2], urlparse(url).path.split('/')[-1]
    if n == 'p':
        await v3(protocol, host, int(pid))
    else:
        await v2(url)

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("loj-download <url>")
    else:
        try:
            asyncio.run(run(sys.argv[2]))
        except Exception as e:
            print(e)
            time.sleep(1)
            print(e)
            sys.exit(1)
