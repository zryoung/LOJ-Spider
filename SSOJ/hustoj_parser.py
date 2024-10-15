import json
import os
import random
import re
import time
import uuid
import bs4 as bs
import html2text
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_random
import sys
sys.path.append(os.getcwd())
from config import DOWNLOAD_PATH
from util import base64_to_img, create_writer, get_filename_and_extension, log_while_last_retry, ordered_yaml_dump, request_get, BASE64, resume_download


@retry(stop=stop_after_attempt(5), retry_error_callback=log_while_last_retry,wait=wait_random(1, 3),reraise=True)
def pid_parser(pid: str, path):
    
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36',
        'Accept': '*/*',
        'Connection': 'keep-alive',
    }
    problem_url = "http://ssoi.noip.space/problem.php"
    try:
        # use requests to open the url with cookie
        problem_rsp = request_get(f"{problem_url}?id={pid}", headers=headers) 
        # print(problem_rsp.text)
        soup = bs.BeautifulSoup(problem_rsp.text, "html.parser")

        title = soup.find(class_="ui header").text.strip()
        title = re.sub(r"^\d+: ", "", title)
        title1 = re.sub(r'[\\/:*?"<>|\.]','-',title).strip()  # 替换掉特殊字符
        # print(f"{title=} {title1=}")
        
        memory = re.findall(r"Memory Limit：(\d+) MB", problem_rsp.text)[0]
        time = re.findall(r"Time Limit：(\d+) S", problem_rsp.text)[0]
        config = dict()
        config["time"] = f"{int(time)*1000}ms"
        config["memory"] = f"{memory}m"

        problem_path = os.path.join(path, str(pid)+"-"+title1)
        writer = create_writer(problem_path)
        writer('testdata/config.yaml', ordered_yaml_dump(config))
        
        writer('problem.yaml', ordered_yaml_dump({
            "title": title,
            "owner": 1,
        },
        allow_unicode=True,
        ))
        
        div = soup.find_all(class_="ui bottom attached segment font-content")[0]
        images = div.find_all('img')
        if images != []:
            pic_path = os.path.join(problem_path, "additional_file")
            os.makedirs(pic_path, exist_ok=True)

        for img in images:
            src = img['src']
            mat = re.findall(BASE64, src, flags=0)
            if (mat != None) and (mat != []):
                base64str = mat[0][1]
                sufix = mat[0][0]
                pic_name = uuid.uuid1().hex + '.' + sufix                
                
                base64_to_img(base64str, os.path.join(pic_path,pic_name))
                img.replace_with(f"\n\n![](file://{pic_name}?type=additional_file)\n\n")
            elif src.startswith("http"):
                pic_name, sufix = get_filename_and_extension(src)
                resume_download(src, os.path.join(pic_path, pic_name + "." + sufix))
                img.replace_with(f"\n\n![](file://{pic_name + "." + sufix}?type=additional_file)\n\n")
            elif src.startswith("/"):
                pic_name, sufix = get_filename_and_extension("http://ssoi.noip.space" + src)
                resume_download("http://ssoi.noip.space" + src, os.path.join(pic_path, pic_name + "." + sufix))
                img.replace_with(f"\n\n![](file://{pic_name + "." + sufix}?type=additional_file)\n\n")
            else:
                pic_name, sufix = get_filename_and_extension("http://ssoi.noip.space/" + src)
                resume_download("http://ssoi.noip.space/" + src, os.path.join(pic_path, pic_name + "." + sufix))
                img.replace_with(f"\n\n![](file://{pic_name + "." + sufix}?type=additional_file)\n\n")

        text = div.text
        text = text.replace("【", "\n## ")
        text = text.replace("】", "\n")
        # print(text)
        writer("problem.md", content=text)

    except Exception as e:
        logger.error(f"Error: pid={pid} reason:{e}")
        with open(os.path.join(DOWNLOAD_PATH, 'fail.txt'), "a", encoding="utf-8") as f:
            f.write(str(pid))
            f.write('\n')
        return None
    
if __name__ == "__main__":
    path = os.path.join(DOWNLOAD_PATH, 'SSOJ')
    os.makedirs(path, exist_ok=True)
    for id in range(2081, 2082):  #2028, 2229
        pid_parser(id, path) #2031,2061
        time.sleep(random.randint(0,2))