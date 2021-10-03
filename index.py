from requests import *
from json import dumps, loads
from os import mkdir, chdir

num = post("https://api.loj.ac/api/problem/queryProblemSet", headers={
    "Content-Type": "application/json"
}, data=dumps({"locale": "zh_CN", "skipCount": 0, "takeCount": 50})).json()["count"]


def getProblemMeta(id):
    return post("https://api.loj.ac/api/problem/getProblem", headers={
        "Content-Type": "application/json",
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/93.0.4577.18 Safari/537.36 Edg/93.0.961.10"
    }, data=dumps({"displayId": id, "testData": True, "additionalFiles": True, "localizedContentsOfLocale": "zh_CN", "tagsOfLocale": "zh_CN", "judgeInfo": True,
                   "samples": True})).json()


totlist = []


def getDataURL(filenamelist, id):
    return post("https://api.loj.ac/api/problem/downloadProblemFiles", headers={"Content-Type": "application/json"},
                data=dumps({
                    "problemId": id,
                    "type": "TestData",
                    "filenameList": filenamelist
                })).json()["downloadInfo"]


def downloadProblem(id):
    # print("Started Downloading LOJ No."+str(id)+" ...",end="");
    dat = getProblemMeta(id)
    try:
        mkdir(str(id));
    except Exception as e:
        pass
    chdir(str(id));
    with open("Description.md", "w+", encoding="utf-8") as f:
        # f.write()
        content = dat["localizedContentsOfLocale"]["contentSections"]
        for i in content:
            f.write("## " + i["sectionTitle"] + "\n")
            if (i["type"] == 'Text'):
                f.write(i["text"] + "\n");
            elif (i["type"] == "Sample"):
                f.write("### Input\n```\n" + dat["samples"][i["sampleId"]]["inputData"] + "```\n");
                f.write("### Output\n```\n" + dat["samples"][i["sampleId"]]["outputData"] + "```\n");

    #get tag name
    with open("problem.yaml", "w+") as f:
        f.write("owner:2\n")
        f.write("title:" + dat["localizedContentsOfLocale"]["title"] + "\n")
        f.write("tags:\n")
        # print(dat)
        content = dat["tagsOfLocale"]
        for i in content:
            f.write(" - " + i["name"] + "\n")

    try:
        mkdir("testData");
    except Exception as e:
        pass
    # chdir("testData")
    #get "config" file
    with open("testData/config.yaml", "w+") as f:
        judgeInfo = dat["judgeInfo"]
        if "timeLimit" in judgeInfo.keys():
            f.write("time:" + str(judgeInfo["timeLimit"]) + "ms\n")
        if "memoryLimit" in judgeInfo.keys():
            f.write("memory:" + str(judgeInfo["memoryLimit"]) + "m\n")
        f.write("filename:null\n")
        if "type" in dat["meta"].keys():
            f.write("type:" + dat["meta"]["type"])


    testData = dat["testData"]
    fnlist = [];
    for i in testData:
        fnlist.append(i["filename"]);
    URList = getDataURL(fnlist, id)
    for i in URList:
        resp = get(i["downloadUrl"])
        try:
            with open("testData/" + i["filename"], "w+") as f:
                f.write(resp.text);
        except Exception as e:
            with open("testData/" + i["filename"], "wb+") as f:
                f.write(resp.content);
    chdir("..")
    print("No." + str(id) + " Done");



nowi = 0;
try:
    for i in range(14, num, 8):
        list = post("https://api.loj.ac/api/problem/queryProblemSet", headers={"Content-Type": "application/json"},
                    data=dumps({"locale": "zh_CN", "skipCount": i, "takeCount": 8})).json()["result"]
        for j in list:
            nowi = j["meta"]["displayId"];
            downloadProblem(j["meta"]["displayId"])

except KeyboardInterrupt as e:
    print("Download Interupted...\n Saving Files... ", end="");
    with open("history.dat", "w+") as f:
        f.write(str(nowi))
    print("Done");
