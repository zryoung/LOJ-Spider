import functools
import json
import random
import schedule
import os, re, requests, sys, yaml
import time
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


pid_list = []

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
    try:
        num = query_problem_set(skipCount, takeCount)["count"]
        print(f'题目总数：{num}')
        pid_list = []
        # result = query_problem_set(skipCount, num)["result"]
        # for item in result:
        #     pid_list.append(item['meta']['displayId'])
        # return pid_list
        for skipCount in range(2967, num, takeCount):
            logger.info(f'获取题号列表{skipCount}')
            result = query_problem_set(skipCount, takeCount)["result"]
            # try:
            #     result = query_problem_set(skipCount, takeCount)["result"]
            # except:
            #     # time.sleep(5)
            #     logger.exception('异常')
            #     result = query_problem_set(skipCount, takeCount)["result"]
            # print(result)
            # pid_list = [item['meta']['displayId'] for item in result]
            # print(pid_list)
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


@catch_exceptions()
def get_problem_from_list():
    pid = pid_list[0]
    # print(pid)
    pid_list.pop(0)
    try:
        message = get_problem('https', 'loj.ac', pid)
        logger.info(message)
    except Exception as e:
        logger.error(f'{pid},message:{e}')


def run_by_schedule():
    # nowTime = time.strftime("%H:%M", time.localtime())
    # print(nowTime)
    
    # schedule.every().day.at(nowTime).do(getNewProblem)  # 每天的4:30执行一次任务
    schedule.every(10).minutes.do(get_problem_from_list)  # 每10分钟
    # schedule.every().hour.do(getNewProblem)  # 每小时执行一次
    # schedule.every().day.at("10:30").do(job)
    # schedule.every().monday.do(job)
    # schedule.every().wednesday.at("13:15").do(job)
    # schedule.run_all()
    while len(pid_list):
        schedule.run_pending()
        time.sleep(1)

if __name__ == '__main__':
    logger.add(os.path.join(DOWNLOAD_PATH, 'log.txt'))
    
    with open(os.path.join(DOWNLOAD_PATH, 'pid_list.json'), 'r') as f:
        pid_list = json.load(f)
    # print(pid_list)
    logger.info(f'开始题号：{pid_list[0]}')
    run_by_schedule()
