import json
import os
import re
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_random
import sys
sys.path.append(os.getcwd())
from config import DOWNLOAD_PATH
from util import log_while_last_retry, request_get


@retry(stop=stop_after_attempt(5), retry_error_callback=log_while_last_retry,wait=wait_random(1, 3),reraise=True)
def pid_parser(pid: str, path):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Accept': '*/*',
        # 'Host': 'www.luogu.com.cn',
        'Connection': 'keep-alive',
        # 'Cookie': '__client_id=ca02d46480bf42032e4d99e690eec5e887a5228c; _uid=630003'
        # 'Cookie': LUOGU_COOKIE
    }
    problem_url = "http://ssoi.noip.space/problem.php"
    # solution_url = "https://www.luogu.com.cn/problem/solution/"
    try:
        # use requests to open the url with cookie
        problem_rsp = request_get(f"{problem_url}?id={pid}&md=1", headers=headers) 
        print(problem_rsp.text)
        # problem_js = json.loads(problem_rsp.text)["currentData"]["problem"]
        # title = re.sub(r'[\\/:*?"<>|\.]','-',problem_js['title']).strip()  # 替换掉特殊字符
        # n_path = os.path.join(path,problem_js['pid'] + "-" + title)    
            
        # problem_js = json.loads(problem_rsp.text)["currentData"]["problem"]
        # problem_markdown_parser(problem_js, path=n_path)

        # solution_rsp = request_get(solution_url + pid + "?_contentOnly=1", headers=headers)
        
        # soup = bs.BeautifulSoup(solution_rsp.text, "html.parser")
        # script = soup.find(id="lentille-context").string
        
        # js = json.loads(script)
        # solution_markdown_parser(n_path, js)

    except Exception as e:
        logger.error(f"Error: pid={pid} reason:{e}")
        with open(os.path.join(DOWNLOAD_PATH, 'fail.txt'), "a", encoding="utf-8") as f:
            f.write(pid)
            f.write('\n')
        return None
    
if __name__ == "__main__":
    path = os.path.join(DOWNLOAD_PATH, 'SSOJ')
    os.makedirs(path, exist_ok=True)
    pid_parser(2031, path)