
import os
import shutil

WORKDIR = ""

def move(pid_dir, target_dir):
    
    data_dir = os.path.join(pid_dir, 'in')
    filenames = os.listdir(data_dir)
    for fi in filenames:
        fi_name, _ = os.path.splitext(fi)
        shutil.move(os.path.join(data_dir, fi), os.path.join(target_dir, fi_name + '.in'))

    data_dir = os.path.join(pid_dir, 'out')
    filenames = os.listdir(data_dir)
    for fi in filenames:
        fi_name, _ = os.path.splitext(fi)
        shutil.move(os.path.join(data_dir, fi), os.path.join(target_dir, fi_name + '.out'))


if __name__ == '__main__':
    os.makedirs(r'..\downloads\AtCoder\abc377\A\testdata', exist_ok=True)
    move(r'..\downloads\AtCoder\abc377\A', r'..\downloads\AtCoder\abc377\A\testdata')