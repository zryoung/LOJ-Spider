import os
import re
import time
import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
from urllib.parse import urljoin
import zipfile
import shutil

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
    """改进的日期解析函数，支持多种格式"""
    months = ['January', 'February', 'March', 'April', 'May', 'June',
              'July', 'August', 'September', 'October', 'November', 'December']
    
    # 尝试匹配格式："7th March 2020" 或 "March 7th, 2020"
    patterns = [
        r'(?P<day>\d{1,2})(?:th|st|nd|rd)?\s+(?P<month>[A-Za-z]+)\s+(?P<year>\d{4})',
        r'(?P<month>[A-Za-z]+)\s+(?P<day>\d{1,2})(?:th|st|nd|rd)?,\s+(?P<year>\d{4})'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, date_str, re.IGNORECASE)
        if match:
            month_str = match.group('month').capitalize()
            if month_str in months:
                return int(match.group('year')), months.index(month_str) + 1
    return None, None

def pdf_to_markdown(pdf_path, output_dir):
    doc = fitz.open(pdf_path)
    markdown = []
    img_count = 0
    image_dir = os.path.join(output_dir, 'images')
    create_folder(image_dir)

    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        # 提取文本（保留原始布局）
        text = page.get_text("text", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        if text.strip():
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
    """处理题目页面（包括子页面）"""
    print(f"处理Tasks页面：{tasks_url}")
    time.sleep(DELAY)
    try:
        resp = session.get(tasks_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 查找直接PDF链接或子页面链接
        pdf_links = []
        for link in soup.select('a[href$=".pdf"]'):
            href = link['href']
            if any(kw in href.lower() for kw in ['task', 'problem', 'en']):
                pdf_links.append(urljoin(tasks_url, href))
        
        # 如果没有直接PDF链接，查找子页面
        if not pdf_links:
            for subpage_link in soup.select('a[href*="task"]'):
                subpage_url = urljoin(tasks_url, subpage_link['href'])
                sub_resp = session.get(subpage_url)
                sub_soup = BeautifulSoup(sub_resp.text, 'html.parser')
                for pdf_link in sub_soup.select('a[href$=".pdf"]'):
                    pdf_links.append(urljoin(subpage_url, pdf_link['href']))
        
        # 去重下载
        seen = set()
        for pdf_url in pdf_links:
            if pdf_url.lower() in seen:
                continue
            seen.add(pdf_url.lower())
            
            task_name = os.path.splitext(os.path.basename(pdf_url))[0]
            task_dir = os.path.join(folder_name, task_name)
            create_folder(task_dir)
            
            pdf_path = os.path.join(task_dir, 'problem.pdf')
            if not os.path.exists(pdf_path):
                print(f"下载题目：{task_name}")
                download_file(pdf_url, pdf_path)
                time.sleep(DELAY)
            
            # 转换为Markdown
            pdf_to_markdown(pdf_path, task_dir)
    except Exception as e:
        print(f"处理Tasks失败：{str(e)}")

def process_testdata(testdata_url, folder_name, session):
    """处理测试数据（支持.zip和.tar.gz）"""
    print(f"下载测试数据：{testdata_url}")
    try:
        # 获取文件扩展名
        file_ext = os.path.splitext(testdata_url)[1].lower()
        archive_path = os.path.join(folder_name, f'tests{file_ext}')
        
        download_file(testdata_url, archive_path)
        time.sleep(DELAY)
        
        # 创建临时目录
        temp_dir = os.path.join(folder_name, 'temp_tests')
        create_folder(temp_dir)
        
        # 解压文件
        if file_ext == '.zip':
            with zipfile.ZipFile(archive_path, 'r') as zip_ref:
                zip_ref.extractall(temp_dir)
        elif file_ext in ['.gz', '.tar']:
            import tarfile
            with tarfile.open(archive_path, 'r:*') as tar_ref:
                tar_ref.extractall(temp_dir)
        
        # 遍历题目目录
        for task_dir in os.listdir(folder_name):
            task_path = os.path.join(folder_name, task_dir)
            if not os.path.isdir(task_path) or task_dir == 'temp_tests':
                continue
            
            # 创建测试用例目录
            testcases_dir = os.path.join(task_path, 'testcases')
            create_folder(testcases_dir)
            
            # 匹配测试文件
            case_counter = 1
            for root, _, files in os.walk(temp_dir):
                files.sort()  # 确保顺序一致
                for file in files:
                    src_path = os.path.join(root, file)
                    # 匹配测试用例文件
                    if re.match(r'^(.*\.(in|out))$', file):
                        # 去除可能的数字后缀
                        base_name = re.sub(r'[\d_]*\.(in|out)$', '', file)
                        if task_dir.lower() in base_name.lower():
                            # 确定文件类型
                            if file.endswith('.in'):
                                dest = os.path.join(testcases_dir, f"{case_counter}.in")
                                shutil.copy(src_path, dest)
                            elif file.endswith('.out'):
                                dest = os.path.join(testcases_dir, f"{case_counter}.out")
                                shutil.copy(src_path, dest)
                                case_counter += 1
        # 清理
        shutil.rmtree(temp_dir)
        os.remove(archive_path)
    except Exception as e:
        print(f"处理测试数据失败：{str(e)}")

def process_season(season_url, session):
    """处理赛季页面"""
    print(f"处理赛季：{season_url}")
    time.sleep(DELAY)
    try:
        resp = session.get(season_url)
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        # 定位比赛表格（根据实际页面结构调整）
        table = soup.find('table', {'border': '0', 'cellspacing': '2'})
        if not table:
            print("未找到比赛表格")
            return
        
        # 解析表格头确定列索引
        header = table.find('tr')
        columns = [th.text.strip().lower() for th in header.find_all('td')]
        try:
            date_idx = columns.index('contest date')
            tasks_idx = columns.index('tasks')
            testdata_idx = columns.index('test data')
            solutions_idx = columns.index('solutions') if 'solutions' in columns else -1
        except ValueError:
            print("表格列标题不匹配")
            return
        
        # 处理每行比赛
        for row in table.find_all('tr')[1:]:
            cells = row.find_all('td')
            if len(cells) < max(date_idx, tasks_idx, testdata_idx) + 1:
                continue
            
            # 提取基本信息
            contest_name = cells[0].text.strip()
            date_str = cells[date_idx].text.strip()
            tasks_link = cells[tasks_idx].find('a')['href'] if cells[tasks_idx].find('a') else None
            testdata_link = cells[testdata_idx].find('a')['href'] if cells[testdata_idx].find('a') else None
            solutions_link = cells[solutions_idx].find('a')['href'] if solutions_idx != -1 and cells[solutions_idx].find('a') else None
            
            # 解析日期
            year, month = extract_month_year(date_str)
            if not year or not month:
                print(f"无法解析日期：{date_str}")
                continue
            
            # 创建文件夹
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
            
            # 处理Solutions（可选）
            if solutions_link:
                solutions_url = urljoin(season_url, solutions_link)
                solutions_path = os.path.join(folder_name, 'solutions.pdf')
                download_file(solutions_url, solutions_path)
    except Exception as e:
        print(f"处理赛季失败：{str(e)}")

def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    
    # 获取所有赛季链接
    print("获取主页面赛季列表...")
    resp = session.get(BASE_URL)
    soup = BeautifulSoup(resp.text, 'html.parser')
    
    # 查找所有赛季链接（包括archive和当前赛季）
    season_links = []
    for link in soup.select('a[href^="archive/"], a[href^="coci/"]'):
        href = urljoin(BASE_URL, link['href'])
        if href not in season_links:
            season_links.append(href)
    
    # 处理每个赛季
    for season_url in season_links:
        process_season(season_url, session)

if __name__ == "__main__":
    main()