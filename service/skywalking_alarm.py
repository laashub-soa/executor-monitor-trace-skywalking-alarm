import datetime
import json
import logging
import os
import time
from urllib import parse

from component import skywalking, dingding_webhook

logger = logging.getLogger('loki_ruler')
logger.setLevel(logging.DEBUG)


class SkywalkingAlarm(object):
    def __init__(self, task_persistent_path, task_data):
        # 任务初始数据
        self.task_persistent_path = task_persistent_path
        self.init_service_damage_time_point_path = os.path.join(self.task_persistent_path,
                                                                "init_service_damage_time_point")
        self.init_service_damage_time_point = None
        self.task_data = task_data
        # 任务局部数据
        self.damage_time_point = {  # 受损时间点
            "total": 0,  # 总体
            "each": {}  # 详细 {"oss-api": 1630857600000}
        }
        self.now_time_second = 0
        self.service_mapping_follow_user = None  # 服务被关注的用户

    # 获取上次业务受损时间点
    def get_init_service_damage_time_point(self):
        if not os.path.exists(self.init_service_damage_time_point_path):
            self.init_service_damage_time_point = {
                "total": 0,
                "each": {},
            }
        else:
            with open(self.init_service_damage_time_point_path, "r", encoding="utf-8")as f:
                self.init_service_damage_time_point = json.loads(f.read())
        return self.init_service_damage_time_point

    # 设置初始化业务受损时间点
    def set_init_service_damage_time_point(self):
        with open(self.init_service_damage_time_point_path, "w", encoding="utf-8")as f:
            f.write(json.dumps(self.init_service_damage_time_point))
            print(self.init_service_damage_time_point)

    # 获取关注服务的用户及手机号码
    def get_service_follow_of_user_name_phone_list(self, service_name):
        if not self.service_mapping_follow_user:
            self.service_mapping_follow_user = {}  # {"oss-api": [tristan, tristan2]}
            user_follow_service = self.task_data["common"]["user_follow_service"]
            for user_name in user_follow_service:
                service_list = user_follow_service[user_name]
                for item in service_list:
                    if item not in self.service_mapping_follow_user:
                        self.service_mapping_follow_user[item] = [user_name]
                    else:
                        self.service_mapping_follow_user[item].append(user_name)
        user_name_list = []
        user_phone_list = []
        if "" != service_name:
            user_code_list = self.service_mapping_follow_user[service_name]
            for item in user_code_list:
                user_info_group_str = self.task_data["common"]["user_info"][item]
                user_info_group = user_info_group_str.split("-")
                user_name = user_info_group[0]
                user_phone = user_info_group[1]
                if user_name not in user_name_list:
                    user_name_list.append(user_name)
                if user_phone not in user_phone_list:
                    user_phone_list.append(user_phone)
        return user_name_list, user_phone_list

    # 获取最精简化的时间点
    def get_single_time(self, time_point):
        time_point_timestamp = time_point / 1000000 / 1000
        target_datetime = datetime.datetime.fromtimestamp(time_point_timestamp)
        return str(target_datetime.hour) + ":" + str(target_datetime.minute)

    # 获取最小化显示受损时间持续段
    def get_minimize_display_damage_time_duration(self, ori_time_duration):
        """
        :param ori_time_duration: 原始持续时间(单位秒钟)
        :return:
        """
        result = ""
        if ori_time_duration > 60:  # 超过1个分钟
            if ori_time_duration > 3600:  # 超过1个小时
                if ori_time_duration > 86400:  # 超过1个天
                    if ori_time_duration > 2678400:  # 超过1个月
                        result += str(int(ori_time_duration / 2678400)) + "月"
                        ori_time_duration = ori_time_duration % 2678400
                    result += str(int(ori_time_duration / 86400)) + "天"
                    ori_time_duration = ori_time_duration % 86400
                result += str(int(ori_time_duration / 3600)) + "时"
                ori_time_duration = ori_time_duration % 3600
            result += str(int(ori_time_duration / 60)) + "分"
            ori_time_duration = ori_time_duration % 60
        result += str(int(ori_time_duration)) + "秒"
        return result

    # 获取服务点击链接
    def get_query_service_url(self, service_name):
        query_service_url = self.task_data["alarm"]["loki_click_base_url"] \
            .replace("{SERVICE_NAME}", service_name) \
            .replace("{QUERY_FROM_TIME}", str(int(self.loki_query_time_start / 1000000))) \
            .replace("{QUERY_TO_TIME}", str(int(self.loki_query_time_end / 1000000)))
        logger.debug(query_service_url)
        return self.task_data["alarm"]["loki_click_base_prefix"] + parse.quote(query_service_url)

    def gen_detail_alarm_msg(self, ori_alarm_data):
        ori_alarm_data_list = []
        for key in ori_alarm_data:
            value = ori_alarm_data[key]["total_count"]
            ori_alarm_data_list.append({"name": key, "count": value})
        ori_alarm_data_list.sort(key=lambda x: x["count"], reverse=True)
        alarm_msg_text = ""
        new_damage_time_point_each = {}
        at_user_list = []
        for item in ori_alarm_data_list:
            service_name = item["name"]
            service_count = item["count"]
            query_service_url = self.get_query_service_url(service_name)
            follow_of_users, follow_of_phones = self.get_service_follow_of_user_name_phone_list(service_name)
            if int(self.task_data["alarm"]["maximum_tolerance_count"]) < service_count:
                at_user_list += follow_of_phones
            new_damage_time_point_each[service_name] = self.now_time_second  # 秒钟
            damage_time_duration_str = "(首次)"
            if service_name not in self.init_service_damage_time_point["each"]:
                self.init_service_damage_time_point["each"][service_name] = self.now_time_second
            else:
                damage_time_duration = self.now_time_second - int(
                    self.init_service_damage_time_point["each"][service_name])
                damage_time_duration_str = self.get_minimize_display_damage_time_duration(damage_time_duration)
            follow_of_phone_str = ""
            for follow_of_phone in follow_of_phones:
                follow_of_phone_str += "@" + str(follow_of_phone)
            alarm_msg_text += self.task_data["alarm"]["template"].format(service_name=service_name,
                                                                         query_service_url=query_service_url,
                                                                         service_count=service_count,
                                                                         follow_of_users=follow_of_phone_str,
                                                                         damage_time_duration=damage_time_duration_str
                                                                         ) + "\n\n"
        self.damage_time_point["each"] = new_damage_time_point_each

        return self.task_data["alarm"]["head_template"] + alarm_msg_text, list(set(at_user_list))

    def convert_query_time_range(self, query_time_range):
        """
        转换查询时间范围
        :param query_time_range: 查询时间范围
        :return: 单位: 毫秒
        """
        # "rel: 5m-0m"
        # "fix: h0-h24"
        time_type_index = query_time_range.find(": ")
        time_type = query_time_range[:time_type_index]
        time_range = query_time_range[time_type_index + 2:]
        time_start_end_index = time_range.find("-")
        time_start = time_range[:time_start_end_index]
        time_end = time_range[time_start_end_index + 1:]

        # 统一转换成分钟单位
        def convert_rel_time_value_unit_2_minute(ori_time_value_unit):
            time_value = ori_time_value_unit[:-1]
            time_unit = ori_time_value_unit[-1:]
            if "m" == time_unit.lower():
                pass
            elif "h" == time_unit.lower():
                time_value = time_value * 60
            elif "d" == time_unit.lower():
                time_value = time_value * 60 * 24
            else:
                raise Exception("数据格式解析异常: %s" % time_unit)
            return int(time_value)

        def convert_fix_time_value_unit(ori_time_value_unit):
            time_unit = ori_time_value_unit[:1]
            time_value = int(ori_time_value_unit[1:])
            if "h" == time_unit:
                now_datetime = datetime.datetime.now()
                if time_value > 23:
                    time_value = datetime.datetime(year=now_datetime.year, month=now_datetime.month,
                                                   day=now_datetime.day,
                                                   hour=0, minute=0, second=0)
                    time_value = (time_value + datetime.timedelta(days=1)).timestamp()
                else:
                    time_value = datetime.datetime(year=now_datetime.year, month=now_datetime.month,
                                                   day=now_datetime.day,
                                                   hour=time_value, minute=0, second=0).timestamp()
            else:
                raise Exception("数据格式解析异常: %s" % time_unit)
            return time_value

        if "rel" == time_type:
            start_query_time = (datetime.datetime.now() - datetime.timedelta(
                minutes=convert_rel_time_value_unit_2_minute(time_start))).timestamp()
            end_query_time = (datetime.datetime.now() - datetime.timedelta(
                minutes=convert_rel_time_value_unit_2_minute(time_end))).timestamp()
        elif "fix" == time_type:
            start_query_time = convert_fix_time_value_unit(time_start)
            end_query_time = convert_fix_time_value_unit(time_end)
        else:
            raise Exception("未知类型的查询时间, 请检查配置: job.query_time_range")

        return int(start_query_time * 1000 * 1000000), int(end_query_time * 1000 * 1000000)

    # 查询数据
    def query_data(self):
        total_alarm_msg = ""
        # 查询数据
        self.loki_query_time_start, self.loki_query_time_end = self.convert_query_time_range(
            self.task_data["job"]["query_time_range"]
        )
        resp_data = loki.query(self.task_data["common"]["loki_base_uri"], self.task_data["job"]["logql"],
                               self.loki_query_time_start,
                               self.loki_query_time_end)
        # 解析数据并生成告警字符串
        # # 总体受损
        logger.debug(resp_data)
        total_damage_service_count = 0  # 服务数量
        # total_damage_service_node_count = 0  # 服务节点数量

        # # 服务受损
        service_damage = {}  # {"oss-api": {"wjh-prod": {"lmbrn": {"file_name_1":1}}}}
        query_result = resp_data["data"]["result"]
        if len(query_result) < 1:  # 当没有查询到异常日志项的时候
            # (重新)初始化数据
            init_service_damage_time_point = self.get_init_service_damage_time_point()
            init_service_damage_time_point["total"] = 0
            init_service_damage_time_point["each"] = {}

            return total_alarm_msg, {}
        # 遍历loki查询数据
        query_result = resp_data["data"]["result"]
        for item in query_result:
            # 解析值
            metric = item["metric"]
            service_name = metric["replicaset"]
            # service_env = metric["environment"]
            # service_node_name = metric["pod"] + "__" + metric["filename"]
            service_node_count = int(item["values"][len(item["values"]) - 1][1])
            # 加工数据
            # 切入到当前服务层级
            if service_name not in service_damage:
                service_damage[service_name] = {"total_count": 0}
                total_damage_service_count += 1
            service_damage[service_name]["total_count"] += service_node_count

        # 生成总体告警头
        alarm_query_start_time = self.get_single_time(self.loki_query_time_start)  # 精确到小时分钟即可
        alarm_query_end_time = self.get_single_time(self.loki_query_time_end)
        logger.debug(
            "alarm_query_start_time: %s, alarm_query_end_time: %s" % (alarm_query_start_time, alarm_query_end_time))
        alarm_damage_service_count = total_damage_service_count

        if self.init_service_damage_time_point["total"] == 0:
            alarm_damage_time_duration = "(首次)"
            self.init_service_damage_time_point["total"] = self.now_time_second
        else:
            alarm_damage_time_duration = self.get_minimize_display_damage_time_duration(
                self.now_time_second - self.init_service_damage_time_point["total"])
        total_alarm_msg = self.task_data["alarm"]["total_template"].format(query_start_time=alarm_query_start_time,
                                                                           query_end_time=alarm_query_end_time,
                                                                           damage_service_count=alarm_damage_service_count,
                                                                           damage_time_duration=alarm_damage_time_duration) + "\n\n"
        return total_alarm_msg, service_damage

    def start(self):
        access_token = self.task_data["common"]["dingding_webhook_access_token"][0]
        try:
            self.now_time_second = int(time.time())
            self.get_init_service_damage_time_point()
            total_alarm_msg, query_loki_result = self.query_data()
            if len(query_loki_result.keys()) < 1:
                return
            logger.debug(total_alarm_msg)
            logger.debug("query_loki_result: ", query_loki_result)
            detail_alarm_msg, at_phone_list = self.gen_detail_alarm_msg(query_loki_result)
            logger.debug(detail_alarm_msg)
            logger.debug(at_phone_list)
            # 告警
            if not self.task_data["alarm"]["is_at"]:
                at_phone_list = []
            alarm_result = dingding_webhook.alarm(access_token, "logging", total_alarm_msg + detail_alarm_msg,
                                                  at_phone_list)
            logger.debug(alarm_result)
        except Exception as e:
            import traceback, sys
            traceback.print_exc()  # 打印异常信息
            exc_type, exc_value, exc_traceback = sys.exc_info()
            error = str(repr(traceback.format_exception(exc_type, exc_value, exc_traceback)))
            msg_template_details = error
            logger.debug(msg_template_details)
            msg_template_details = str(e)
            alarm_result = dingding_webhook.alarm(access_token, "logging", msg_template_details, [])
            logger.debug(alarm_result)
        finally:
            self.set_init_service_damage_time_point()
