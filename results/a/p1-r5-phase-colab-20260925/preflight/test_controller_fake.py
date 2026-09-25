"""Tiny offline fakes for R5 source checks and one successful controller path."""
import ast,json,pathlib,sys,tempfile
HERE=pathlib.Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import controller

def main():
 src=controller.sources();assert src['source_commit']=='8e63305f86a3692b9552295c61c4f234a006c105'
 events=[]
 class WD:
  def cancel(self):events.append('cancel')
 def start(session,deadline):events.append('watchdog');return WD()
 def runner(label,argv,timeout):
  events.append(label)
  if label in ('preflight-sessions','finally-sessions'):
   return {'returncode':0,'stdout':'[colab] No active sessions found on server.\n','stderr':''}
  if label=='upload-bundle':
   assert pathlib.Path(argv[-2]).name=='r5-source-bundle.tar.gz'
  if label=='download':pathlib.Path(argv[-1]).write_bytes(b'fake archive')
  return {'returncode':0,'stdout':'','stderr':''}
 with tempfile.TemporaryDirectory() as tmp:
  log=controller.run_once(runner=runner,watchdog_start=start,verify=lambda p:{'setup_status':'phase-pair-complete-NOT-E0','diagnostics_verified':True},now=lambda:100.0,persist=lambda x:None,cli='/fake/colab',archive=pathlib.Path(tmp)/'evidence.tar.gz')
  assert log['status']=='probe-success-collected' and log['VM_stopped_readback']
  assert events.index('watchdog')<events.index('new')
  assert events.index('upload-bundle')<events.index('exec')<events.index('download')
 ast.parse((HERE/'remote_setup.py').read_text())
 code=(HERE/'remote_setup.py').read_text();assert "BASE.mkdir(parents=True,exist_ok=False);EVID.mkdir()" in code
 print(json.dumps({'fake_controller_success':True,'upload_basename':'r5-source-bundle.tar.gz','source_hashes':True,'setup_dirs_bootstrapped':True,'events':events}))
if __name__=='__main__':main()
