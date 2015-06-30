import socket
import time

from threading import Thread
from paramiko import AutoAddPolicy, SSHClient, SSHException, \
AuthenticationException


class SSHCollector(Thread):
    def __init__(self, hostname, username, password, proto,
            loggername, zapiport, sshport=22, keepalive=True, timeout=60):
        Thread.__init__(self)
        self.hostname = hostname
        self.username = username
        self.password = password
        self.keepalive = keepalive
        self.timeout = timeout
        self._conn = None
        self.success = False
        self.client = SSHClient()
        self.client.load_system_host_keys()
        self.client.set_missing_host_key_policy(AutoAddPolicy())
        self.client.set_log_channel(loggername)

    def _connect(self):
        if None is not self.client.get_transport() and \
            self.client.get_transport().is_active():
            return
        if None is self.username:
            self.client.connect(hostname=self.hostname,
                                timeout=self.timeout)
        elif None is self.password:
            self.client.connect(hostname=self.hostname,
                                username=self.username,
                                password=self.password,
                                timeout=self.timeout)
        else:
            self.client.connect(hostname=self.hostname,
                                username=self.username,
                                password=self.password,
                                look_for_keys=False,
                                timeout=self.timeout)
        trans = self.client.get_transport()
        trans.use_compression(True)
        trans.set_keepalive(1)

    def close(self):
        self.client.close()

    __del__ = close

    def execute(self, lcmd, auto_close=False, timeout=300, read_max=10*1024*1024):
        output = r''
        err = r''
        self._error = ""
        read_max = int(read_max/2)
        exit_status = False

        self._connect()
        chan = self.client.get_transport().open_session()
        if not self.keepalive:
            self.client.get_transport().set_keepalive(0)
        chan.settimeout(timeout)
        chan.exec_command(lcmd)

        stdin = chan.makefile('wb', -1)
        stdout = chan.makefile('rb', -1)
        stderr = chan.makefile_stderr('rb', -1)

        start_time = time.time()

        while True:
            if stderr.channel.recv_stderr_ready():
                ret = stderr.read()
                if ret:
                    err += ret

            if stdout.channel.recv_ready():
                try:
                    ret = stdout.read(read_max)
                    if ret:
                        output += ret
                except socket.timeout:
                    pass

            exit_status = chan.exit_status_ready()
            if exit_status or ((int(start_time) + timeout) < int(time.time())):
                timeout = False
                if exit_status:
                    exit_status = str(stderr.channel.recv_exit_status())
                else:
                    self.signal(chan, 'KILL')
                    exit_status = str(stderr.channel.recv_exit_status())
                    timeout = True

            if stdin:
                stdin.channel.shutdown_write()
                stdin.close()

            if stdout.channel.recv_ready():
                ret = stdout.read(read_max)
                if ret:
                    output += ret
            stdout.close()

            if stderr.channel.recv_stderr_ready():
                ret = stderr.read()
                if ret:
                    err += ret
            err += "exit_status("+str(exit_status)+") to("+str(timeout)+")"
            stderr.close()
            break

        self.success = True
        if auto_close:
            self.client.close()

        return (output, err)

    def setCommand(self, cmd):
        self.cmd = cmd

    def runcmd(self, cmd):
        return self.execute(cmd, auto_close=True)

    def run(self):
        self.resultset = self.runcmd(self.cmd)

if __name__ == '__main__':

    cmd = 'date'
    threads = []
    a = time.time()
    for i in range(3):
        collector = SSHCollector('173.39.245.139', 'sds',  '31415SdS31415', \
	                      'auto', 'dummylogger', None)
    collector.setCommand(cmd)
    threads.append(collector)
    for i in threads:
        i.start()
    for i in threads:
        i.join()
    for i in threads:
        print i.resultset
    b=time.time()
    print b-a
