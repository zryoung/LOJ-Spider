import os
from config import DOWNLOAD_PATH
from get_by_schedule import get_pid_list


pid_list = get_pid_list()

with open(os.path.join(DOWNLOAD_PATH,'pid_list.txt'), 'w') as f:
    f.write(pid_list)