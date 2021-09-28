from component.skywalking import Skywalking

if __name__ == '__main__':
    base_url = "http://skywalking-trace-monitor.dev.local.wangjiahuan.com/graphql"
    query_time_start = "2021-09-28 003715"
    query_time_end = "2021-09-28 105215"
    duration_threshold = "1000"
    ignore_endpoints = ["/ping"]
    slow_endpoints = Skywalking(base_url).get_slow_endpoints(query_time_start, query_time_end, duration_threshold,
                                                             ignore_endpoints)
    # print(slow_endpoints)
    for item in slow_endpoints:
        print(item)
