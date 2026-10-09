"""Focused mouse/keyboard window for IN v1; absolute angles tolerate UDP loss."""
import argparse
import binascii
import math
import secrets
import socket
import struct
import time

def packet(frame,sequence,buttons,yaw,pitch):
    if any(type(v) is not int for v in (buttons,yaw,pitch)) or not 0<=buttons<=255 or not 0<=yaw<=255 or not -32<=pitch<=32:
        raise ValueError('IN v1 requires buttons/yaw 0..255 and pitch -32..32')
    payload=b'IN'+bytes((1,sequence&255,buttons,yaw,pitch&255))+bytes(17)
    command=b'GF'+bytes((2,11,24))+payload
    command+=struct.pack('>H',binascii.crc_hqx(command,0xffff))
    return struct.pack('>2sBBIHH',b'GP',2,3,frame&0xffffffff,0,len(command))+command

class Sender:
    def __init__(self,ip,port):
        self.target=(ip,port);self.frame=secrets.randbits(32);self.sequence=0
        self.replies=0;self.accepted=0
        self.socket=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        self.socket.bind(('',0));self.socket.setblocking(False)
    def send(self,buttons,yaw,pitch):
        self.socket.sendto(packet(self.frame,self.sequence,buttons,yaw,pitch),self.target)
        self.frame=(self.frame+1)&0xffffffff;self.sequence=(self.sequence+1)&255
        while True:
            try:
                data,peer=self.socket.recvfrom(2048)
                if peer==self.target and len(data)==20 and data[:4]==b'GS\x02\x01':
                    self.replies+=1;self.accepted+=bool(struct.unpack_from('>I',data,12)[0]&1)
            except (BlockingIOError,ConnectionResetError):break
    def close(self,yaw,pitch):
        for _ in range(3):self.send(0,yaw,pitch);time.sleep(1/60)
        self.socket.close()
        print(f'Stopped: {self.replies} replies, {self.accepted} accepted; keys expire after 300 ms.')

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ip',default='192.168.7.2');p.add_argument('--port',type=int,default=4000)
    p.add_argument('--seconds',type=float);p.add_argument('--buttons',type=lambda s:int(s,0))
    p.add_argument('--yaw',type=int,default=0);p.add_argument('--pitch',type=int,default=0)
    p.add_argument('--sensitivity',type=float,default=5,help='Pixels per angle step (1.40625 degrees)')
    a=p.parse_args()
    try:packet(0,0,a.buttons or 0,a.yaw,a.pitch)
    except ValueError as e:p.error(str(e))
    if not math.isfinite(a.sensitivity) or a.sensitivity<=0 or (a.seconds is not None and (not math.isfinite(a.seconds) or a.seconds<=0)):
        p.error('Duration/sensitivity must be finite and positive')
    if a.buttons is not None and a.seconds is None:p.error('Fixed input needs --seconds')
    sender=Sender(a.ip,a.port);yaw,pitch=a.yaw,a.pitch
    if a.buttons is not None:
        try:
            start=time.monotonic();tick=start
            while time.monotonic()-start<a.seconds:
                sender.send(a.buttons,yaw,pitch);tick+=1/60;time.sleep(max(0,tick-time.monotonic()))
        finally:sender.close(yaw,pitch)
        return
    import tkinter as tk
    root=tk.Tk();root.title('FPGA game controls — click to capture, Tab to release, Esc to stop')
    root.geometry('640x360');root.resizable(False,False)
    text=tk.Label(root,text='Click here to capture the mouse\n\nWASD: walk/strafe   Space: jump\nE: use door   Left mouse/F: fire\nR: reset demo   Tab: release mouse   Esc: stop',font=('Segoe UI',15))
    text.pack(expand=True,fill='both')
    held=set();captured=False;start=time.monotonic();fx=float(yaw);fy=float(pitch)
    def release(event=None):
        nonlocal captured
        captured=False;held.clear();root.grab_release();root.config(cursor='');text.config(cursor='')
    def center():root.event_generate('<Motion>',warp=True,x=320,y=180,
        rootx=root.winfo_rootx()+320,rooty=root.winfo_rooty()+180)
    def capture(event=None):
        nonlocal captured
        captured=True;root.focus_force();root.grab_set();root.config(cursor='none');text.config(cursor='none');center()
    def motion(event):
        nonlocal fx,fy,yaw,pitch
        if not captured:return
        # Root-relative coordinates also work when the Label receives the event.
        dx=event.x_root-root.winfo_rootx()-320;dy=event.y_root-root.winfo_rooty()-180
        if not dx and not dy:return
        fx=(fx+dx/a.sensitivity)%256;fy=max(-32,min(32,fy-dy/a.sensitivity))
        yaw=round(fx)&255;pitch=round(fy);center()
    def key(event,down):
        nonlocal yaw,pitch,fx,fy
        name=event.keysym.lower()
        if name=='escape':root.destroy();return
        if name=='tab':release();return
        if down and captured:
            held.add(name)
            if name=='r':yaw=a.yaw;pitch=0;fx=float(yaw);fy=0
        else:held.discard(name)
    def click(event):
        if captured:held.add('fire')
        else:capture()
    def tick():
        mask=0
        for names,bit in ((('a','left'),1),(('d','right'),2),(('w','up'),4),(('s','down'),8),
                          (('space',),16),(('fire','f'),32),(('e',),64),(('r',),128)):
            if any(n in held for n in names):mask|=bit
        sender.send(mask if captured else 0,yaw,pitch)
        if a.seconds is not None and time.monotonic()-start>=a.seconds:root.destroy()
        else:root.after(16,tick)
    root.bind('<Motion>',motion);root.bind('<Button-1>',click)
    root.bind('<ButtonRelease-1>',lambda e:held.discard('fire'))
    root.bind('<KeyPress>',lambda e:key(e,True));root.bind('<KeyRelease>',lambda e:key(e,False))
    root.bind('<FocusOut>',release)
    try:tick();root.mainloop()
    finally:sender.close(yaw,pitch)

if __name__=='__main__':main()
