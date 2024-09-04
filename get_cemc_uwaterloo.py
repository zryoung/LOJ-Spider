

import os

from loguru import logger
from util import request_get, resume_download
from bs4 import BeautifulSoup as bs
from requests import packages
from config import DOWNLOAD_PATH

packages.urllib3.disable_warnings()  # 去除警告信息

if __name__ == '__main__':
    hosts = 'https://cemc.uwaterloo.ca/'
    prefix = hosts + 'resources/past-contests'
    # print(prefix)
    host = 'uwaterloo'
    problem_path = os.path.join(DOWNLOAD_PATH, host)
    os.makedirs(problem_path, exist_ok=True)

    
    for page in range(4):
        url = f'https://cemc.uwaterloo.ca/resources/past-contests?grade=All&academic_year=All&contest_category=29&page={page}'
        result = request_get(
            url,
            # params=params
        )
        html = result.content
        soup = bs(html, "html.parser")
        table = soup.find("tbody")
        rows = table.find_all("tr")
        for row in rows:
            try:
                data = row.find_all("td")
                title = data[0].getText().strip()
                year = data[1].getText().strip()
                contest = data[3].find_all("a", attrs={"download":"download"})[0].get('href')
                solution = data[4].find_all("a", attrs={"download":"download"})[0].get('href')
                new_path = os.path.join(problem_path, title, year)
                os.makedirs(new_path, exist_ok=True)
                # print(new_path + contest.split('/')[-1])
                resume_download(hosts + contest, os.path.join(new_path, contest.split('/')[-1]))
                resume_download(hosts + solution, os.path.join(new_path, solution.split('/')[-1]))
                print(title, year, contest, solution)
            except Exception as e:
                logger.error(e)
        
        try:
            # 下一页
            url = prefix + soup.find("a", attrs={"class":"page-link align-items-center", "rel":"next"}).get('href')
        except Exception as e:
            url = ''
        print(url)