#!"D:\0000WorkTechnique\0002dev\python-watcher\.venv\Scripts\python.exe"
import signal
import subprocess
import json
import sys
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent
import psutil
import paho.mqtt.client as mqtt
from datetime import datetime
import os
import time

# https://stackoverflow.com/questions/5568646/usleep-in-python
usleep = lambda x: time.sleep(x/1000000.0)

class Watcher:
    def __init__(self, config, client: mqtt):
        self.running = False
        self.config = config
        self.client = client
        self.client.connect(self.config['broker'], self.config['broker_port'])
        self.observer = Observer()
        self.handler = MyHandler(self.client, self.config)
        self.dir = self.config['watch_path']
        # send a list at startup
        evt = FileModifiedEvent(self.dir)
        evt.first_scan = True
        self.handler.send_files(evt)

    def setConfig(self, config):
        self.config = config

    def run(self):
        self.observer.schedule(self.handler, self.dir, recursive=True)
        self.handler.run()
        self.observer.start()
        self.running = True
        try:
            while self.running:
                time.sleep(1)
        except:
            self.observer.stop()
        self.observer.join()
        # print('observer stopped')
        self.handler.disconnect()
        # print('watcher terminated successfully')

    def stop(self):
        self.running = False
        self.client.loop_stop()
        self.observer.stop()
        # print('watcher stopped successfully')


class MyHandler(FileSystemEventHandler):
    def __init__(self, mqttClient: mqtt, config):
        self.config = config
        self.client = mqttClient
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        # setting arena PID
        self.arena_is_running()
        # print('arena pid : ', self.pid)

    def run(self):
        self.client.loop_start()

    def on_any_event(self, event):
        self.send_files(event)

    def send_files(self, event):
        if (not event.is_directory and event.src_path.endswith('.avc')) or (hasattr(event, 'first_scan')):
            self.publish_watchdog()

    def scan_dir(self):
        files = []
        for f in os.listdir(self.config['watch_path']):
            # filter out everithing without .avc extension and dirs
            if (not os.path.isdir(os.path.join(self.config['watch_path'], f)) and f.endswith('.avc')):
                files.append(os.path.join(self.config['watch_path'], f))
        return files

    def on_message(self, client, userdata, message):
        pload = ''
        try:
            pload = json.loads(message.payload.decode('utf-8'))
        except Exception as err:
            print(err)
        if 'from' in  pload and pload['from'] != 'watchdog':
            if 'start' in pload:
                # start Arena if not running and send a scan
                # print('Starting')
                self.startArena()
                self.publish_start()
            elif 'restart' in pload:
                # start Arena if not running with the selected file
                if 'file' in pload:
                    compo = str(pload['file'])
                    # print("Restarting Arena with " + compo)
                    self.restartArena(compo)
                else:
                    self.publish_restart("No file provided", False)
            elif 'stop' in pload and pload['stop']:
                # print("Stopping Arena...")
                if self.arena_is_running():
                    self.kill_arena()
                    self.publish_stop()
                else:
                    self.publish_stop(False)
            elif 'alive' in pload and pload['alive']:
                self.publish_alive()
            elif 'files' in pload:
                self.publish_watchdog()


    def restartArena(self, compo=None):
        if not self.compoIsOk(compo):
            self.publish_restart(compo + " does not exist or are not supported", False)
            return
        ## check if the process is running
        if self.arena_is_running():
            self.kill_arena()
            time.sleep(0.5)
            fullPath = [os.path.join(self.config['process_path'], self.config['process_exec_name']), compo]
            self.launchProcess(fullPath)
            #waiting resolume to start empiric value 
            time.sleep(10)
            self.publish_restart(compo)
            return

    def startArena(self):
        if self.arena_is_running():
            self.publish_start(False)
            return
        else:
            fullPath = [os.path.join(self.config['process_path'], 
                    self.config['process_exec_name'])]
            self.launchProcess(fullPath)
            time.sleep(10)
            self.publish_start()
            return

            

    def launchProcess(self, args):
            # hack found https://stackoverflow.com/questions/9705652/how-to-hide-stdout-of-subprocess-on-windows
            with open(os.devnull, 'w') as null:
                subprocess.Popen(args, stderr=null, stdout=null,
                    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            return

    def compoIsOk(self, file):
        fileOK = os.path.exists(str(file)) 
        extOK =  str(file).endswith('.avc')
        if  not fileOK or not extOK:
            return 
        return True
        ## check if the process is running

    def publish_watchdog(self):
        data = {
                    'from' : 'watchdog',
                    'action': 'watchdog',
                    'time': datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                    }
        
        data['files'] = self.scan_dir()
        self.client.publish(self.config['state_topic'], json.dumps(data))
    
    def publish_stop(self, wasStopped=True, succes=True ):
        data = {
                    'from' : 'watchdog',
                    'action': 'stop',
                    'time': datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                    }
        if succes:
            data['done'] = True
        if wasStopped:
            data['result'] = 'stopped successfully'
        else:
            data['result'] = 'already stopped'
        self.client.publish(self.config['state_topic'], json.dumps(data))


    def publish_start(self, wasStarted=True, succes=True ):
        data = {
                    'from' : 'watchdog',
                    'action': 'start',
                    'time': datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
                    'data': 0
                    }
        if succes:
            data['done'] = True
        if wasStarted:
            data['result'] = 'started successfully'
        else:
            data['result'] = 'already strated'
        data['files'] = self.scan_dir()
        self.client.publish(self.config['state_topic'], json.dumps(data))

    def publish_restart(self, file_or_err=None, succes=True ):
        data = {
                    'from' : 'watchdog',
                    'action': 'restart',
                    'time': datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
                    'result': 'restarted successfully',
                    'data': file_or_err,
                    'files': self.scan_dir()
                    }
        if succes:
            data['done'] = True
        else:
           data['done'] = False 
           data['result'] = 'error'
        # print("sending restart data : " + json.dumps(data))
        self.client.publish(self.config['state_topic'], json.dumps(data))

    def publish_connect(self):
        data = {
                    'from' : 'whatdog',
                    'action': 'connected',
                    'time': datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
                    'result': 'watchdog listening',
                    'done': True,
                    'data': self.scan_dir()
                    }
        self.client.publish(self.config['state_topic'], json.dumps(data))

    def publish_alive(self):
        self.arena_is_running()
        data = {
                    'from' : 'whatdog',
                    'action': 'connected',
                    'time': datetime.now().strftime('%Y-%m-%d_%H-%M-%S'),
                    'result': 'watchdog listening',
                    'done': True,
                    'files': self.scan_dir()
                    }
        data['arenaRunning'] = True if self.pid != -2 else False
        self.client.publish(self.config['state_topic'], json.dumps(data))


    def on_connect(self, client, userdata, flags, rc):
        self.client.subscribe(self.config['state_topic'])
        self.publish_connect()
        # print("CONNECTED")

    def kill_arena(self):
        os.kill(self.pid, signal.SIGTERM)
        self.pid = -2

    def arena_is_running(self):
        for process in psutil.process_iter(['pid', 'name']):
            if process.name() == self.config['process_exec_name']:
                self.pid = process.pid
                return True
        self.pid = -2
        return False


    def disconnect(self):
        self.client.disconnect()


def read_config(config_file='./config.json'):
    with open('config.json') as config:
        conf = json.load(config)
        return conf





def main(args):
    conf = read_config()
    client = mqtt.Client()
    w = Watcher(conf, client)
    try:
        w.run()
    except KeyboardInterrupt:
        w.stop()


if __name__ == '__main__':
    main(sys.argv)
