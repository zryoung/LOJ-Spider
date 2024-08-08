import os
import random
import re
import uuid
from io import BytesIO
from PIL import Image

from requests import *
from json import dumps, loads
from os import mkdir, chdir
from queue import Queue
import threading
import time
import schedule
from requests import packages
from requests.adapters import HTTPAdapter

directory = 'E:/LOJ/download/'
delay_time = 1
headers={
    "Content-Type": "application/json",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
}

ScoreTypeMap = {
    'GroupMin': 'min',
    'Sum': 'sum',
    'GroupMul': 'max',
}

LanguageMap = {
    'cpp': 'cc',
}

def getProblemMeta(id):
    return post("https://api.loj.ac/api/problem/getProblem",
                stream=True,
                verify=False,
                timeout=(5, 5),
                headers={
                    "Content-Type": "application/json",
                    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
                }, data=dumps(
            {"displayId": id, "testData": True, "additionalFiles": True, "localizedContentsOfLocale": "zh_CN",
             "tagsOfLocale": "zh_CN", "judgeInfo": True,
             "samples": True})).json()


totlist = []
failList = []


def getDataURL(filenamelist, id, type):
    rsp = post("https://api.loj.ac/api/problem/downloadProblemFiles",
               headers={"Content-Type": "application/json",
                        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
                        },
               data=dumps({
                   "problemId": id,
                   "type": type,
                   "filenameList": filenamelist
               })).json()
    return rsp["downloadInfo"]


def get_response(url):
    rand_time = random.random() * delay_time
    time.sleep(rand_time)
    try:
        response = get(url=url, headers=headers)
        return response
    except Exception as e:
        print(f'网络读取出错：url-{url};info-{e.args}')
    return None


def get_and_replace_images(content, picpath):
    img_arr = re.findall(r'!\[.*?\]\((.*?)\)', content)

    if img_arr:
        os.makedirs(picpath, exist_ok=True)
    # print(img_arr)
    for img_url in img_arr:
        # print(img_url)
        response = get_response(img_url)
        # print(response.content)
        if response != None and response.status_code == 200:
            # TODO: 无法识别svg图片
            img = Image.open(BytesIO(response.content))
            pic_name = uuid.uuid1().hex + '.' + img.format.lower()
            pic_file_path = os.path.join(picpath, pic_name)

            with open(pic_file_path, 'wb+') as f:
                f.write(response.content)

            content = content.replace(img_url, f'file://{pic_name}?type=additional_file')
    return content


def downloadProblem(displayId):
    print("Started Downloading LOJ No." + str(displayId) + " ..." + time.strftime("%Y-%m-%d %H:%M:%S",
                                                                                  time.localtime(time.time())))
    # dat = getProblemMeta(displayId)

    packages.urllib3.disable_warnings()
    sess = Session()
    sess.mount('http://', HTTPAdapter(max_retries=3))
    sess.mount('https://', HTTPAdapter(max_retries=3))
    sess.keep_alive = False  # 关闭多余连接
    dat = post("https://api.loj.ac/api/problem/getProblem",
               stream=True,
               verify=False,
               timeout=(5, 5),
               headers={
                   "Content-Type": "application/json",
                   "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
               },
               data=dumps({"displayId": displayId, "testData": True, "additionalFiles": True,
                           "localizedContentsOfLocale": "zh_CN",
                           "tagsOfLocale": "zh_CN", "judgeInfo": True,
                           "samples": True})).json()
    # print(dat)

    try:
        mkdir(directory + str(displayId))
    except Exception as e:
        pass
    # chdir(str(displayId));
    if not os.path.exists(directory + str(displayId) + "/problem.md"):
        with open(directory + str(displayId) + "/problem.md", "w+", encoding="utf-8") as f:
            # f.write()
            content = dat["localizedContentsOfLocale"]["contentSections"]
            sample_id = 0

            for i in content:
                f.write("## " + i["sectionTitle"] + "\n")
                if i["type"] == 'Text':
                    # print(i["text"])
                    text = get_and_replace_images(i["text"],directory + str(displayId) + "/additional_file")
                    f.write(text + "\n")
                elif i["type"] == "Sample":
                    sample_id = sample_id + 1
                    f.write("```input" + str(sample_id) + "\n" + dat["samples"][i["sampleId"]]["inputData"] + "\n```\n")
                    f.write(
                        "```output" + str(sample_id) + "\n" + dat["samples"][i["sampleId"]]["outputData"] + "\n```\n")
                    text = get_and_replace_images(i["text"], directory + str(displayId) + "/additional_file")
                    f.write(text + "\n")
                    # f.write("### Input\n```\n" + dat["samples"][i["sampleId"]]["inputData"] + "\n```\n")
                    # f.write("### Output\n```\n" + dat["samples"][i["sampleId"]]["outputData"] + "\n```\n")
            f.write("### 来源\n")
            f.write("[LOJ" + str(displayId) + "](" + "https://loj.ac/p/" + str(displayId) + ")\n")

    # get tag name
    if not os.path.exists(directory + str(displayId) + "/problem.yaml"):
        with open(directory + str(displayId) + "/problem.yaml", "w+", encoding='utf-8') as f:
            f.write("owner: 2\n")
            f.write("title: " + dat["localizedContentsOfLocale"]["title"] + "\n")
            f.write("tag:\n")
            # print(dat)
            content = dat["tagsOfLocale"]
            for i in content:
                f.write("  - " + i["name"] + "\n")

    try:
        mkdir(directory + str(displayId) + "/testdata")
    except Exception as e:
        pass
    # chdir("testData")
    # get "config" file
    if not os.path.exists(directory + str(displayId) + "/testdata/config.yaml"):
        with open(directory + str(displayId) + "/testdata/config.yaml", "w+") as f:
            judgeInfo = dat["judgeInfo"]
            if "timeLimit" in judgeInfo.keys():
                f.write("time: " + str(judgeInfo["timeLimit"]) + "ms\n")
            if "memoryLimit" in judgeInfo.keys():
                f.write("memory: " + str(judgeInfo["memoryLimit"]) + "m\n")
            f.write("filename: null\n")
            if "type" in dat["meta"].keys():
                f.write("type: ")
                if dat["meta"]["type"] == "Traditional":
                    f.write("default\n")
                elif dat["meta"]["type"] == "Interaction":
                    f.write("interactive\n")
                    f.write("interactor: ")
                    f.write(judgeInfo["interactor"]["filename"] + "\n")
                    # TODO: other thing: compiler?,loj:3286
                elif dat["meta"]["type"] == "SubmitAnswer":
                    f.write("submit_answer\n")
            if "subtasks" in judgeInfo.keys():
                f.write("subtasks:\n")
                for sub_task in judgeInfo["subtasks"]:
                    if "points" in sub_task:
                        f.write("  - score: ")
                        f.write(str(sub_task["points"]) + "\n")
                    f.write("    type: ")
                    if sub_task["scoringType"] == "GroupMin":
                        f.write("min\n")
                    elif sub_task["scoringType"] == "Sum":
                        f.write("sum\n")
                    else:
                        print(str(displayId) + sub_task["scoringType"])
                    f.write("    cases: \n")
                    for test_case in sub_task["testcases"]:
                        if "inputFile" in test_case:
                            f.write("      - input: ")
                            f.write(test_case["inputFile"] + "\n")
                        if "outputFile" in test_case:
                            f.write("        output: ")
                            f.write(test_case["outputFile"] + "\n")
                    if "dependencies" in sub_task:
                        f.write("    if: \n")
                        for dependency in sub_task["dependencies"]:
                            f.write("      - " + str(dependency) + "\n")

    testdata = dat["testData"]
    id = dat["meta"]["id"]
    fnlist = []
    for i in testdata:
        fnlist.append(i["filename"])
    URList = getDataURL(fnlist, id, 'TestData')
    # print(URList)
    for i in URList:
        if not os.path.exists(directory + str(displayId) + "/testdata/" + i["filename"]):
            resp = get(i["downloadUrl"])
            try:
                with open(directory + str(displayId) + "/testdata/" + i["filename"], "w+") as f:
                    f.write(resp.text)
            except Exception as e:
                with open(directory + str(displayId) + "/testdata/" + i["filename"], "wb+") as f:
                    f.write(resp.content)
            resp.close()  # 关闭连接
    # chdir("..")

    additional_data = dat["additionalFiles"]
    if additional_data:
        try:
            mkdir(directory + str(displayId) + "/additional_file")
        except Exception as e:
            pass
        fnlist = []
        for i in additional_data:
            fnlist.append(i["filename"])
        # print(fnlist)
        URList = getDataURL(fnlist, id, 'AdditionalFile')
        # print(URList)
        for i in URList:
            if not os.path.exists(directory + str(displayId) + "/additional_file/" + i["filename"]):
                resp = get(i["downloadUrl"])
                try:
                    with open(directory + str(displayId) + "/additional_file/" + i["filename"], "w+") as f:
                        f.write(resp.text)
                except Exception as e:
                    with open(directory + str(displayId) + "/additional_file/" + i["filename"], "wb+") as f:
                        f.write(resp.content)
                resp.close()  # 关闭连接

    print("No." + str(displayId) + " Done..." + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))


class worker(threading.Thread):
    def __init__(self, q):
        threading.Thread.__init__(self)
        self.queue = q

    def run(self):
        while True:
            if self.queue.empty():
                break
            displayid = queue.get()
            print(f'避免反爬，等待{delay_time}秒。')
            time.sleep(delay_time)

            try:
                # print("thread %s is running..." %threading.current_thread().name)
                # print("%d downloading"%displayId)
                downloadProblem(displayid)
            except Exception as e:
                print(e)
                with open(directory + "fail.txt", "a+") as f:
                    f.write(str(displayid) + "failed." + str(e) + "\n")
            self.queue.task_done()



def getNewProblem():
    list = get("https://api.loj.ac.cn/api/homepage/getHomepage?locale=zh_CN", headers={
        "Content-Type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
    }).json()["latestUpdatedProblems"]
    # print(list)
    for li in list:
        # print(str(li["meta"]["displayId"]), li["title"], li["meta"]["publicTime"])
        # print(time.strftime('%Y-%m-%d %H:%M:%S', li["meta"]["publicTime"]) - time.localtime(time.time()))
        # interval_time = (time.time() - time.mktime(
        #     time.strptime(li["meta"]["publicTime"], "%Y-%m-%dT%H:%M:%S.000Z"))) / 60 / 60  # 获取1天内更新的题目
        # if interval_time < 2:  # 1小时内更新的题目
        #     print("get new problem.", li["meta"]["displayId"])
        #     # downloadProblem(li["meta"]["displayId"], li["meta"]["id"])
        #     queue.put((li["meta"]["displayId"], li["meta"]["id"]))
        if not os.path.exists(directory + str(li["meta"]["displayId"])):
            print("get new problem.", li["meta"]["displayId"])
            queue.put(li["meta"]["displayId"])
        else:
            print("{}已经存在。".format(li["meta"]["displayId"]))
        if threading.active_count() < 10:
            t = worker(queue)
            t.start()

    queue.join()
    print("Updated!", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))


nowi = 0
queue = Queue(maxsize=10)
# num=25
choice = input('''请输入1或2选择下载最新题目或下载全部题目：
               1.下载最新题目（持续监控题目更新）
               2.指定题号信息下载。
               3.下载全部题目（耗时很长）
               ''')
print("Begin!", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
if choice == '1':
    # nowTime = time.strftime("%H:%M", time.localtime())
    nowTime = time.strftime("%H:%M", time.localtime())
    print(nowTime)
    schedule.every().day.at(nowTime).do(getNewProblem)  # 每天的4:30执行一次任务
    # schedule.every(10).minutes.do(job)
    # schedule.every().hour.do(getNewProblem)  # 每小时执行一次
    # schedule.every().day.at("10:30").do(job)
    # schedule.every().monday.do(job)
    # schedule.every().wednesday.at("13:15").do(job)
    schedule.run_all()
    while True:
        schedule.run_pending()
        time.sleep(60)
    # getNewProblem()
elif choice == '2':
    b_id = int(input('请输入开始题号：'))
    e_id = int(input('请输入结束题号：'))
    for p_id in range(b_id, e_id + 1):
        queue.put(p_id)
        if threading.active_count() < 10:
            t = worker(queue)
            t.start()
else:
    num = post("https://api.loj.ac/api/problem/queryProblemSet", headers={
        "Content-Type": "application/json"
    }, data=dumps({"locale": "zh_CN", "skipCount": 0, "takeCount": 50})).json()["count"]

    try:
        for i in range(0, num, 8):
            try:
                list = \
                    post("https://api.loj.ac/api/problem/queryProblemSet", headers={"Content-Type": "application/json"},
                         data=dumps({"locale": "zh_CN", "skipCount": i, "takeCount": 8})).json()["result"]
            except:
                time.sleep(5)
                list = \
                    post("https://api.loj.ac/api/problem/queryProblemSet", headers={"Content-Type": "application/json"},
                         data=dumps({"locale": "zh_CN", "skipCount": i, "takeCount": 8})).json()["result"]
            for j in list:
                nowi = j["meta"]["displayId"]
                # id = j["meta"]["id"]
                # downloadProblem(j["meta"]["displayId"])
                queue.put(nowi)

                if threading.active_count() < 10:
                    t = worker(queue)
                    t.start()

    except KeyboardInterrupt as e:
        print("Download Interupted...\n Saving Files... ", end="")
        with open(directory + "history.dat", "w+") as f:
            f.write(str(nowi))
        print("Done")

    queue.join()
    # with open("fail.txt", "w+") as f:
    #     f.write(failList)

print("All Done!", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
