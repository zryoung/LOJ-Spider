import json
import urllib.request
import requests
import bs4 as bs
import re
import os

from util import get_and_replace_images
from config import DOWNLOAD_PATH, LUOGU_COOKIE


def json_parser(html: str):
    # convert raw html to json
    # !!! a new method is discovered, this function is deprecated !!!
    try:
        pattern = r'decodeURIComponent\("(.*?)"\)'
        soup = bs.BeautifulSoup(html, "html.parser")
        script = soup.find_all("script")[0].string
        match = re.search(pattern, script)
        if match:
            content = urllib.parse.unquote(match.group(1))
            js = json.loads(content)
            return js
        else:
            print("No match found.")
            return None
    except Exception as e:
        print("Error: ", e)
        return None


def problem_markdown_parser(dict: dict, path):
    os.makedirs(path, exist_ok=True)
    # convert json to markdown
    pid = dict["pid"]
    title = dict["title"]
    pic_path = os.path.join(path, 'additional_file')

    translation = {
        "background": "题目背景",
        "description": "题目描述",
        "inputFormat": "输入格式",
        "outputFormat": "输出格式",
        "samples": "样例",
        "hint": "说明/提示",
    }

    def content_parser(content):
        # 下载图片并更换链接
        content = get_and_replace_images(content=content, picpath=pic_path)
        # remove the head and tail \n
        content = content.lstrip("\n").rstrip("\n")
        return content

    # with open(os.path.join(path, pid + "-" + title + ".md"), "a", encoding="utf-8") as f:
    with open(os.path.join(path, "problem_zh.md"), "w", encoding="utf-8") as f:
        f.write("# " + title + "\n\n")
        if dict["background"] != "":
            f.write("## " + translation["background"] + "\n\n")
            f.write(content_parser(dict["background"]) + "\n\n")
        if dict["description"] != "":
            f.write("## " + translation["description"] + "\n\n")
            f.write(content_parser(dict["description"]) + "\n\n")
        if dict["inputFormat"] != "":
            f.write("## " + translation["inputFormat"] + "\n\n")
            f.write(content_parser(dict["inputFormat"]) + "\n\n")
        if dict["outputFormat"] != "":
            f.write("## " + translation["outputFormat"] + "\n\n")
            f.write(content_parser(dict["outputFormat"]) + "\n\n")
        if dict["samples"] != []:
            i = 1
            for sample in dict["samples"]:
                # f.write("## " + translation["samples"] + " #" + str(i) + "\n\n")
                # f.write("### " + "样例输入" + " #" + str(i) + "\n\n")
                f.write(f"```input{str(i)}\n")
                f.write(content_parser(sample[0]))
                f.write("\n```\n\n")
                # f.write("### " + "样例输出" + " #" + str(i) + "\n\n")
                f.write(f"```output{str(i)}\n")
                f.write(content_parser(sample[1]))
                f.write("\n```\n\n")
                i += 1
        if dict["hint"] != "":
            f.write("## " + translation["hint"] + "\n\n")
            f.write(content_parser(dict["hint"]))
    
    os.makedirs(os.path.join(path, 'testdata'), exist_ok=True)
    with open(os.path.join(path, 'testdata/config.yaml'), "w", encoding="utf-8") as f:
        f.write(f"time: {dict['limits']['time'][0]}ms\n")
        f.write(f"memory: {dict['limits']['memory'][0] // 1024}m\n")



def solution_markdown_parser(dict: dict, path):
    # convert json to markdown
    pid = dict["problem"]["pid"]
    title = dict["problem"]["title"]
    content = dict["solutions"]["result"][0]
    # with open(os.path.join(path, pid + "-" + title + "-题解.md"), "a", encoding="utf-8") as f:
    with open(os.path.join(path, "solution_zh.md"), "w", encoding="utf-8") as f:
        f.write("# " + content["title"] + "\n\n")
        f.write(content["content"])


def config_parser():
    # return config.json
    def init_config():
        # create config.json
        config = {
            "init": False,
            "username": "",
            "password": "",
            "language": "",
            "problem": "",
            "solution": "",
        }
        with open("config.json", "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    if os.path.exists("config.json"):
        with open("config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    else:
        print("config.json not found. We will create one for you.")
        init_config()
        return None


def pid_parser(pid: str, path):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Host': 'www.luogu.com.cn',
        'Connection': 'keep-alive',
        # 'Cookie': '__client_id=ca02d46480bf42032e4d99e690eec5e887a5228c; _uid=630003'
        'Cookie': LUOGU_COOKIE
    }
    problem_url = "https://www.luogu.com.cn/problem/"
    solution_url = "https://www.luogu.com.cn/problem/solution/"

    # use requests to open the url with cookie
    problem_rsp = requests.get(problem_url + pid + "?_contentOnly=1", headers=headers)    
    problem_js = json.loads(problem_rsp.text)["currentData"]["problem"]
    n_path = os.path.join(path,problem_js['pid'] + "-" + problem_js['title'])    
        
    problem_js = json.loads(problem_rsp.text)["currentData"]["problem"]
    problem_markdown_parser(problem_js, path=n_path)

    solution_rsp = requests.get(solution_url + pid + "?_contentOnly=1", headers=headers)
    try:
        soup = bs.BeautifulSoup(solution_rsp.text, "html.parser")
        script = soup.find(id="lentille-context").string
        
        js = json.loads(script)
        i = 1
        for res in js["data"]["solutions"]["result"]:
            with open(os.path.join(n_path, f'solution{i}.md'), "w", encoding="utf-8") as f:
                f.write(res["content"])

    except Exception as e:
        print("Error: ", e)
        return None
    # print(solution_rsp.text)
    # solution_js = json.loads(solution_rsp.text)["currentData"]

    # solution_markdown_parser(solution_js, os.path.join(n_path, 'solution'))


def read_json_file():
    # return json file
    with open("test.json", "r", encoding="utf-8") as f:
        return json.load(f)


def write_json_file(data):
    # write json file
    with open("test.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

if __name__ == "__main__":
    path = os.path.join(DOWNLOAD_PATH, 'luogu')
    os.makedirs(path, exist_ok=True)
    pid_parser("p1015", path=path)