import logging
import os

from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger

from __init__ import init
from __init__ import project_temp_path
from config import app_conf
from service.skywalking_alarm import SkywalkingAlarm

sched = BlockingScheduler()

init()
logger = logging.getLogger('setup')
logger.setLevel(logging.DEBUG)


def common_job(task_key, task_value):
    logger.debug("task(%s) is start" % task_key)
    task_persistent_path = os.path.join(project_temp_path, task_key)
    if not os.path.exists(task_persistent_path):
        os.mkdir(task_persistent_path)
    task_data = task_value
    task_data["common"] = {
        "dingding_webhook_access_token": app_conf["dingding_webhook_access_token"],
        "user_info": app_conf["user_info"],
        "user_follow_service": app_conf["user_follow_service"],
        "query_compensate_timezone": app_conf["query"]["compensate_timezone"],
        "query_base_url": app_conf["query"]["base_url"],
        "query_ignore_endpoints": app_conf["query"]["ignore_endpoints"],
        "query_duration_threshold": app_conf["query"]["duration_threshold"],
    }
    SkywalkingAlarm(task_persistent_path, task_data).start()


if __name__ == '__main__':
    # 根据tasks创建调度任务
    # 调度频率为trigger中cron的值
    # 或者自定义解析
    for item in app_conf["tasks"]:
        # common_job(item, app_conf["tasks"][item])
        sched.add_job(common_job, CronTrigger.from_crontab(app_conf["tasks"][item]["trigger"]["cron"]),
                      args=[item, app_conf["tasks"][item]])
        logger.debug("add scheduler job: %s" % item)
    logger.debug("server is start")
    sched.start()
