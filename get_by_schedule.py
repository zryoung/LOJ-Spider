from datetime import timedelta, timezone, datetime
import functools
import json
import random
import schedule
import os, re, requests, sys, yaml
# import time
import threading
from json import dumps
from requests import packages
from urllib.parse import urlparse
import traceback
from tenacity import retry, stop_after_attempt, wait_random
from config import DOWNLOAD_PATH
from loj_download import *
from loguru import logger

from util import request_post


# pid_list = []

def catch_exceptions(cancel_on_failure=False):
    def catch_exceptions_decorator(job_func):
        @functools.wraps(job_func)
        def wrapper(*args, **kwargs):
            try:
                return job_func(*args, **kwargs)
            except:
                import traceback
                print(traceback.format_exc())
                if cancel_on_failure:
                    return schedule.CancelJob
        return wrapper
    return catch_exceptions_decorator

# @logger.catch
# @catch_exceptions()
# @retry(stop=stop_after_attempt(5),wait=wait_random(1, 3),reraise=True)
def get_pid_list():    
    skipCount = 0
    takeCount = 50
    pid_list = []
    try:
        num = query_problem_set(skipCount, takeCount)["count"]
        print(f'题目总数：{num}')
        
        for skipCount in range(2967, num, takeCount):
            logger.info(f'获取题号列表{skipCount}')
            result = query_problem_set(skipCount, takeCount)["result"]

            for item in result:
                pid_list.append(item['meta']['displayId'])
            # print(skipCount)
        return pid_list

    except Exception as e:
        logger.error(f'获取题号列表出错，{skipCount=},{takeCount=}')

# @logger.catch
# @catch_exceptions()
@retry(stop=stop_after_attempt(5),wait=wait_random(1, 3),reraise=True)
def query_problem_set(skipCount, takeCount):
    return request_post("https://api.loj.ac/api/problem/queryProblemSet",
                    stream=True,
                    verify=False,
                    timeout=(5, 5), 
                    headers={"Content-Type": "application/json"},
                    data=dumps({"locale": "zh_CN", "skipCount": skipCount, "takeCount": takeCount})
                ).json()


# 新增一个变量来跟踪当前的查询时间范围
current_query_time = 0

@catch_exceptions()
def get_latest_problem():
    global current_query_time
    logger.info(f"获取最新题目({current_query_time}小时内)")
    try:
        list = request_get("https://api.loj.ac/api/homepage/getHomepage?locale=zh_CN", headers={
            "Content-Type": "application/json",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
        }).json()["latestUpdatedProblems"]
        # print(list)

        p_list = []
        for item in list:
            # 假设你有一个 UTC 时间字符串
            utc_time_str = item["meta"]["publicTime"]
            # 将字符串解析为 datetime 对象，并指定时区为 UTC
            utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)
            # 获取当前的 UTC 时间
            current_utc_time = datetime.now(timezone.utc)
            # 计算时间差
            time_difference = current_utc_time - utc_time
            # 获取时间差的秒数
            difference_in_seconds = time_difference.total_seconds()
            interval_time = difference_in_seconds // 3600 

            if interval_time <= current_query_time:  
                print("get new problem.", item["meta"]["displayId"])
                try:
                    pid = item["meta"]["displayId"]
                    p_list.append(pid)
                except Exception as e:
                    logger.error(f'{pid},message:{e}')

        get_problem_from_list(p_list=p_list)
        print(f"wait next time ({int_time} hours later) to get new problem.")
        # 如果获取成功，恢复查询时间范围为 int_time 小时
        current_query_time = int_time
    except Exception as e:
        logger.error(f"获取最新题目出错: {e}")
        # 如果出错，增加查询时间范围
        current_query_time += int_time
        print(f"获取失败，下次将获取 {current_query_time} 小时内的题目。")


@catch_exceptions()
def get_problem_from_list(p_list):
    for pid in p_list:
        try:
            run_in_thread(get_problem, 'https', 'loj.ac', pid)
        except Exception as e:
            logger.error(f'{pid},message:{e}')

def run_in_thread(func, *args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.start()

if __name__ == '__main__':
    logger.add(os.path.join(DOWNLOAD_PATH, 'log.txt'))
    
    int_time = 24 #默认爬取24小时内题目
    if len(sys.argv)==2:
        int_time = int(sys.argv[1]) #运行参数设置最新题目时间段
    current_query_time = int_time
    run_in_thread(get_latest_problem)
    schedule.every(int_time).hours.do(run_in_thread, get_latest_problem)

    while True:
        schedule.run_pending()
        time.sleep(1)
    # get_latest_problem()
