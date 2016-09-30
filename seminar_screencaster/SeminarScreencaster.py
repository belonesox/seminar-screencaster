#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
  Different heuristics to reliable record screencasts on seminars and conferences.
"""
import sys
import os
import time
import subprocess
import datetime
import re
import signal
import socket
import errno
import Xlib
import Xlib.display


def mkdir_p(path):
    '''
     «mkdir -p»
    '''
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise

class RecordingProcess(object):
    def __init__(self, process, filename):
        '''
          Associate process with filename 
        '''
        self.process = process
        self.filename = filename

    def shutdown(self):
        '''
        Shutdown the process
        '''
        try:
            os.kill(self.process.pid, signal.SIGINT)
        except:
            pass

class SeminarScreencaster:
    """
      Record video from several sources.
    """
    def __init__(self):
        """
        Cleaning and initializing
        """
        os.system('killall ffmpeg')

        self.filesize = {}

        #home/working directory
        self.homedir = os.getcwd()
        self.recorddir = None
        self.translated_file = None
        self.grabbers = None

        self.logdir = os.path.join(os.getenv("HOME"),
                                   'SparkleShare/seminar_screencaster_logs')
        if not os.path.exists(self.logdir):
            self.logdir = '.'

        stime = self.iso_time()
        logname = '-'.join([socket.gethostname(), stime]) + '.log'
        self.logfilename = os.path.join(self.logdir, logname)
        self.loglines = []
     
        self.display = ':0.0'    
        if 'DISPLAY' in os.environ:
            self.display = os.environ['DISPLAY']

        # self.display = Xlib.display.Display()
        # self.screen = self.display.screen()
        # self.dummy_window = self.screen.root.create_window(0, 0, 1, 1, 1, self.screen.root_depth)     
        self.reload_screens()
     
        pass
        
        
    def reload_screens(self):
        '''
          Reload Displays  
        '''    
        resolution = Xlib.display.Display().screen().root.get_geometry()
        output = self.get_out_from_cmd('xrandr')
        self.active_screens = {}        
#        for mre in re.findall(r'(?P<w>\d+)x(?P<h>\d+)\+(?P<x>\d+)\+(?P<y>\d+))', output):
        for mre in re.findall(r'(?P<geometry>\d+x\d+\+\d+\+\d+)', output):
            # disp_x = mre.groups('x')
            # disp_y = mre.groups('y')
            # disp_w = mre.groups('w')
            # disp_h = mre.groups('h')
            geometry = mre
            gre = re.match(r"(?P<w>\d+)x(?P<h>\d+)\+(?P<x>\d+)\+(?P<y>\d+)", geometry)
            self.active_screens[geometry] = (int(gre.group('x')),
                                             int(gre.group('y')),
                                             int(gre.group('w')),
                                             int(gre.group('h')))
        pass         

    def iso_time(self):
        '''
        return ISO time suited for path  
        '''
        now = datetime.datetime.now()  #pylint: disable=E1101
        millis = now.microsecond/1000
        stime = now.strftime('%Y-%m-%d-%H-%M-%S') + '-' + "%03d" % millis 
        return stime

    def print_status_line(self):
        '''
        Print log line, using state of recording files. 
        ''' 

        def size4file(filename):
            filesize = str(os.stat(filename).st_size/1024/1024) + 'M'
            return filesize
        
        stime = self.iso_time()
        terms = [stime, '> ']
        for screen in set(self.grabbers.keys()).intersection(self.active_screens.keys()):
            filesize_ = 'NA'
            fname = self.grabbers[screen].filename

            if fname and os.path.exists(fname):
                filesize_ = size4file(fname)
                terms += [' %(screen)s=' % vars(), filesize_]
                # if screen in self.filesize:
                #     if self.filesize[screen] == filesize_:
                #         self.grabbers[screen].shutdown()
                #         filesize = '---'
                #         time.sleep(3)
            self.filesize[screen] = filesize_

        logline = "".join(terms)
        print logline
        self.loglines = [logline] + self.loglines[:100]
        lf = open(self.logfilename, 'w')
        lf.write('\n'.join(self.loglines))
        lf.close()

    def get_out_from_cmd(self, scmd):
        """
        Get output from command
        """
        progin, progout = os.popen4(scmd)
        sresult =  progout.read()

        progin.close()
        progout.close()

        return sresult

    def activate_screencasting(self):
        for screen in self.active_screens:
            if screen in self.grabbers:
                pr = self.grabbers[screen].process.poll()
                if not (pr == None):
                    self.grabbers[screen].shutdown()
                    del self.grabbers[screen]
                    self.start_screen_record(screen)
            else:
                self.start_screen_record(screen)

        exist_live = False
        for screen in self.grabbers:
            pr_ = self.grabbers[screen].process.poll()
            if pr_ == None:
                exist_live = True
        return exist_live


    def start_screen_record(self, screen):
        '''
        Activate record for new display of display with changed resolution 
        '''    

        stime = self.iso_time()
        screenfilename = "-".join([stime, screen]) + '.flv'

        geoopt = self.display.strip() + '+%d,%d' % self.active_screens[screen][0:2]
        video_size =  '%dx%d' % self.active_screens[screen][2:]
        
        scmd = ('nice -n 19 '
               ' ffmpeg -y '
               ' -video_size ' + video_size +
               ' -f x11grab -r 8 '
               ' -i ' + geoopt +
               ' -f alsa -i pulse -ab 256K -ar 44100 '
               '-vcodec libx264 -preset ultrafast -qmin 2 -qmax 4  -vsync 1 '
               ' -f flv '
               + screenfilename)

        print scmd
        slog = open("screen-%(screen)s.log" % vars(), "w")
        pid = subprocess.Popen(scmd, shell=True, stderr=slog)
        rp = RecordingProcess(pid, screenfilename)
        self.grabbers[screen] = rp
        slog.close()
        pass


    def start_recording(self, recordpath):
        """
         Fork tools for recording screen and sound with given parameters.
         Kill both then one of them are ends up.
        """
        def directory_ok(thedir):
            if not os.path.exists(thedir):
                try:
                    mkdir_p(thedir)
                    os.chdir(thedir)
                except:
                    pass
                if os.path.exists(thedir):
                    return True
                return False
            else:
                testdir = os.path.join(thedir, '~~test-for-recording')
                try:
                    mkdir_p(testdir)
                except:
                    pass
                if os.path.exists(testdir):
                    os.rmdir(testdir)
                    return True
            return False

        homedir = os.getcwd()

        if not directory_ok(recordpath):
            print 'Cannot create directory "%s" for recording, call Stas Fomin!' % recordpath
            sys.exit(0)

        stime = self.iso_time()
        os.chdir(recordpath)
        recorddir = "-".join([stime, r"recording"])
        recorddir = os.path.realpath(recorddir)
        if not os.path.exists(recorddir):
            os.mkdir(recorddir)
        self.recorddir = os.path.realpath(recorddir)
        os.chdir(recorddir)

        self.grabbers = {}

        try:
            while True:
                self.reload_screens()
                self.activate_screencasting()
                self.print_status_line()
                time.sleep(10)
            pass

        except KeyboardInterrupt:
            pass
            print 'Keyboard INT'
        print "Recording stopped!"
        os.chdir(homedir)

def main():
    '''
    Start recording from all available sources.
    '''
    recordpath = 'screencasts'
    if len(sys.argv) > 1:
        recordpath = sys.argv[1]

    semrec = SeminarScreencaster()
    #os.setpgrp()
    try:
        semrec.start_recording(recordpath)
    finally:
        pass
        #os.killpg(0, signal.SIGKILL) 


if __name__ == '__main__':
    main()
