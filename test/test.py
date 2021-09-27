import requests


def do_query(data):
    url = 'http://skywalking-trace-monitor.dev.local.wangjiahuan.com/graphql'
    headers = {'content-type': 'application/json'}
    r = requests.post(url, data=data, headers=headers)
    return r.json()


def query_by_trace_id(trace_id):
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
    query_result = do_query(query)
    service_code = query_result["data"]["trace"]["spans"][0]["serviceCode"]
    return service_code


summary_result = {}
"""
{
    "service_name": {
        "count": 1, 
        "endpoint_name":{
            "count": 1,
            "trace_id": "c105d6f8909d454497d41ee6a042bb52.151.16327400972690297"
        }
    }
}

展示时: 
    先展示service_name层级count值高的作为service层级
    再展示endpoint层级count值高的作为endpoint层级
"""


def push_2_summary_result(service_code, endpoint_name, trace_id):
    global summary_result
    if not summary_result.__contains__(service_code):
        summary_result[service_code] = {}
        summary_result[service_code]["count"] = 1
    else:
        summary_result[service_code]["count"] += 1
    if not summary_result[service_code].__contains__(endpoint_name):
        summary_result[service_code][endpoint_name] = {}
        summary_result[service_code][endpoint_name]["count"] = 1
        summary_result[service_code][endpoint_name]["trace_id"] = trace_id
    else:
        summary_result[service_code][endpoint_name]["count"] += 1


def test():
    # query = """{"query":"query queryServices($duration: Duration!,$keyword: String!) {
    #     services: getAllServices(duration: $duration, group: $keyword) {
    #           key: id
    #         label: name
    #         group
    #             }}"
    #         ,"variables":{"duration":{"start":"2021-09-27 1030","end":"2021-09-27 1045","step":"MINUTE"},"keyword":""}}"""
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
        ,"variables":{"condition":{"queryDuration":{"start":"2021-09-27 103715","end":"2021-09-28 105215","step":"SECOND"},"traceState":"ALL","paging":{"pageNum":1,"pageSize":100,"needTotal":true},"queryOrder":"BY_DURATION","minTraceDuration":"1000","tags":[]}}}
    """
    query_result = do_query(query)
    ignore_endpoint_names = ["/ping"]
    global summary_result
    for item in query_result["data"]["data"]["traces"]:
        endpoint_name = item["endpointNames"][0]
        if endpoint_name in ignore_endpoint_names:
            continue
        if item["isError"]:
            continue
        trace_id = item["traceIds"][0]
        service_code = query_by_trace_id(trace_id)
        push_2_summary_result(service_code, endpoint_name, trace_id)


def do_alarm():
    summary_service_result = []
    global summary_result
    for key in summary_result:
        summary_service_result.append({"service": key, "count": summary_result[key]["count"]})
    summary_service_result.sort(key=lambda x: x["count"], reverse=True)
    # print(summary_service_result)
    for service in summary_service_result:
        service_name = service["service"]
        print("-" * 100, service_name, "(%s)" % str(summary_result[service_name]["count"]))
        summary_endpoint_result = []
        for key in summary_result[service_name]:
            if "count" == key:
                continue
            summary_endpoint_result.append(
                {"endpoint": key, "count": summary_result[service_name][key]["count"]})
        summary_endpoint_result.sort(key=lambda x: x["count"], reverse=True)
        for endpoint in summary_endpoint_result:
            print(endpoint["endpoint"], "(%s)" % str(endpoint["count"]), " -- ",
                  summary_result[service_name][key]["trace_id"])


if __name__ == '__main__':
    test()
    # print(summary_result)
    do_alarm()
