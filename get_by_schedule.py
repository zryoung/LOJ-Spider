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
from loj_download import *
# import logging
from apscheduler.schedulers.blocking import BlockingScheduler
from loguru import logger


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

@logger.catch
@catch_exceptions()
@retry(stop=stop_after_attempt(5),wait=wait_random(1, 3),reraise=True)
def get_pid_list(url):
    num = requests.post("https://api.loj.ac/api/problem/queryProblemSet", 
                stream=True,
                verify=False,
                timeout=(5, 5), 
                headers={"Content-Type": "application/json"}, 
                data=dumps({"locale": "zh_CN", "skipCount": 0, "takeCount": 50})
            ).json()["count"]
    print(f'题目总数：{num}')
    skipCount = 0
    takeCount = 50
    pid_list = []
    # result = \
    #     requests.post("https://api.loj.ac/api/problem/queryProblemSet", headers={"Content-Type": "application/json"},
    #             data=dumps({"locale": "zh_CN", "skipCount": 1247, "takeCount": num})).json()["result"]
    # for item in result:
    #     pid_list.append(item['meta']['displayId'])
    # return pid_list
    try:
        for skipCount in range(1247, num, takeCount):
            logger.info(f'获取题号列表{skipCount}')
            try:
                result = \
                    requests.post("https://api.loj.ac/api/problem/queryProblemSet",
                    stream=True,
                    verify=False,
                    timeout=(5, 5), 
                    headers={"Content-Type": "application/json"},
                    data=dumps({"locale": "zh_CN", "skipCount": skipCount, "takeCount": takeCount})
                ).json()["result"]
            except:
                # time.sleep(5)
                logger.exception('异常')
                result = \
                    requests.post("https://api.loj.ac/api/problem/queryProblemSet",
                    stream=True,
                    verify=False,
                    timeout=(5, 5), 
                    headers={"Content-Type": "application/json"},
                    data=dumps({"locale": "zh_CN", "skipCount": skipCount, "takeCount": takeCount})
                ).json()["result"]
            # print(result)
            # pid_list = [item['meta']['displayId'] for item in result]
            # print(pid_list)
            for item in result:
                pid_list.append(item['meta']['displayId'])
            # print(skipCount)
        return pid_list

    except KeyboardInterrupt as e:
        print("Download Interupted...\n Saving Files... ", end="")
        # with open(directory + "history.dat", "w+") as f:
        #     f.write(str(nowi))
        print("Done")


@catch_exceptions()
def get_problem_from_list():
    pid = pid_list[0]
    # print(pid)
    pid_list.pop(0)
    try:
        message = get_problem('https', 'loj.ac', pid)
        print(message)
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

def run_by_apscheduler():
    print(f'开始：{time.strftime("%H:%M", time.localtime())}')
    scheduler = BlockingScheduler()
    scheduler.add_job(get_problem_from_list, 'cron', hour='0-8',minute='*/10')  # 10-11点，每10分钟执行一次
    scheduler.start()

if __name__ == '__main__':

    # logger = logging.getLogger("apscheduler")
    # logger = logging.getLogger("schedule")
    # logger.setLevel(logging.DEBUG)
    # fh = logging.FileHandler('../downloads/log.txt')
    # fh.setLevel(logging.DEBUG)
    # formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    # fh.setFormatter(formatter)
    # logger.addHandler(fh)

    logger.add('../downloads/log.txt')
    pid_list = get_pid_list('https://api.loj.ac/api/problem/queryProblemSet')
    print(pid_list)
    print(f'开始题号：{pid_list[0]},{time.strftime("%Y-%m-%d %H:%M", time.localtime())}')
    run_by_schedule()
    # run_by_apscheduler()
