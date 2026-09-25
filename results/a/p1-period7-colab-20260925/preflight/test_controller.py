"""Fake-only controller ordering checks; no Colab CLI or VM."""
from pathlib import Path
import tempfile,unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parent))
import controller as c
class FakeWatchdog:
 def __init__(self):self.cancelled=False
 def cancel(self):self.cancelled=True
class ControllerFlowTests(unittest.TestCase):
 def run_flow(self,*,active=False,exec_failed=False,stop_uncertain=False,verify_failed=False,real_prefix=False):
  steps=[];watch=FakeWatchdog();now=[0.0];saved=[]
  with tempfile.TemporaryDirectory() as td:
   archive=Path(td)/'evidence.tar.gz'
   def runner(label,argv,timeout):
    steps.append(label);now[0]+=1
    if label in ('download','salvage-download'):archive.write_bytes(b'fake archived bytes')
    empty='[colab] '+c.EMPTY+'\n' if real_prefix else c.EMPTY
    return {'step':label,'returncode':1 if label=='exec' and exec_failed else 0,
            'stdout':'Active session' if ((label=='preflight-sessions' and active) or (label=='finally-sessions' and stop_uncertain)) else empty if label.endswith('sessions') else '',
            'stderr':''}
   def start(session,deadline):
    self.assertEqual(deadline,now[0]+270);return watch
   def verify(p):
    if verify_failed:raise ValueError('fake archive mismatch')
    return {'archive_sha256':'fake','setup_status':'failed' if exec_failed else 'probe-complete','plan_sha256_verified':not exec_failed}
   with patch.object(c,'sources',return_value={'bundle_sha256':'fake'}):
    result=c.run_once(runner=runner,watchdog_start=start,
     verify=verify,
     now=lambda:now[0],persist=lambda x:saved.append(x.copy()),cli='/fake/colab',archive=archive)
   return steps,result,watch,saved
 def test_success_once_and_stop_readback(self):
  steps,result,watch,saved=self.run_flow()
  self.assertEqual(steps,['preflight-sessions','new','upload-bundle','exec','download','finally-stop','finally-sessions'])
  self.assertTrue(result['probe_success'] and result['archive_collected'] and result['VM_stopped_readback'])
  self.assertTrue(watch.cancelled)
 def test_observed_prefixed_stdout_passes_preflight_and_stop_readback(self):
  steps,result,watch,_=self.run_flow(real_prefix=True)
  self.assertEqual(steps[0],'preflight-sessions')
  self.assertEqual(steps[-1],'finally-sessions')
  self.assertTrue(result['probe_success'] and result['VM_stopped_readback'])
  self.assertTrue(watch.cancelled)
 def test_empty_session_parser_rejects_ambiguous_or_error_output(self):
  good={'returncode':0,'stdout':'[colab] No active sessions found on server.\n','stderr':''}
  self.assertTrue(c.empty_sessions_receipt(good))
  for changed in ({'returncode':1}, {'stderr':'error'},
                  {'stdout':'[colab] p1-period7-008-20260925\n'},
                  {'stdout':'[colab] No active sessions found on server.\nother text'},
                  {'stdout':'[colab] [colab] No active sessions found on server.\n'},
                  {'stdout':'[colab] Error: No active sessions found on server.\n'}):
   self.assertFalse(c.empty_sessions_receipt({**good,**changed}),changed)
 def test_exec_failure_salvages_and_stops_without_retry(self):
  steps,result,watch,_=self.run_flow(exec_failed=True)
  self.assertEqual(steps.count('exec'),1)
  self.assertEqual(steps.count('new'),1)
  self.assertIn('salvage-download',steps)
  self.assertEqual(steps[-2:],['finally-stop','finally-sessions'])
  self.assertFalse(result['probe_success'])
 def test_active_preflight_never_creates_vm(self):
  steps,result,watch,_=self.run_flow(active=True)
  self.assertEqual(steps,['preflight-sessions'])
  self.assertEqual(result['status'],'preflight-failed')
  self.assertFalse(watch.cancelled)
 def test_uncertain_stop_does_not_cancel_watchdog_or_claim_success(self):
  steps,result,watch,_=self.run_flow(stop_uncertain=True)
  self.assertEqual(result['status'],'stop-unconfirmed')
  self.assertFalse(result['probe_success'])
  self.assertFalse(watch.cancelled)
 def test_bad_archive_is_not_accepted_or_redownloaded(self):
  steps,result,watch,_=self.run_flow(verify_failed=True)
  self.assertFalse(result['archive_collected'])
  self.assertFalse(result['probe_success'])
  self.assertEqual(steps.count('download'),1)
  self.assertNotIn('salvage-download',steps)
  self.assertTrue(result['VM_stopped_readback'])
if __name__=='__main__':unittest.main()
