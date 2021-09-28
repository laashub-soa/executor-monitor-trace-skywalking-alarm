import logging
import os

import config

project_root_path = os.getcwd()  # 项目根目录
config.init()
project_temp_path = os.path.join(project_root_path, "temp")
if not os.path.exists(project_temp_path):
    os.mkdir(project_temp_path)
logging.basicConfig()


def init():
    pass
