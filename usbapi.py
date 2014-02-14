import pywinusb.hid as hid
import time
import Queue
import threading

"""
TODO
- make the instant set actions maybe add to the end of the queue
- add a delay action
- add an alarm action for a set time
- chase actions from one device to the next
- allow devices to be reordered, AND that order saved to disck for reuse next time
- allow for infinite sequences by having callback defined ones as well as queue driven ones
"""

class UsbDevices(list):
    # List subclassing as decribed at http://stackoverflow.com/questions/8180014/how-to-subclass-python-list-without-type-problems
    def __getslice__(self,i,j):
        return UsbDevices(list.__getslice__(self, i, j))
    def __add__(self,other):
        return UsbDevices(list.__add__(self,other))
    def __mul__(self,other):
        return UsbDevices(list.__mul__(self,other))
    def __getitem__(self, item):
        result = list.__getitem__(self, item)
        try:
            return UsbDevices(result)
        except TypeError:
            return result
            
    # This batch of methods are only used on list of devices
    
    def list(self):
        for usbdevice in self:
            device = usbdevice.device
            print "%s pID=0x%04x %s" \
                  % (device.product_name, device.product_id, device.device_path)    

    def identify(self):
        """Run through the devices in sequence to identity them"""
        for i, device in enumerate(self, start = 1):
            device.color(i).pulse(number = i, delay = 0.7)
            
        for device in self:
            device.wait()
            
        for device in self:
            device.dance().wait()
            
    def reorder(self, sequence):
        reordered = UsbDevices()
        for i in self:
            reordered.append(None)
        starter = sequence[0]
        for i in sequence:
            starter = min(starter, i)       
        for i, value in enumerate(sequence):
            reordered[value - starter] = self[i]

        return reordered
        
    def chase(self):
        limit = len(self)
        
        colors = [self[0].white]
        if limit > 2:
            colors.append(self[0].cyan)
        if limit > 3:
            colors.append(self[0].blue)
        colors.append(self[0].black)
        
        colorMask = self[0].colorMask
        colorShift = self[0].colorShift
        
        when = time.time()
        for i in range(100):
            for c, color in enumerate(colors):
                self[(i - c) % limit].queue.put((when, colorMask, color << colorShift))
            when += 0.7

    # This batch of methods mirror the methods on a single device
    
    def color(self, color):
        for device in self:
            device.color(color)
        return self
        
    def heart(self, heart):
        for device in self:
            device.heart(heart)
        return self
        
    def turn(self, turn):
        for device in self:
            device.turn(turn)
        return self
        
    def flap(self, flap):
        for device in self:
            device.flap(flap)
        return self
    
    def dance(self, number = 10, delay = 0.2):
        for device in self:
            device.dance(number, delay)
        return self
        
    def fly(self, number = 10, delay = 0.1):
        for device in self:
            device.fly(number, delay)
        return self

    def buzz(self, number = 30, delay = 0.02):
        for device in self:
            device.buzz(number, delay)
        return self

    def pulse(self, number = 30, delay = 0.1):
        for device in self:
            device.pulse(number, delay)
        return self
        
    def flash(self, number = 30, delay = 0.01, color = None):
        for device in self:
            device.flash(number, delay, color)
        return self
            
    def wait(self):
        for device in self:
            device.wait()
        return self
               
    def reset(self):
        for device in self:
            device.reset()
        return self
        
    def discard(self):
        for device in self:
            device.discard()
        return self

class usbapi:
    """Class for providing access to USB notifier type objects"""

#    def __init__(self):
#        self.data = []

    def getDevices(self):
        # find all the i-buddy devices
        dev_filter = hid.HidDeviceFilter(vendor_id = 0x1130)
        hiddevices = dev_filter.get_devices()

        # Select just the devices we can interact with
        devices = UsbDevices()
        for device in hiddevices:
            # Each phsical device shows up twice, we just want the '01' labelled one
            if '&mi_01#' in device.device_path:
                usbdev = usbdevice(device)
                usbdev.index = len(devices)
                devices.append(usbdev)
                
        self.devices = devices
        return self.devices
        
class usbdevice:

    def __init__(self, device):
    
        self.device = device
        
        self.lock = threading.Lock()
        
        # assume we start from all off
        self.value = 0xff

        # we pick a preferred move
        self.move = 1
			
        self.queue = Queue.PriorityQueue()
            
        self.queue.device = self
            
        t = threading.Thread(target=self.worker, args=(self.queue,))
        t.daemon = True
        t.start()
        
    def __str__(self):
        color = (self.value & ~self.colorMask) >> self.colorShift
        heart = (self.value & ~self.heartMask) >> self.heartShift
        flap = (self.value & ~self.flapMask) >> self.flapShift
        turn = (self.value & ~self.turnMask) >> self.turnShift
        #print color, heart, flap, turn
        return str(self.index) + ') ' + self.colors[color] + ' ' + self.hearts[heart] + ' ' + self.flaps[flap] + ' ' + self.turns[turn] + ' ' + str(self.queue.qsize()) + ' queued'
        
    def __repr__(self):
        return str(self)    

    colors = ['white', 'cyan', 'magenta', 'blue', 'yellow', 'green', 'red', 'nothing']
    flaps = ['flaps both', 'pull', 'push', '']
    turns = ['turn both', 'left', 'right', '']
    hearts = ['heart', '']
     
    red = 6
    green = 5
    blue = 3
    cyan = 1
    magenta = 2
    yellow = 4
    white = 0
    nothing = black = 7
    
    left = pull = 1
    right = push = 2
    neutral = rest = 3
    
    show = 0
    hide = 1
    
    colorMask = 0x8f              
    colorShift = 4
    heartMask = 0x7f
    heartShift = 7
    turnMask = 0xfc
    turnShift = 0    
    flapMask = 0xf3
    flapShift = 2    
    
    def output(self, value=None):

        if value == None:
            value = self.value

        try:
            self.lock.acquire()
            self.device.open()
	
            reports = self.device.find_output_reports()
	
            out_report = reports[0]
    
            data = (0x00, 0x55, 0x53, 0x42, 0x43, 0x00, 0x40, 0x02, value)
            out_report.send(data)

            self.value = value
      
        finally:
            self.device.close()
            self.lock.release()

    def assemble(self, color, heart, turn, flap):
        return (color << self.colorShift) + (heart << self.heartShift) + (turn) + (flap << self.flapShift) 

    # Actions
    
    def color(self, color):
        """Set the color of the main indicator"""
        color = color if (color <= 7 and color >= 0) else 7 if color > 7 else 0
        self.value = (self.value & self.colorMask) + (color << self.colorShift)
        self.output()
        return self

    def heart(self, heart):
        """Set the secondary (heart) indicator"""
        heart = 0 if heart == 0 else 1
        self.value = (self.value & self.heartMask) + (heart << self.heartShift)
        self.output()
        return self
        
    def turn(self, turn):
        """Turn the body"""
        turn = turn if (turn <= 3 and turn >= 0) else 3 if turn > 3 else 0
        if turn == 1 or turn == 2:
            move = turn
        self.value = (self.value & self.turnMask) + (turn << self.turnShift)
        self.output()
        return self
        
    def flap(self, flap):
        """Move the wings"""
        flap = flap if (flap <= 3 and flap >= 0) else 3 if flap > 3 else 0
        self.value = (self.value & self.flapMask) + (flap << self.flapShift)
        self.output()
        return self
    
    def dance(self, number = 10, delay = 0.2):
        """Dance turning left and right"""
        when = time.time()
        for each in range(number):              
            self.queue.put((when, self.turnMask, self.left << self.turnShift))
            when += delay
            self.queue.put((when, self.turnMask, self.right << self.turnShift))
            when += delay
        self.queue.put((when, self.turnMask, self.neutral << self.turnShift))
        return self
        
    def fly(self, number = 10, delay = 0.1):
        """Flap the wings multiple times"""
        when = time.time()
        for each in range(number):              
            self.queue.put((when, self.flapMask, self.pull << self.flapShift))
            when += delay
            self.queue.put((when, self.flapMask, self.push << self.flapShift))
            when += delay
        self.queue.put((when, self.flapMask, self.neutral << self.flapShift))
        return self

    def buzz(self, number = 30, delay = 0.02):
        """Make a buzzing sound"""
        # We try and not disturb the turn by turning back to the last move
        turn = self.move

        when = time.time()
        for each in range(number):
            self.queue.put((when, self.turnMask, turn << self.turnShift))
            self.queue.put((when, self.turnMask, (turn  ^ 3) << self.turnShift))
            when += delay
            self.queue.put((when, self.turnMask, self.neutral << self.turnShift))
            when += delay
        return self

    def pulse(self, number = 30, delay = 0.1):
        """Pulse the secondary indicator (heart)"""
        return self.sequence(number, delay, mask = self.heartMask, shift = self.heartShift)
        
    def flash(self, number = 30, delay = 0.01, color = None):
        """Flash the main indicator"""
        color = color if color != None else self.red
        return self.sequence(number, delay, mask = self.colorMask, shift = self.colorShift, on = color, off = self.black)
    
    def wait(self):
        """wait for all outstanding actions to complete"""
        self.queue.join()
        return self        
               
    def reset(self):
        """Clears any queued items, and resets back to all off"""
        self.discard()
        self.output(0xff)
        return self
        
    def discard(self):
        """Clears any queued items"""
        try:
            while True:
                item = self.queue.get_nowait()
                self.queue.task_done()
        except:
             pass
        return self

    # Internal helper actions    
    def sequence(self, number, delay, mask, shift, on = 0, off = 1):
        """Helper function"""
        when = time.time()
        for each in range(number):
            self.queue.put((when, mask, on << shift))
            when += delay
            self.queue.put((when, mask, off << shift))
            when += delay
        return self
               
    # Private worker thread, not part of the api           
    def worker(self, queue):
        while True:
            item = queue.get()
        
            when, mask, value = item
            delay = when - time.time()
            if delay > 0:
                time.sleep(delay)
            self.value = (self.value & mask) + value
            self.output()
            queue.task_done()