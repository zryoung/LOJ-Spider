import os

from requests import *
from json import dumps, loads
from os import mkdir, chdir
from queue import Queue
import threading
import time
import schedule


def getProblemMeta(id):
    return post("https://api.loj.ac/api/problem/getProblem", headers={
        "Content-Type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
    }, data=dumps({"displayId": id, "testData": True, "additionalFiles": True, "localizedContentsOfLocale": "zh_CN",
                   "tagsOfLocale": "zh_CN", "judgeInfo": True,
                   "samples": True})).json()


totlist = []
failList = []


def getDataURL(filenamelist, id):
    return post("https://api.loj.ac/api/problem/downloadProblemFiles", headers={"Content-Type": "application/json"},
                data=dumps({
                    "problemId": id,
                    "type": "TestData",
                    "filenameList": filenamelist
                })).json()["downloadInfo"]


def downloadProblem(displayId, id):
    print("Started Downloading LOJ No."+str(displayId)+" ..."+time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
    dat = getProblemMeta(displayId)
    try:
        mkdir(str(displayId))
    except Exception as e:
        pass
    # chdir(str(displayId));
    if not os.path.exists(str(displayId) + "/Description.md"):
        with open(str(displayId) + "/Description.md", "w+", encoding="utf-8") as f:
            # f.write()
            content = dat["localizedContentsOfLocale"]["contentSections"]
            for i in content:
                f.write("## " + i["sectionTitle"] + "\n")
                if i["type"] == 'Text':
                    f.write(i["text"] + "\n")
                elif i["type"] == "Sample":
                    f.write("### Input\n```\n" + dat["samples"][i["sampleId"]]["inputData"] + "```\n")
                    f.write("### Output\n```\n" + dat["samples"][i["sampleId"]]["outputData"] + "```\n")

    # get tag name
    if not os.path.exists(str(displayId) + "/problem.yaml"):
        with open(str(displayId) + "/problem.yaml", "w+", encoding='utf-8') as f:
            f.write("owner:2\n")
            f.write("title:" + dat["localizedContentsOfLocale"]["title"] + "\n")
            f.write("tags:\n")
            # print(dat)
            content = dat["tagsOfLocale"]
            for i in content:
                f.write(" - " + i["name"] + "\n")

    try:
        mkdir(str(displayId) + "/testdata")
    except Exception as e:
        pass
    # chdir("testData")
    # get "config" file
    if not os.path.exists(str(displayId) + "/testdata/config.yaml"):
        with open(str(displayId) + "/testdata/config.yaml", "w+") as f:
            judgeInfo = dat["judgeInfo"]
            if "timeLimit" in judgeInfo.keys():
                f.write("time:" + str(judgeInfo["timeLimit"]) + "ms\n")
            if "memoryLimit" in judgeInfo.keys():
                f.write("memory:" + str(judgeInfo["memoryLimit"]) + "m\n")
            f.write("filename:null\n")
            if "type" in dat["meta"].keys():
                f.write("type:" + dat["meta"]["type"])

    testdata = dat["testdata"]
    fnlist = []
    for i in testdata:
        fnlist.append(i["filename"])
    URList = getDataURL(fnlist, id)
    for i in URList:
        if not os.path.exists(str(displayId) + "/testdata/" + i["filename"]):
            resp = get(i["downloadUrl"])
            try:
                with open(str(displayId) + "/testdata/" + i["filename"], "w+") as f:
                    f.write(resp.text)
            except Exception as e:
                with open(str(displayId) + "/testdata/" + i["filename"], "wb+") as f:
                    f.write(resp.content)
    # chdir("..")
    print("No." + str(displayId) + " Done..." + time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))


class worker(threading.Thread):
    def __init__(self, q):
        threading.Thread.__init__(self)
        self.queue = q

    def run(self):
        while True:
            if self.queue.empty():
                break
            displayid, id = queue.get()

            try:
                # print("thread %s is running..." %threading.current_thread().name)
                # print("%d downloading"%displayId)
                downloadProblem(displayid,id)
            except Exception as e:
                print(e)
                with open("fail.txt", "a+") as f:
                    f.write(str(displayid) + "failed." + str(e) + "\n")
            self.queue.task_done()


def getNewProblem():
    list = get("https://api.loj.ac.cn/api/homepage/getHomepage?locale=zh_CN", headers={
        "Content-Type": "application/json"
    }).json()["latestUpdatedProblems"]
    # print(list)
    for li in list:
        # print(str(li["meta"]["displayId"]), li["title"], li["meta"]["publicTime"])
        # print(time.strftime('%Y-%m-%d %H:%M:%S', li["meta"]["publicTime"]) - time.localtime(time.time()))
        interval_time = (time.time() - time.mktime(
            time.strptime(li["meta"]["publicTime"], "%Y-%m-%dT%H:%M:%S.000Z"))) / 60 / 60  # 获取1天内更新的题目
        if interval_time < 24:
            print("get new problem.", li["meta"]["displayId"])
            downloadProblem(li["meta"]["displayId"], li["meta"]["id"])
    #         queue.put(li["meta"]["displayId"])
    #     if threading.activeCount() < 10:
    #         t = worker(queue)
    #         t.start()
    #
    # queue.join()
    print("Updated!", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))


nowi = 0
queue = Queue(maxsize=10)
# num=25
choice = input("请输入1或2选择下载最新题目或下载全部题目：\n"
               "1.下载最新题目（持续监控题目更新）\n"
               "2.下载全部题目（耗时很长）")
print("Begin!", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
if choice == '1':
    schedule.every().day.at("10:30").do(getNewProblem)  # 每天的10:30执行一次任务
    while True:
        schedule.run_pending()
        time.sleep(60)
    # getNewProblem()
else:
    num = post("https://api.loj.ac/api/problem/queryProblemSet", headers={
        "Content-Type": "application/json"
    }, data=dumps({"locale": "zh_CN", "skipCount": 0, "takeCount": 50})).json()["count"]

    try:
        for i in range(0, num, 8):
            list = post("https://api.loj.ac/api/problem/queryProblemSet", headers={"Content-Type": "application/json"},
                        data=dumps({"locale": "zh_CN", "skipCount": i, "takeCount": 8})).json()["result"]
            for j in list:
                nowi = j["meta"]["displayId"]
                id = j["meta"]["id"]
                # downloadProblem(j["meta"]["displayId"])
                queue.put((nowi, id))

                if threading.activeCount() < 10:
                    t = worker(queue)
                    t.start()

    except KeyboardInterrupt as e:
        print("Download Interupted...\n Saving Files... ", end="")
        with open("history.dat", "w+") as f:
            f.write(str(nowi))
        print("Done")

    queue.join()
    # with open("fail.txt", "w+") as f:
    #     f.write(failList)

    print("All Done!", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(time.time())))
