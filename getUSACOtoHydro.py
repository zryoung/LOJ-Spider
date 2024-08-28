import json
import os
import re
import threading
import zipfile

import html2text
from requests import *
from util import request_get, request_post, resume_download, get_and_replace_images, get_filename_and_extension

domain = r'http://www.usaco.org/'
work_dir = r'd:/usaco1/'
debug_flag = True


# def log(s):
#     if debug_flag:
#         print(s)


# def log_error(s):
#     print(s)


# class Worker(threading.Thread):
#     def __init__(self, q):
#         threading.Thread.__init__(self)
#         self.queue = q

#     def run(self):
#         while True:
#             if self.queue.empty():
#                 break


# def request_get(url):
#     headers = {
#         "Content-Type": "application/json",
#         "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
#                       "Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62 "
#     }
#     try_times = 3  # 重试的次数
#     response = None
#     for i in range(try_times):
#         try:
#             response = get(url, headers=headers, verify=False, proxies=None, timeout=5)
#             # 注意此处也可能是302等状态码
#             if response.status_code == 200:
#                 response.close()
#                 return response.text
#         except Exception as e:
#             # logdebug(f'requests failed {i}time')
#             log_error(f'requests failed {i + 1} time,ERROR: {e},, 涉及题目：{url}')
#     if response:
#         response.close()
#     return ''


def get_contest_list():
    html = request_get(domain + "index.php?page=contests").text
    pattern = r'<a href="(.*?results)">.*?</a>'
    links = re.findall(pattern, html, re.M)
    # log(len(link_list))
    _url_list = []
    for _url in links:
        _url_list.append(domain + _url)
    return _url_list


def get_contest_medal_list(_url):
    """
    按级别获取url
    :param _url:比赛主页url
    :return: medal：级别，title:标题，description：描述，data：数据，solution：题解
    """
    html = request_get(_url).text
    pattern1 = r"<div style:'position:relative;float:right;'>" \
               r"<b>(.*?)</b>.*?" \
               r"<a href='(.*?)'>View problem</a>.*?" \
               r"<a href='(.*?)'>Test data</a>.*?" \
               r"<a href='(.*?)'>Solution</a>"

    pattern = r'<h2><img.*?>(.*?)</h2>'
    _match = re.finditer(pattern, html)
    _pos = []
    lst = re.finditer(pattern1, html, re.M | re.S)
    # log(lst)
    # pattern1 = re.compile(r"<div style:'position:relative;float:right;'>"
    #                       r"<b>(.*?)</b>.*?"
    #                       r"<a href='(.*?)'>View problem</a>.*?"
    #                       r"<a href='(.*?)'>Test data</a>.*?"
    #                       r"<a href='(.*?)'>Solution</a>")
    # lst = pattern1.findall(html, 4000)
    for item in _match:
        log(item.group(1))
        log(item.span())
        _pos.append((item.group(1), item.start()))
    _pos.append(('END', len(html)))
    # log(_pos)
    i = 0
    _ret_list = []
    for item in lst:
        log(item.group(1))
        log(item.span())
        if _pos[i][1] < item.start() < _pos[i + 1][1]:
            pass
        else:
            i += 1
        _problem = dict()
        _problem['medal'] = _pos[i][0]
        _problem['title'] = item[1]
        _problem['description'] = item[2]
        _problem['data'] = item[3]
        _problem['solution'] = item[4]
        _ret_list.append(_problem)

    return _ret_list


def get_description(_url):
    """
    获取题目描述
    :param _url: 题目描述url
    :return: json格式的题目描述
    """
    # 获得题头
    html = request_get(_url).text
    pattern = r'<h2>(.*?)</h2>'
    medal_title = re.findall(pattern, html)
    log(medal_title)

    desc_en = get_description_by_lang(_url, medal_title)
    desc_zh = get_description_by_lang(_url + '&lang=zh', medal_title)
    desc_fr = get_description_by_lang(_url + '&lang=fr', medal_title)
    desc_ru = get_description_by_lang(_url + '&lang=ru', medal_title)
    desc_es = get_description_by_lang(_url + '&lang=es', medal_title)

    problem = dict(en=desc_en, zh=desc_zh, fr=desc_fr, ru=desc_ru, es=desc_es)

    return json.dumps(problem)


def get_description_by_lang(url, medal_title):
    """
    按语言类型获取题面描述
    :param url: 题目描述url
    :param medal_title: 级别及标题
    :return: 题目描述
    """
    html = request_get(url).text
    # 获得题面
    pattern = r'<div.*?class="problem-text".*?>(.*?) Contest has ended.'
    description = re.findall(pattern, html, re.M | re.S)

    description = ''.join(description)
    # description = del_html(description)
    description = html2text.html2text(description)
    description = '## 题目描述\n' + description
    description = description + '\n## Source:\n\nFrom:' + ''.join(medal_title)

    return description


def get_data(url, directory):
    file_name = url.split('/')[-1]
    html = get(url, stream=True)
    if not os.path.exists(directory):
        os.mkdir(directory)
    with open(directory + file_name, 'wb') as f:
        for chunk in html.iter_content(chunk_size=1024):
            if chunk:
                f.write(chunk)
    try:
        # 解压
        with zipfile.ZipFile(directory + file_name) as zf:
            zf.extractall(directory)
    except Exception as _e:
        log_error(f'解压出错：{_e}, 涉及题目：{url}')
    else:
        os.remove(directory + file_name)


def get_solution(url):
    html = request_get(url).text

    # txt = del_html(html)
    txt = html2text.html2text(html)

    return txt


def get_all(u_list):
    # url_list = get_contest_list()
    # log(url_list)
    # 测试
    for url in u_list:
        link_list = get_contest_medal_list(url)
        log(link_list)
        i = 0
        for link in link_list:
            i += 1
            prob_name = link['medal'].replace(',', '').replace(' ', '')
            prob_directory_name = prob_name + str(i)
            prob_directory_name = work_dir + prob_directory_name
            title = 'title: 「' + prob_name + '」' + link['title'] + '\n'
            description = get_description(domain + link['description'])
            solution = get_solution(domain + link['solution'])
            data = domain + link['data']
            get_one(prob_directory_name, title, description, data, solution)


def get_one(directory, title, description, data, solution):
    try:
        # log(prob_directory_name)
        if not os.path.exists(directory):
            os.mkdir(directory)

        # 写入problem.yaml
        yaml_file_name = directory + '/problem.yaml'
        # log(yaml_file_name)
        with open(yaml_file_name, 'w', encoding='utf-8') as f:
            f.write(title)

        # 写入problem.md
        md_file_name = directory + '/problem.md'
        with open(md_file_name, 'w', encoding='utf-8') as f:
            f.write(description)

        # 写入solution.md
        sol_file_name = directory + '/solution.md'

        with open(sol_file_name, 'w', encoding='utf-8') as f:
            f.write(solution)

        # 下载测试数据
        test_data_dir = directory + '/testdata/'
        if not os.path.exists(test_data_dir):
            os.mkdir(test_data_dir)
        get_data(data, test_data_dir)

        # 写入config.yaml
        # with open(test_data_dir + '/config.yaml', 'w') as f:
        #     f.write('')
    except Exception as e:
        log_error(f'Fail:{e}, 涉及题目：{title}')


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # pass
    # url_list =['http://www.usaco.org/index.php?page=feb22results']
    url_list = ['https://usaco.org/index.php?page=open24results', 'https://usaco.org/index.php?page=feb24results']
    get_all(url_list)
    # url = get_contest_medal_list('http://www.usaco.org/index.php?page=open19results')

    # get_one
    # prob_name = 'USACO2015USOpenGold'
    # prob_directory_name = prob_name + str(3)
    # prob_directory_name = work_dir + prob_directory_name
    # title = 'title: 「' + prob_name + '」Trapped in the Haybales (Gold)\n'
    # description = get_description('http://www.usaco.org/index.php?page=viewproblem2&cpid=554')
    # solution = get_solution('http://www.usaco.org/current/data/sol_trapped_gold.html')
    # data = 'http://www.usaco.org/current/data/trapped_gold.zip'
    # get_one(prob_directory_name, title, description, data, solution)

    pass
