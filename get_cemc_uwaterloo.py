

import json
import os

from loguru import logger
from util import request_get, resume_download
from bs4 import BeautifulSoup as bs
from requests import packages
from config import DOWNLOAD_PATH

packages.urllib3.disable_warnings()  # 去除警告信息

def get_contest(hosts, prefix, problem_path, url):
    # for page in range(3):
        # url = f'https://cemc.uwaterloo.ca/resources/past-contests#ccc?grade=All&academic_year=All&contest_category=29&page={page}'
        # url = url + f'&page={page}'  # CCC地址
        # url = f'https://cemc.uwaterloo.ca/views/ajax?academic_year=All&contest_category=80&view_name=listing&view_display_id=past_contest&page={page}'  # CCO地址
        result = request_get(
            url,
            # params=params
        )
        result_text = result.content  # bytes类型结果
        result_text = json.loads(result_text)
        # print(type(result_text))
        for item in result_text:
            if item["command"]=="insert" and item["method"]=="replaceWith" and len(item["data"])>0:
                html = item["data"]
                break

        # print(html)


        soup = bs(html, "html.parser")
        table = soup.find("tbody")
        rows = table.find_all("tr")
        for row in rows:
            try:
                data = row.find_all("td")
                title = data[1].getText().strip()
                year = data[2].getText().strip()
                # testdata = data[5].find_all("a", attrs={"download":"download"})[0].get('href')
                new_path = os.path.join(problem_path, title, year)
                os.makedirs(new_path, exist_ok=True)
                # print(new_path + contest.split('/')[-1])
                contest = data[4].find_all("a", attrs={"class":"btn btn-secondary"})[0].get('href')
                if not contest.startswith("http"):
                    contest_pdf_url = hosts + contest
                else:
                    contest_pdf_url = contest

                testdata = data[5].find_all("a", attrs={"class":"btn btn-secondary"})[0].get('href')
                if not testdata.startswith("http"):
                    test_data_url = hosts + testdata
                else:
                    test_data_url = testdata
                print(title, year, contest, testdata)
                
                resume_download(contest_pdf_url, os.path.join(new_path, contest.split('/')[-1]))
                
                resume_download(test_data_url, os.path.join(new_path, testdata.split('/')[-1]))
                # contest_html = data[4].find_all("a", attrs={"class": "btn btn-outline-secondary"})[0].get('href')
                # resume_download(hosts + contest, os.path.join(new_path, contest_html.split('/')[-1]))
                # solution_html = data[5].find_all("a", attrs={"class": "btn btn-outline-secondary"})[0].get('href')
                # resume_download(hosts + contest, os.path.join(new_path, solution_html.split('/')[-1]))
                
            except Exception as e:
                logger.error(e)
        


if __name__ == '__main__':
    hosts = 'https://cemc.uwaterloo.ca/'
    prefix = hosts + 'resources/past-contests'
    # print(prefix)
    host = 'uwaterloo'
    problem_path = os.path.join(DOWNLOAD_PATH, host)
    os.makedirs(problem_path, exist_ok=True)

    # 调试下载文件
    # resume_download(
    #      "https://s3.amazonaws.com/cemc.drupal/documents/bigfiles/2020CCCSeniorTestData.zip",
    #      os.path.join(problem_path, r"Canadian Computing Competition Senior\2020", "2020CCCSeniorTestData.zip")
    #      )

    # get CCC J/S
    contest_category = 29
    for page in range(3):
        url = f"https://cemc.uwaterloo.ca/views/ajax?academic_year=All&{contest_category=}&view_name=listing&view_display_id=past_contest&{page=}"
        get_contest(hosts, prefix, problem_path, url)

    # get CCO
    contest_category= 80
    url = f"https://cemc.uwaterloo.ca/views/ajax?academic_year=All&{contest_category=}&view_name=listing&view_display_id=past_contest"
    get_contest(hosts, prefix, problem_path, url)