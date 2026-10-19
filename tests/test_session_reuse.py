"""The desktop app can query and then start an activity without a second login."""

import unittest
from pathlib import Path
from unittest.mock import patch

import requests

import xxxx


class FakeAPI:
    def __init__(self, _title, school, username, password, _proxy, _type, session, bank_path):
        self.s = school
        self.u = username
        self.p = password
        self.session = session
        self.bank_path = bank_path
        self.login_calls = 0
        self.exams = []
        self.courseInfo = [{"courseId": "project"}]
        self.activities = {3: {"userActivityId": "mock"}}
        self.jds = {"jd": "1/1", "jds": "模拟考试"}

    def setHeader(self):
        pass

    def setInfo(self, _course, _course_id):
        pass

    def login(self):
        self.login_calls += 1
        return True

    def update(self, *_args):
        pass

    def get_coursesList(self):
        return True

    def getCourses(self):
        return True

    def list_activities(self):
        pass

    def getDetail(self, _course):
        pass

    def handle(self):
        pass

    def work(self, *_args):
        pass

    def exm(self, selection, execute, _score, _duration, _seed):
        self.exams.append((selection, execute))

    def get_jd(self):
        return self.jds


class SessionReuseTest(unittest.TestCase):
    def test_query_then_mock_reuses_login_and_session(self):
        with requests.Session() as session, patch.object(xxxx, "API", FakeAPI):
            bank = Path(__file__).resolve().parents[1] / "题库.xlsx"
            client = xxxx.apiMain(
                "竞赛", "学校", "账号", "密码", None, "deimos", "", "", session,
                activity="list", bank_path=bank,
            )
            result = xxxx.apiMain(
                "竞赛", "学校", "账号", "", None, "deimos", "", "", session,
                activity="mock", execute=True, bank_path=bank, client=client,
            )
            self.assertIs(result, client)
            self.assertEqual(client.login_calls, 1)
            self.assertEqual(client.exams, [({3}, True)])


if __name__ == "__main__":
    unittest.main()
