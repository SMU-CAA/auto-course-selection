import time
from datetime import datetime
from urllib import parse

import pyjson5 as json5
import requests
import yaml
from bs4 import BeautifulSoup
from urllib3 import disable_warnings
from urllib3.exceptions import InsecureRequestWarning

disable_warnings(InsecureRequestWarning)


def read_config():
    with open(file='config.yml', mode='r', encoding='utf-8') as f:
        config = yaml.load(f, Loader=yaml.SafeLoader)
        return config


CONFIG = read_config()

JWXT_BASE_URL = "https://10.81.33.87/shmtu" if CONFIG["app"]["lan"] == True else "https://jwxt.shmtu.edu.cn/shmtu"


def http_client(
    url,
    method="GET",
    params=None,
    headers=None,
    payload=None,
):
    default_headers = {
        "Accept": "*/*",
        "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "max-age=0",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/108.0.0.0"
    }
    headers = default_headers.update(headers) if headers else default_headers
    default_cookie = CONFIG["cookie"]

    while True:
        try:
            response = requests.request(
                method=method,
                url=JWXT_BASE_URL + url,
                data=payload,
                headers=headers,
                params=params,
                cookies=default_cookie,
                verify=False,
                timeout=10
            )
            return response
        except Exception as e:
            print("请求错误，正在重试...")
            # print(e)
            time.sleep(1)


def get_events():
    while True:
        try:
            result = []

            response = http_client("/stdElectCourse.action")
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.select('table.gridtable')[0]
            events = table.select('tbody tr')
            for event in events:
                cell = event.select('td')
                event_name = cell[1].text.strip()
                event_action_url = cell[4].select('a')[0].get('href')
                params = parse.parse_qs(parse.urlparse(event_action_url).query)
                event_id = params["electionProfile.id"][0]

                result.append((event_name, event_id))

            return result
        except:
            print("获取选课事件列表错误，正在重试...")
            time.sleep(1)


def get_session_time(event_id):
    while True:
        try:
            response = http_client(
                "/stdElectCourse!defaultPage.action",
                params={"electionProfile.id": event_id}
            )
            soup = BeautifulSoup(response.text, 'html.parser')
            session_time = soup.select('input#elecSessionTime')[0].get('value')
            return session_time
        except:
            print("获取选课会话时间错误，正在重试...")
            time.sleep(1)


def get_all_courses(event_id):
    while True:
        try:
            response = http_client(
                "/stdElectCourse!data.action",
                params={"profileId": event_id}
            )
            course_json = response.text[18:-1]  # remove `var lessonJSONs = `
            result = json5.loads(course_json)
            return result
        except:
            print("获取所有课程列表错误，正在重试...")
            time.sleep(1)


def map_course_no_id(course_list):
    result = {}
    for course in course_list:
        result[course["no"]] = course["id"]
    return result


def select_course(event_id, course_id, session_time):
    while True:
        try:
            response = http_client(
                "/stdElectCourse!batchOperator.action",
                method="POST",
                params={
                    "profileId": event_id,
                    "elecSessionTime": session_time
                },
                payload={"operator0": "%s:true:0" % course_id}
            )
            soup = BeautifulSoup(response.text, 'html.parser')
            result = soup.select('table')[0].text.strip()

            if "选课成功" in result or "你已经选过" in result:
                return result
            elif "与以下课程冲突" in result:
                return result
            else:
                raise Exception("未知错误")
        except:
            print("选课错误，正在重试...")
            time.sleep(1)


def main():
    print("获取选课事件列表...")
    events = get_events()
    for event in events:
        print("========================================")
        print(event[0])

        print("获取选课会话时间...")
        session_time = get_session_time(event[1])
        print("选课会话时间: %s" % session_time)

        print("获取所有课程列表...")
        all_courses = get_all_courses(event[1])
        print("总计 %d 个课程可以选择" % len(all_courses))
        course_no_id_map = map_course_no_id(all_courses)
        for course in CONFIG["courses"]:
            if course in course_no_id_map:
                print("发现目标课程：%s" % course)
                select_result = select_course(
                    event[1], course_no_id_map[course], session_time)
                print(select_result)


if __name__ == "__main__":
    if CONFIG["app"]["schedule"] == False:
        main()
    else:
        while True:
            if CONFIG["app"]["schedule_time"] <= datetime.now():
                main()
                break
            print("未到设置的选课时间，正在等待...")
            time.sleep(1)
