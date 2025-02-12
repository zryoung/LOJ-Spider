import os
import re
import time
import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
from urllib.parse import urljoin
import zipfile
import shutil

# 忽略SSL证书验证警告
requests.packages.urllib3.disable_warnings()

# 配置
BASE_URL = 'https://hsin.hr/coci/'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.93 Safari/537.36'
}
DELAY = 1  # 请求间隔防止反爬

def create_folder(path):
    os.makedirs(path, exist_ok=True)

def download_file(url, save_path):
    response = requests.get(url, headers=HEADERS, stream=True)
    with open(save_path, 'wb') as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

def extract_month_year(date_str):
    """从日期字符串提取年份和月份"""
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    # 匹配格式如："7th March 2020" 或 "March 7th, 2020"
    match = re.search(r'''
        (\d{1,2}(?:th|st|nd|rd)?\s+  # 日期部分
        (January|February|March|April|May|June|July|
        August|September|October|November|December)\s+  # 月份
        (\d{4})  # 年份
        |
        (January|February|March|April|May|June|July|
        August|September|October|November|December)\s+  # 月份
        \d{1,2}(?:th|st|nd|rd)?,\s+  # 日期部分
        (\d{4})  # 年份
    ''', date_str, re.VERBOSE | re.IGNORECASE)
    
    if match:
        if match.group(2):  # 第一种格式
            month_str = match.group(2)
            year = int(match.group(3))
        else:  # 第二种格式
            month_str = match.group(4)
            year = int(match.group(5))
        return year, months.index(month_str) + 1
    return None, None

def pdf_to_markdown(pdf_path, output_dir):
    """转换PDF到Markdown并提取图片"""
    doc = fitz.open(pdf_path)
    markdown = []
    img_count = 0
    image_dir = os.path.join(output_dir, 'images')
    create_folder(image_dir)

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # 提取文本
        text = page.get_text("text").strip()
        if text:
            markdown.append(text)
        # 提取图片
        img_list = page.get_images(full=True)
        for img in img_list:
            xref = img[0]
            base_img = doc.extract_image(xref)
            img_data = base_img["image"]
            img_ext = base_img["ext"]
            img_name = f"image_{img_count}.{img_ext}"
            img_path = os.path.join(image_dir, img_name)
            with open(img_path, 'wb') as f:
                f.write(img_data)
            markdown.append(f"![{img_name}](./images/{img_name})")
            img_count += 1

    md_path = os.path.join(output_dir, 'problem.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write('\n\n'.join(markdown))

def process_tasks(tasks_url, folder_name, session):
    """处理题目页面并下载所有PDF"""
    print(f"处理Tasks页面：{tasks_url}")
    time.sleep(DELAY)
    try:
        resp = session.get(tasks_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 查找所有PDF链接
        task_links = []
        for link in soup.select('a[href$=".pdf"]'):
            href = link['href']
            if any(kw in href.lower() for kw in ['task', 'problem', 'en']):
                task_links.append(urljoin(tasks_url, href))
        
        # 下载每个题目PDF
        for task_url in task_links:
            task_name = os.path.splitext(os.path.basename(task_url))[0]
            task_dir = os.path.join(folder_name, task_name)
            create_folder(task_dir)
            
            pdf_path = os.path.join(task_dir, 'problem.pdf')
            if not os.path.exists(pdf_path):
                print(f"下载题目：{task_name}")
                download_file(task_url, pdf_path)
                time.sleep(DELAY)
            
            # 转换为Markdown
            pdf_to_markdown(pdf_path, task_dir)
    except Exception as e:
        print(f"处理Tasks页面失败：{str(e)}")

def process_testdata(testdata_url, folder_name, session):
    """处理测试数据"""
    print(f"下载测试数据：{testdata_url}")
    try:
        zip_path = os.path.join(folder_name, 'tests.zip')
        download_file(testdata_url, zip_path)
        time.sleep(DELAY)
        
        # 解压到临时目录
        temp_dir = os.path.join(folder_name, 'temp_tests')
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(temp_dir)
        
        # 遍历所有题目目录
        for task_dir in os.listdir(folder_name):
            task_path = os.path.join(folder_name, task_dir)
            if os.path.isdir(task_path) and task_dir != 'temp_tests':
                # 在测试数据中查找匹配的题目
                testcases_dir = os.path.join(task_path, 'testcases')
                create_folder(testcases_dir)
                
                # 搜索所有测试文件
                case_num = 1
                for root, _, files in os.walk(temp_dir):
                    for file in files:
                        if task_dir.lower() in file.lower():
                            src = os.path.join(root, file)
                            # 确定文件类型
                            if file.endswith('.in'):
                                dest = os.path.join(testcases_dir, f"{case_num}.in")
                                shutil.copy(src, dest)
                            elif file.endswith('.out'):
                                dest = os.path.join(testcases_dir, f"{case_num}.out")
                                shutil.copy(src, dest)
                                case_num += 1
        # 清理
        shutil.rmtree(temp_dir)
        os.remove(zip_path)
    except Exception as e:
        print(f"处理测试数据失败：{str(e)}")

def process_season(season_url, session):
    """处理单个赛季页面"""
    print(f"处理赛季：{season_url}")
    time.sleep(DELAY)
    try:
        resp = session.get(season_url, headers=HEADERS, verify=False)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 查找比赛表格
        contest_list = soup.find_all('td', {'class': 'desni_rub'})  # 可能需要调整class选择器
        if not contest_list:
            print("未找到比赛表格")
            return
        
        # 遍历表格行（跳过表头）
        for contest in contest_list:
            # cols = row.find_all('td')
            # if len(cols) < 5:
            #     continue
            
            # 解析比赛信息
            # contest_name = cols[0].text.strip()
            # date_str = cols[1].text.strip()
            # tasks_link = cols[2].find('a')['href'] if cols[2].find('a') else None
            # testdata_link = cols[3].find('a')['href'] if cols[3].find('a') else None

            contest_item = contest.find_all('a')
            date_str = contest_item[0].text.strip()
            tasks_link = contest_item[1]['href'] if len(contest_item) > 1 else None
            testdata_link = contest_item[2]['href'] if len(contest_item) > 2 else None
            solution_link = contest_item[3]['href'] if len(contest_item) > 3 else None
            
            # 提取日期
            year, month = extract_month_year(date_str)
            if not year or not month:
                print(f"无法解析日期：{date_str}")
                continue
            
            # 创建赛季文件夹
            folder_name = f"COCI{year}_{month:02d}"
            create_folder(folder_name)
            
            # 处理Tasks
            if tasks_link:
                tasks_url = urljoin(season_url, tasks_link)
                process_tasks(tasks_url, folder_name, session)
            
            # 处理Test data
            if testdata_link:
                testdata_url = urljoin(season_url, testdata_link)
                process_testdata(testdata_url, folder_name, session)
    except Exception as e:
        print(f"处理赛季失败：{str(e)}")

def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # 获取所有赛季链接
    print("获取主页面赛季列表...")
    resp = session.get(BASE_URL, headers=HEADERS, verify=False)
    soup = BeautifulSoup(resp.text, 'html.parser')
    season_links = []
    
    # 查找所有赛季链接（包括当前赛季）
    for link in soup.select('a[href^="archive/"], a[href^="coci/"]'):
        href = urljoin(BASE_URL, link['href'])
        if href not in season_links:
            season_links.append(href)
    
    # 处理每个赛季
    for season_url in season_links:
        process_season(season_url, session)

if __name__ == "__main__":
    main()