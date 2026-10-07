import pathlib,unittest
class T(unittest.TestCase):
 def test_limits(self):
  s=pathlib.Path("proxy/server.py").read_text();self.assertIn("2_000_000",s);self.assertIn("User-Agent",s)
if __name__=="__main__":unittest.main()
