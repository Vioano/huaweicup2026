"""Install one per-user non-LLM supervisor at login. Uses existing runtimes only."""
from __future__ import annotations
import argparse
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from .engine import read_json
from .snapshot import atomic_write

LABEL='com.huaweicup.benchmark-sync'
TASK='HuaweiCup-Benchmark-Sync'


def launcher(state):
    atomic_write(state/'start.py',Path(__file__).with_name('launcher.py').read_bytes())


def install(config_path,*,start=False):
    config=read_json(config_path);state=Path(config['state']);launcher(state)
    (state/'logs').mkdir(parents=True,exist_ok=True)
    if sys.platform=='darwin':
        path=Path.home()/'Library/LaunchAgents'/f'{LABEL}.plist'
        bins=[str(Path(config[k]).parent) for k in ('python','node','gh')]
        bins+=[str(Path(shutil.which('git')).parent),'/usr/bin','/bin','/usr/sbin','/sbin']
        payload={'Label':LABEL,'ProgramArguments':[config['python'],'-X','utf8',str(state/'start.py')],
                 'WorkingDirectory':str(state),'RunAtLoad':True,'KeepAlive':True,'ThrottleInterval':15,
                 'EnvironmentVariables':{'PATH':':'.join(dict.fromkeys(bins)),'PYTHONUTF8':'1'},
                 'StandardOutPath':str(state/'logs/launcher.log'),'StandardErrorPath':str(state/'logs/launcher.err')}
        atomic_write(path,plistlib.dumps(payload))
        if start:
            existing=subprocess.run(['launchctl','print',f'gui/{os.getuid()}/{LABEL}'],capture_output=True)
            if existing.returncode==0: raise RuntimeError('Existing supervisor already registered; use its current service, do not duplicate it')
            subprocess.run(['launchctl','bootstrap',f'gui/{os.getuid()}',str(path)],check=True)
        return str(path)
    if os.name=='nt':
        sid=subprocess.check_output(['powershell.exe','-NoProfile','-NonInteractive','-Command',
             '[System.Security.Principal.WindowsIdentity]::GetCurrent().User.Value'],text=True).strip()
        ns='http://schemas.microsoft.com/windows/2004/02/mit/task';ET.register_namespace('',ns)
        def child(parent,name,text=None,**attrs):
            e=ET.SubElement(parent,'{'+ns+'}'+name,attrs)
            if text is not None: e.text=text
            return e
        task=ET.Element('{'+ns+'}Task',{'version':'1.4'})
        trigger=child(child(task,'Triggers'),'LogonTrigger');child(trigger,'Enabled','true');child(trigger,'UserId',sid)
        principal=child(child(task,'Principals'),'Principal',id='Author')
        child(principal,'UserId',sid);child(principal,'LogonType','InteractiveToken');child(principal,'RunLevel','LeastPrivilege')
        settings=child(task,'Settings')
        for k,v in {'MultipleInstancesPolicy':'IgnoreNew','DisallowStartIfOnBatteries':'false','StopIfGoingOnBatteries':'false',
                    'StartWhenAvailable':'true','ExecutionTimeLimit':'PT0S'}.items(): child(settings,k,v)
        restart=child(settings,'RestartOnFailure');child(restart,'Interval','PT1M');child(restart,'Count','3')
        command=child(child(task,'Actions',Context='Author'),'Exec')
        child(command,'Command',config['python']);child(command,'Arguments',subprocess.list2cmdline(['-X','utf8',str(state/'start.py')]))
        child(command,'WorkingDirectory',str(state))
        path=state/'scheduled-task.xml';atomic_write(path,ET.tostring(task,encoding='utf-16',xml_declaration=True))
        subprocess.run(['schtasks.exe','/Create','/TN',TASK,'/XML',str(path),'/F'],check=True)
        if start: subprocess.run(['schtasks.exe','/Run','/TN',TASK],check=True)
        return TASK
    raise RuntimeError('Automatic login installation supports macOS and Windows; run start.py manually on other systems')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--config',type=Path,required=True);p.add_argument('--start',action='store_true')
    args=p.parse_args();print(install(args.config,start=args.start))

if __name__=='__main__': main()
