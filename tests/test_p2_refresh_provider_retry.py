import unittest
from types import SimpleNamespace
from collector.p2_refresh_batch_observe import query_with_retry,ProviderResponseError
from collector.p2_independent_bars import FIELDS
class Q:
    def __init__(self,ok):
        self.error_code="0" if ok else "100"
        self.fields=FIELDS
        self.done=False
    def next(self):
        if self.done:return False
        self.done=True
        return True
    def get_row_data(self):return ["1"]*len(FIELDS)
class Client:
    def __init__(self,answers):self.answers=iter(answers);self.calls=0
    def query_history_k_data_plus(self,*a,**kw):
        self.calls+=1
        return Q(next(self.answers))
class RetryTests(unittest.TestCase):
    def test_transient(self):
        c=Client([False,True]);wait=[]
        self.assertEqual(len(query_with_retry(c,"sh.600150",16,wait.append)),1)
        self.assertEqual(c.calls,2);self.assertEqual(wait,[5])
    def test_exhausted(self):
        c=Client([False]*3);wait=[]
        with self.assertRaises(ProviderResponseError):query_with_retry(c,"sh.600150",16,wait.append)
        self.assertEqual(c.calls,3);self.assertEqual(wait,[5,10])
