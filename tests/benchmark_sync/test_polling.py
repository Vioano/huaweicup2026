import unittest
from unittest.mock import patch
from src.benchmark_sync.__main__ import poll_delay

class PollingTests(unittest.TestCase):
    def test_backlog_runs_promptly_but_offline_and_rate_limits_still_back_off(self):
        config={'role':'leader','poll_seconds':5}
        active={'state':'online','receive':{'pending':12}}
        with patch('src.benchmark_sync.__main__.time.time',return_value=100):
            self.assertEqual(poll_delay(config,active,0,0),2)
            self.assertEqual(poll_delay(config,{'state':'online','receive':{'pending':0}},0,0),5)
            self.assertEqual(poll_delay(config,dict(active,state='offline'),3,0),40)
            self.assertEqual(poll_delay(config,active,0,180),80)
            self.assertEqual(poll_delay(config,dict(active,error={'retry_after':90}),0,0),90)
            self.assertEqual(poll_delay(dict(config,role='member'),active,0,0),5)
