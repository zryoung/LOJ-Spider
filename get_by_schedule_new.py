from datetime import timedelta, timezone, datetime
import functools
import json
import random
import schedule
import os
import re
import requests
import sys
import yaml
import threading
from urllib.parse import urlparse
import traceback
from tenacity import retry, stop_after_attempt, wait_random
from config import DOWNLOAD_PATH
from loj_download import *
from loguru import logger
from util import request_post, request_get

# 配置信息
API_URL = {
    "query_problem_set": "https://api.loj.ac/api/problem/queryProblemSet",
    "get_homepage": "https://api.loj.ac/api/homepage/getHomepage"
}

REQUEST_HEADERS = {
    "Content-Type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
}

# 异常处理装饰器
def catch_exceptions(cancel_on_failure=False):
    def catch_exceptions_decorator(job_func):
        @functools.wraps(job_func)
        def wrapper(*args, **kwargs):
            try:
                return job_func(*args, **kwargs)
            except Exception as e:
                logger.error(f"执行 {job_func.__name__} 时出错: {e}")
                logger.error(traceback.format_exc())
                if cancel_on_failure:
                    return schedule.CancelJob
        return wrapper
    return catch_exceptions_decorator

# 获取题目编号列表
@catch_exceptions()
@retry(stop=stop_after_attempt(5), wait=wait_random(1, 3), reraise=True)
def get_pid_list():
    skip_count = 0
    take_count = 50
    pid_list = []
    try:
        num = query_problem_set(skip_count, take_count)["count"]
        logger.info(f'题目总数：{num}')

        for skip_count in range(2967, num, take_count):
            logger.info(f'获取题号列表，跳过 {skip_count} 条')
            result = query_problem_set(skip_count, take_count)["result"]
            for item in result:
                pid_list.append(item['meta']['displayId'])
        return pid_list
    except Exception as e:
        logger.error(f'获取题号列表出错，skip_count={skip_count}, take_count={take_count}')

# 查询题目集合
@retry(stop=stop_after_attempt(5), wait=wait_random(1, 3), reraise=True)
def query_problem_set(skip_count, take_count):
    data = {
        "locale": "zh_CN",
        "skipCount": skip_count,
        "takeCount": take_count
    }
    response = request_post(API_URL["query_problem_set"],
                            stream=True,
                            verify=False,
                            timeout=(5, 5),
                            headers=REQUEST_HEADERS,
                            data=json.dumps(data))
    return response.json()

# 判断题目是否在指定时间范围内
def is_problem_within_time_range(problem, current_query_time):
    utc_time_str = problem["meta"]["publicTime"]
    utc_time = datetime.strptime(utc_time_str, "%Y-%m-%dT%H:%M:%S.000Z").replace(tzinfo=timezone.utc)
    current_utc_time = datetime.now(timezone.utc)
    time_difference = current_utc_time - utc_time
    difference_in_seconds = time_difference.total_seconds()
    interval_time = difference_in_seconds // 3600
    return interval_time <= current_query_time

# 获取最新题目
@catch_exceptions()
def get_latest_problem(current_query_time):
    logger.info(f"获取最新题目({current_query_time}小时内)")
    try:
        response = request_get(f"{API_URL['get_homepage']}?locale=zh_CN", headers=REQUEST_HEADERS)
        latest_problems = response.json()["latestUpdatedProblems"]
        p_list = []
        for problem in latest_problems:
            if is_problem_within_time_range(problem, current_query_time):
                logger.info(f"发现新题目: {problem['meta']['displayId']}")
                try:
                    pid = problem["meta"]["displayId"]
                    p_list.append(pid)
                except Exception as e:
                    logger.error(f'处理题目 {pid} 时出错: {e}')
        get_problem_from_list(p_list=p_list)
        logger.info(f"等待下次查询 ({int_time} 小时后) 获取新题目。")
        return int_time
    except requests.RequestException as e:
        logger.error(f"获取最新题目时网络请求出错: {e}")
    except Exception as e:
        logger.error(f"获取最新题目时出错: {e}")
    return current_query_time + int_time

# 从题目编号列表下载题目
@catch_exceptions()
def get_problem_from_list(p_list):
    for pid in p_list:
        try:
            run_in_thread(get_problem, 'https', 'loj.ac', pid)
        except Exception as e:
            logger.error(f'下载题目 {pid} 时出错: {e}')

# 多线程执行函数
def run_in_thread(func, *args, **kwargs):
    thread = threading.Thread(target=func, args=args, kwargs=kwargs)
    thread.start()

if __name__ == '__main__':
    logger.add(os.path.join(DOWNLOAD_PATH, 'log.txt'))
    int_time = 24  # 默认爬取 24 小时内题目
    if len(sys.argv) == 2:
        int_time = int(sys.argv[1])  # 运行参数设置最新题目时间段
    current_query_time = int_time

    def scheduled_task():
        global current_query_time
        current_query_time = get_latest_problem(current_query_time)

    run_in_thread(scheduled_task)
    schedule.every(int_time).hours.do(run_in_thread, scheduled_task)

    while True:
        schedule.run_pending()
        threading.Event().wait(1)