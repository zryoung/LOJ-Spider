import json
import os
import random
import re
import threading
import zipfile
# from datetime import time
import time

import pymongo
from scrapy import Selector
from utils import Redis, HashEncode

import html2text
from requests import *

domain = r'http://www.usaco.org/'

debug_flag = True
delay_time = 2  # 延迟请求2秒

myclient = pymongo.MongoClient('mongodb://192.168.13.240:27017/')
mydb = myclient['oi']

# Markdown中图片语法![](url)或者<img src='' />
img_patten = r'!\[.*?\]\((.*?)\)|<img.*?src=[\'\"](.*?)[\'\"].*?>'


# 下载文件中的图片，并替换url
# def replace_md_url(md_file):
#     pass
#     """
#     把指定MD文件中引用的图片下载到本地，并替换URL
#     """
#
#     if os.path.splitext(md_file)[1] != '.md':
#         print('{}不是Markdown文件，不做处理。'.format(md_file))
#         return
#
#     cnt_replace = 0
#     # 本次操作时间戳
#     dir_ts = time.strftime('%Y%m', time.localtime())
#     isExists = os.path.exists(dir_ts)
#     # 判断结果
#     if not isExists:
#         os.makedirs(dir_ts)
#     with open(md_file, 'r', encoding='utf-8') as f:  # 使用utf-8 编码打开
#         post = f.read()
#         matches = re.compile(img_patten).findall(post)
#         if matches and len(matches) > 0:
#             # 多个group整合成一个列表
#             for match in list(chain(*matches)):
#                 if match and len(match) > 0:
#                     array = match.split('/')
#                     file_name = array[len(array) - 1]
#                     file_name = dir_ts + "/" + file_name
#                     img = requests.get(match, headers=headers)
#                     f = open(file_name, 'ab')
#                     f.write(img.content)
#                     new_url = "https://blog.52itstyle.vip/{}".format(file_name)
#                     # 更新MD中的URL
#                     post = post.replace(match, new_url)
#                     cnt_replace = cnt_replace + 1
#
#         # 如果有内容的话，就直接覆盖写入当前的markdown文件
#         if post and cnt_replace > 0:
#             url = "https://blog.52itstyle.vip"
#             open(md_file, 'w', encoding='utf-8').write(post)
#             print('{0}的{1}个URL被替换到{2}/{3}'.format(os.path.basename(md_file), cnt_replace, url, dir_ts))
#         elif cnt_replace == 0:
#             print('{}中没有需要替换的URL'.format(os.path.basename(md_file)))


def log(s):
    if debug_flag:
        print(s)


def log_error(s):
    print(s)


class Worker(threading.Thread):
    def __init__(self, q):
        threading.Thread.__init__(self)
        self.queue = q

    def run(self):
        while True:
            if self.queue.empty():
                break


user_agent = [
    "Mozilla/5.0 (Windows NT 6.3; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/35.0.1916.153 Safari/537.36",
    "Mozilla/5.0 (Windows NT 6.1; WOW64; rv:30.0) Gecko/20100101 Firefox/30.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_2) AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 Safari/537.75.14",
    "Mozilla/5.0 (compatible; MSIE 10.0; Windows NT 6.2; Win64; x64; Trident/6.0)",
    'Mozilla/5.0 (Windows; U; Windows NT 5.1; it; rv:1.8.1.11) Gecko/20071127 Firefox/2.0.0.11',
    'Opera/9.25 (Windows NT 5.1; U; en)',
    'Mozilla/4.0 (compatible; MSIE 6.0; Windows NT 5.1; SV1; .NET CLR 1.1.4322; .NET CLR 2.0.50727)',
    'Mozilla/5.0 (compatible; Konqueror/3.5; Linux) KHTML/3.5.5 (like Gecko) (Kubuntu)',
    'Mozilla/5.0 (X11; U; Linux i686; en-US; rv:1.8.0.12) Gecko/20070731 Ubuntu/dapper-security Firefox/1.5.0.12',
    'Lynx/2.8.5rel.1 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/1.2.9',
    "Mozilla/5.0 (X11; Linux i686) AppleWebKit/535.7 (KHTML, like Gecko) Ubuntu/11.04 Chromium/16.0.912.77 Chrome/16.0.912.77 Safari/535.7",
    "Mozilla/5.0 (X11; Ubuntu; Linux i686; rv:10.0) Gecko/20100101 Firefox/10.0",
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/54.0.2840.99 Safari/537.36',
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/96.0.4664.110 Safari/537.36 Edg/96.0.1054.62"
]


def request_get(url):

    try_times = 3  # 重试的次数
    response = None
    for i in range(try_times):
        headers = {
            "Content-Type": "application/json",
            "user-agent": random.choice(user_agent)
        }
        try:
            response = get(url, headers=headers, verify=False, proxies=None, timeout=5)
            # 注意此处也可能是302等状态码
            if response.status_code == 200:
                response.close()
                return response.text
        except Exception as e:
            # logdebug(f'requests failed {i}time')
            log_error(f'requests failed {i + 1} time,ERROR: {e}, 涉及题目：{url},user-agent:{user_agent}')
            print(f'等待{delay_time}秒')
            time.sleep(delay_time)
    if response:
        response.close()
    return ''


def get_contest_list():
    '''
    获取历年比赛信息（http://www.usaco.org/index.php?page=contests）
    :return: 历年比赛url
    '''
    html = request_get(domain + "index.php?page=contests")
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
    html = request_get(_url)
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


def is_url_exist(_url):
    hash_encode = HashEncode()
    _redis = Redis(host='192.168.13.240')
    encode = hash_encode.encode(_url)
    if not _redis.add('urls', encode):  # 检查url是否已经存在，如果存在则放弃
        return True
    else:
        return False


def remove_url(_url):
    hash_encode = HashEncode()
    _redis = Redis(host='192.168.13.240')
    encode = hash_encode.encode(_url)
    _redis.delete('urls', encode)


def get_html(_url):
    """
    获取题目描述
    :param _url: 题目描述url
    :return: html格式的题目描述
    """

    # TODO: 处理图片下载的功能
    html = request_get(_url)
    return html


def save_img(work_dir, img_url):
    path = work_dir + img_url.split('/')[-1]
    try:
        if not os.path.exists(path):
            s = requests.session()
            s.keep_alive = False  # 关闭多余连接
            r = s.get(img_url)  # 你需要的网址
            # r=requests.get(img_url)
            with open(path, 'wb') as f:
                f.write(r.content)
                f.close()
        else:
            print(path + "文件已存在！")
            return 0
    except Exception as e:
        print(img_url + ", 爬取失败！")
        return 1
    print(img_url + "已下载")
    return 0


def get_description_md(html, source=None):
    # 获得题面
    pattern = r'<div.*?class="problem-text".*?>(.*?) Contest has ended.'
    description = re.findall(pattern, html, re.M | re.S)

    description = ''.join(description)
    # description = del_html(description)
    # TODO:html转md还有BUG
    description = html2text.html2text(description)
    # description = '## 题目描述\n' + description
    if source is None:
        pass
    else:
        description = description + '\n## Source:\n\nFrom:' + source

    return description


def get_description(_url):
    """
    获取题目描述
    :param _url: 题目描述url
    :return: json格式的题目描述
    """
    # 获得题头
    html = get_html(_url)
    pattern = r'<h2>(.*?)</h2>'
    medal_title = re.findall(pattern, html)
    source = ''.join(medal_title)
    log(medal_title)

    html = get_html(_url)
    desc_en = get_description_md(html, source)
    html = get_html(_url + '&lang=zh')
    desc_zh = get_description_md(html, source)
    html = get_html(_url + '&lang=fr')
    desc_fr = get_description_md(html, source)
    html = get_html(_url + '&lang=ru')
    desc_ru = get_description_md(html, source)
    html = get_html(_url + '&lang=es')
    desc_es = get_description_md(html, source)

    # desc_zh = get_description_by_lang(_url + '&lang=zh', medal_title)
    # desc_fr = get_description_by_lang(_url + '&lang=fr', medal_title)
    # desc_ru = get_description_by_lang(_url + '&lang=ru', medal_title)
    # desc_es = get_description_by_lang(_url + '&lang=es', medal_title)

    problem = dict(en=desc_en, zh=desc_zh, fr=desc_fr, ru=desc_ru, es=desc_es)

    return json.dumps(problem)


def get_description_by_lang(url, medal_title):
    """
    按语言类型获取题面描述
    :param url: 题目描述url
    :param medal_title: 级别及标题
    :return: 题目描述
    """
    html = get_html(url)
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
        os.makedirs(directory)
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
    html = get_html(url)

    # txt = del_html(html)
    txt = html2text.html2text(html)

    return txt


def get_all(u_list, data_dir, to_file=False):
    '''
    获取所有比赛数据到数据库或文件形式
    :param u_list: 所有比赛链接集合
    :param data_dir: 测试数据保存路径
    :param to_file:是否保存为文件形式，默认为False，
    :return:
    '''
    # url_list = get_contest_list()
    # log(url_list)
    # 测试
    for url in u_list:
        link_list = get_contest_medal_list(url)  # 进入到一个比赛页面，获取所有比赛信息，包括题面，数据，题解url
        log(link_list)
        i = 0
        for link in link_list:
            # TODO:根据库内容去重
            if is_url_exist(domain + link['description']):
                log(f'题目已存在，跳过。{domain + link["description"]}')
                continue

            try:
                i += 1
                prob_name = link['medal'].replace(',', '').replace(' ', '')  # 题目名称：USACO+年+月+级别，如'USACO2022FebruaryContestSilver’
                prob_directory_name = prob_name + str(i)  # 题目文件夹
                title = 'title: 「' + prob_name + '」' + link['title'] + '\n'  # 题目标题，形如：「USACO2022FebruaryContestSilver」Gifts
                description = get_description(domain + link['description'])
                solution = get_solution(domain + link['solution'])  # 题解
                data = domain + link['data']  # 测试数据

                data_set = {'title': '「' + prob_name + '」' + link['title']}
                html = get_html(domain + link['description'])  # 获取题面html
                selector = Selector(text=html)
                lang = selector.xpath('//select[@name="lang"]/option/@value').extract()
                # 获取其它语言的题面
                for la in lang:
                    data_set[f'html_{la}'] = html = get_html(f'{domain}{link["description"]}&lang={la}')
                    data_set[f'md_{la}'] = get_description_md(html)  # 转换为markdown
                data_set['html_solution'] = get_html(domain + link['solution'])  # 获取题解的html格式文本
                data_set['md_solution'] = solution  # TODO:此处要替换

                # TODO: 设置一个数量进行批量入库，提高效率
                result = write_to_db([data_set])
                log(result)

                if not os.path.exists(data_dir):
                    os.makedirs(data_dir)

                # 下载测试数据
                test_data_dir = data_dir + prob_directory_name + '/testdata/'
                if not os.path.exists(test_data_dir):
                    os.makedirs(test_data_dir)
                get_data(data, test_data_dir)

                # 保存到文件
                if to_file:
                    write_to_file(data_dir + prob_directory_name, title, description, data, solution)
            except Exception as _e:
                remove_url(domain + link['description'])
                log_error(f'出错：{_e}, 涉及题目：{url}')


def write_to_db(data_set):
    # pass
    return mydb['document'].insert_many(data_set)


def write_to_file(directory, title, description, data, solution):
    try:
        # log(prob_directory_name)
        if not os.path.exists(directory):
            os.makedirs(directory)

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

        # 写入config.yaml
        # with open(test_data_dir + '/config.yaml', 'w') as f:
        #     f.write('')
    except Exception as e:
        log_error(f'Fail:{e}, 涉及题目：{title}')


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    # pass
    # url_list = get_contest_list()  # 获取历年比赛链接集合
    # url_list =['http://www.usaco.org/index.php?page=feb22results']
    url_list = ['http://www.usaco.org/index.php?page=dec22results']
    work_dir = r'd:/usaco2/'
    get_all(url_list, work_dir, True)
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
