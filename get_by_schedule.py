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


def get_latest_problem(int_time=24):
    logger.info(f"获取最新题目({int_time}小时内)")
    list = request_get("https://api.loj.ac/api/homepage/getHomepage?locale=zh_CN", headers={
        "Content-Type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
    }).json()["latestUpdatedProblems"]
    # print(list)

    for item in list:
        interval_time = (time.time() - time.mktime(
            time.strptime(item["meta"]["publicTime"], "%Y-%m-%dT%H:%M:%S.000Z"))) / 60 / 60  # 获取1天内更新的题目
        if interval_time <= int_time:  # 1小时内更新的题目
            print("get new problem.", item["meta"]["displayId"])
            try:
                pid = item["meta"]["displayId"]
                message = get_problem('https', 'loj.ac', pid)
                logger.info(message)
            except Exception as e:
                logger.error(f'{pid},message:{e}')


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
    
    # with open(os.path.join(DOWNLOAD_PATH, 'pid_list.json'), 'r') as f:
    #     pid_list = json.load(f)
    # # print(pid_list)
    # logger.info(f'开始题号：{pid_list[0]}')
    # run_by_schedule()

    int_time = 24 #默认爬取24小时内题目
    if len(sys.argv)==2:
        int_time = int(sys.argv[1]) #运行参数设置最新题目时间段
    # print(int_time)
    get_latest_problem(int_time)
    schedule.every(int_time).hours.do(get_latest_problem, int_time=int_time)
    while True:
        schedule.run_pending()
        time.sleep(1)
    # get_latest_problem()
