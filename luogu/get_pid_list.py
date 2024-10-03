import json
import os
import sys
import time
sys.path.append(os.getcwd())
from util import request_get, write_json_file
from config import LUOGU_COOKIE,DOWNLOAD_PATH

def get_problem_list(page=1):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Host': 'www.luogu.com.cn',
        'Connection': 'keep-alive',
        # 'Cookie': '__client_id=ca02d46480bf42032e4d99e690eec5e887a5228c; _uid=630003'
        'Cookie': LUOGU_COOKIE
    }
    problem_list_url = f'https://www.luogu.com.cn/problem/list?page={page}&_contentOnly=1&type=AT'

    problem_list_rsp = request_get(problem_list_url,headers=headers)
    problem_list_js = json.loads(problem_list_rsp.text)['currentData']['problems']['result']
    problem_list = [(p['pid'], p['title']) for p in problem_list_js]

    # print(problem_list)
    return(problem_list)


if __name__ == '__main__':
    data = []
    for page in range(1,123):
        # data += get_problem_list(page)
        print(f'page {page}')
        data.extend(get_problem_list(page))
        time.sleep(10)
    
    
    write_json_file(os.path.join(DOWNLOAD_PATH,'at_pid_list.json'),'w',data)