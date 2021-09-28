import requests


class Skywalking(object):
    def __init__(self, base_url):
        self.base_url = base_url
        self.summary_result = {}
        """
        {
            "service_name": {
                "count": 1, 
                "endpoint_name":{
                    "count": 1,
                    "duration_min": 1000,
                    "duration_max": 1000,
                    "duration_avg": 1000,
                    "trace_id": "c105d6f8909d454497d41ee6a042bb52.151.16327400972690297"
                }
            }
        }
        
        展示时: 
            先展示service_name层级count值高的作为service层级
            再展示endpoint层级count值高的作为endpoint层级
        """

    def do_query(self, data):
        """
        核心执行查询
        :param data:
        :return:
        """
        headers = {'content-type': 'application/json'}
        r = requests.post(self.base_url, data=data, headers=headers)
        return r.json()

    def push_2_summary_result(self, service_code, endpoint_name, duration, trace_id):
        if not self.summary_result.__contains__(service_code):
            self.summary_result[service_code] = {}
            self.summary_result[service_code]["count"] = 1
        else:
            self.summary_result[service_code]["count"] += 1
        if not self.summary_result[service_code].__contains__(endpoint_name):
            self.summary_result[service_code][endpoint_name] = {}
            self.summary_result[service_code][endpoint_name]["count"] = 1
            self.summary_result[service_code][endpoint_name]["duration_min"] = duration
            self.summary_result[service_code][endpoint_name]["duration_max"] = duration
            self.summary_result[service_code][endpoint_name]["duration_avg"] = duration
            self.summary_result[service_code][endpoint_name]["trace_id"] = trace_id
        else:
            self.summary_result[service_code][endpoint_name]["count"] += 1
            if self.summary_result[service_code][endpoint_name]["duration_min"] > duration:
                self.summary_result[service_code][endpoint_name]["duration_min"] = duration
            if self.summary_result[service_code][endpoint_name]["duration_max"] < duration:
                self.summary_result[service_code][endpoint_name]["duration_max"] = duration
            duration_avg = int((self.summary_result[service_code][endpoint_name]["duration_avg"] + duration) / 2)
            self.summary_result[service_code][endpoint_name]["duration_avg"] = duration_avg

    def query_service_code__by_trace_id(self, trace_id):
        """
        通过trace_id查询服务编码
        :param trace_id:
        :return:
        """
        query = """
        {"query":"query queryTrace($traceId: ID!) {
          trace: queryTrace(traceId: $traceId) {
              spans {
                traceId
                segmentId
                spanId
                parentSpanId
                refs {
                    traceId
                    parentSegmentId
                    parentSpanId
                    type
                }
                serviceCode
                serviceInstanceName
                startTime
                endTime
                endpointName
                type
                peer
                component
                isError
                layer
                tags {
                    key
                    value
                }
                logs {
                    time
                    data {
                         key
                            value
                   }
                 }    }  }
        }"
        ,"variables":{"traceId":"%s"}}
        """ % trace_id
        query_result = self.do_query(query)
        service_code = query_result["data"]["trace"]["spans"][0]["serviceCode"]
        return service_code

    def query_slow_endpoints(self, query_time_start, query_time_end, duration_threshold):
        # 查看所有的慢接口
        query = """{"query":"query queryTraces($condition: TraceQueryCondition) {
          data: queryBasicTraces(condition: $condition) {
              traces {
                key: segmentId
                endpointNames
                duration
                start
                isError
                traceIds
                }
                  total
              }}"
            ,"variables":{"condition":{"queryDuration":{"start":"%s","end":"%s","step":"SECOND"}
            ,"traceState":"ALL","paging":{"pageNum":1,"pageSize":100,"needTotal":true}
            ,"queryOrder":"BY_DURATION","minTraceDuration":"%s","tags":[]}}}
        """ % (query_time_start, query_time_end, duration_threshold)
        return self.do_query(query)

    def get_slow_endpoints(self, query_time_start, query_time_end, duration_threshold, ignore_endpoints):
        result = []
        # 查询基础数据
        slow_endpoints = self.query_slow_endpoints(query_time_start, query_time_end, duration_threshold)
        for item in slow_endpoints["data"]["data"]["traces"]:
            endpoint_name = item["endpointNames"][0]
            if endpoint_name in ignore_endpoints:
                continue
            if item["isError"]:
                continue
            trace_id = item["traceIds"][0]
            duration = item["duration"]
            service_code = self.query_service_code__by_trace_id(trace_id)
            self.push_2_summary_result(service_code, endpoint_name, duration, trace_id)
        # 得到排序后的结果
        summary_service_result = []
        for key in self.summary_result:
            summary_service_result.append({"service": key, "count": self.summary_result[key]["count"]})
        summary_service_result.sort(key=lambda x: x["count"], reverse=True)
        # print(summary_service_result)
        for service in summary_service_result:
            service_name = service["service"]
            # print("-" * 100, service_name, "(%s)" % str(self.summary_result[service_name]["count"]))
            summary_endpoint_result = []
            for key in self.summary_result[service_name]:
                if "count" == key:
                    continue
                summary_endpoint_result.append(
                    {"endpoint": key, "count": self.summary_result[service_name][key]["count"]})
            summary_endpoint_result.sort(key=lambda x: x["count"], reverse=True)
            for endpoint in summary_endpoint_result:
                # print(endpoint["endpoint"], "(%s)" % str(endpoint["count"]), " -- ",
                #       self.summary_result[service_name][key]["trace_id"])
                result.append({
                    "endpoint": service_name + ":" + endpoint["endpoint"],
                    "count": str(endpoint["count"]),
                    "trace_id": self.summary_result[service_name][key]["trace_id"],
                    "duration_min": self.summary_result[service_name][key]["duration_min"],
                    "duration_max": self.summary_result[service_name][key]["duration_max"],
                    "duration_avg": self.summary_result[service_name][key]["duration_avg"],
                })
        return result
