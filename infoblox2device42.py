import sys
import json
import time
import netaddr
import datetime
import requests
import threading
import ConfigParser
import Queue
import base64 

__version__ = '1.0'


# Infoblox connection params
BLOX_HOST = '192.168.3.50'
BLOX_USER  = 'admin'
BLOX_PASS  = 'infoblox'
BLOX_URL    = 'https://'+BLOX_HOST+'/wapi/v1.2/'

# Device42 upload settings  #
D42_USER   = 'admin'
D42_PWD    = 'adm!nd42'
D42_URL     = 'https://192.168.3.30'
DRY_RUN     = False


# Target network. If None, scipt will fetch ALL! networks. 
# If entered, target network must be in CIDR notation. In that case, script will fetch data for that network only.
# Multiple CIDR blocks can be entered, separated by commas.
#TARGET_NETWORKS = ['172.16.0.0/16']
TARGET_NETWORKS = ['192.168.3.0/24']
#TARGET_NETWORKS = ['192.168.3.0/24', '192.168.1.0/24','172.16.0.0/16']
#TARGET_NETWORKS = None


# Other
ADD_COMMENTS_AS_SUBNET_NAME = True
GET_ASSOCIATED_DEVICE               = True
DEBUG                = True
MAX_THREADS     = 20
IGNORE_DOMAIN   = True  #If you want to strip the domain name part from the hostname.



lock = threading.Lock()
q     = Queue.Queue()


class REST():
    def __init__(self):
        self.password = D42_PWD
        self.username = D42_USER
        self.base_url   = D42_URL
        
    def uploader(self, data, url):
        payload = data
        headers = {
            'Authorization': 'Basic ' + base64.b64encode(self.username + ':' + self.password),
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        r = requests.post(url, data=payload, headers=headers, verify=False)
        if DEBUG:
            msg1 =  unicode(payload)
            msg2 = 'Status code: %s' % str(r.status_code)
            msg3 = str(r.text)
            lock.acquire()
            print '\n\t----------- UPLOADER FUNCTION -----------'
            print '\t'+msg1
            print '\t'+msg2
            print '\t'+msg3
            print '\t------- END OF UPLOADER FUNCTION -------\n'
            lock.release()
        lock.acquire()
        msg = str(r.text)
        lock.release()
 


    def post_subnet(self, data):
        if DRY_RUN == False:
            url = self.base_url+'/api/1.0/subnets/'
            msg =  '\tPosting data to %s' % url
            lock.acquire()
            print msg
            lock.release()
            self.uploader(data, url)


    def post_ip(self, data, ip):
        if DRY_RUN == False:
            url = self.base_url+'/api/ip/'
            msg =  '\tPosting IP %s to %s ' % (ip, url)
            lock.acquire()
            print msg
            lock.release()
            self.uploader(data, url)


    def post_device(self, data):
        if DRY_RUN == False:
            url = self.base_url+'/api/1.0/device/'
            msg =  '\tPosting device data to %s ' % url
            lock.acquire()
            print msg
            lock.release()
            self.uploader(data, url)



class InfobloxNetworks():
    def __init__(self):
        self.session = None
        self.rest = REST()


    def connect(self):
        self.session         = requests.Session()
        self.session.auth  = (BLOX_USER, BLOX_PASS)
        self.session.verify = False


    def get_networks(self):
        networks = []
        
        if not self.session:
            self.connect()
        r = self.session.get(BLOX_URL + 'network')
        data = json.loads(r.text)
        if DEBUG:
            lock.acquire()
            print '\n\t------- GET NETWORKS FUNCTION -------'
            print '\t', data
            print '\t---- END OF GET NETWORKS FUNCTION ----\n'
            lock.release()
        for rec in  data:
            subnet    = {}
            comment = None
            try:
                network  = rec['network']
                net, mask = network.split('/')
                subnet.update({'network':net})
                subnet.update({'mask_bits':mask})
                networks.append(network)
            except:
                pass
            if ADD_COMMENTS_AS_SUBNET_NAME:
                try:
                    comment = rec['comment']
                    subnet.update({'name':comment})
                except:
                    pass
            if subnet:
                print '[+] Subnet: %s' % network
                self.rest.post_subnet(subnet)
        return networks


    def create_network(self, NET):
        subnet = {}
        net, mask = NET.split('/')
        subnet.update({'network':net})
        subnet.update({'mask_bits':mask})
        self.rest.post_subnet(subnet)



class InfobloxDevices():
    def __init__(self, network):
        self.session      = None
        self.network     = network
        self.data_device= {}
        self.data_ip      = {}
        self.rest = REST()
        

    def connect(self):
        self.session         = requests.Session()
        self.session.auth  = (BLOX_USER, BLOX_PASS)
        self.session.verify = False


    def chunks(self, l, n):
        for i in xrange(0, len(l), n):
            yield l[i:i+n]


    def dispatch(self):
        # check network size
        # if larger than 1000, split (Infoblox limit)
        IPs = []
        for ip in netaddr.IPNetwork(self.network).iter_hosts():
            IPs.append(str(ip))
        
        if len(IPs) > 1000:
            pairs = []
            the_list = [IPs[x] for x in xrange(0, len(IPs), 999)]
            last_start = ''
            last_stop = IPs[-1]
            for i in xrange(len(the_list) - 1):
                current_item, next_item = the_list[i], the_list[i + 1]
                pairs.append((current_item, next_item))
                last_start = next_item
            pairs.append((last_start, last_stop))
            for pair in pairs:
                start, end = pair
                self.get_hosts(start, end)
        else:
            self.get_hosts(None, None)
            
        
    def get_hosts(self,start, end):
        if not start:
            msg = '[!] Retrieving data for network: %s' % self.network
        else:
            msg = '[!] Retrieving data for network: %s, block: %s - %s' % (self.network, start, end)
        lock.acquire()
        print '\n'+msg
        lock.release()

        # check session
        if not self.session:
            self.connect()
        
        if not start:
            qstring = 'ipv4address?network=%s&types=FA&types=UNMANAGED&types=RESERVATION&types=HOST&types=A' % self.network
        else:
            qstring = 'ipv4address?network=%s&ip_address>=%s&ip_address<=%s&types=FA&types=UNMANAGED&types=RESERVATION&types=HOST&types=A' % (self.network, start, end)
            
            
        r = self.session.get(BLOX_URL + qstring)
        
        if len(r.text) > 2:
            if not 'does not match any network' in r.text:
                data = json.loads(r.text)
                if DEBUG:
                    lock.acquire()
                    print '\n\t----------- GET DATA FUNCTION -----------'
                    print '\t', r.text
                    print '\t---------- END OF DATA FUNCTION ----------'
                    lock.release()
                for device in data:
                    types = []
                    try:
                        types = device['types']
                    except:
                        pass
                    if types:
                        self.get_data(types, device)

            elif 'does not match any network' in r.text:
                msg = '[!] %s does not match any network.' % self.network
                lock.acquire()
                print msg
                lock.release()
        else:
            msg = '[!] No host IPs in %s network.' % self.network
            lock.acquire()
            print msg
            lock.release()


    def get_data(self, types, device):
        try:
            name = device['names'][0]
            if IGNORE_DOMAIN:
                if '.' in name:
                    name = name.split('.')[0]
            self.data_device.update({'name':name})
        except:
            name = 'Unknown'
        try:
            mac = device['mac_address']
            if mac not in ('', ' ', '\n'):
                self.data_device.update({'macaddress':mac})
                self.data_ip.update({'macaddress':mac})
            else:
                self.data_device.pop('macaddress', None)
                self.data_ip.pop('macaddress', None)
        except:
            pass
        try:
            ip = device['ip_address']
            self.data_device.update({'ipaddress':ip})
            self.data_ip.update({'ipaddress':ip})
        except:
            pass
            
        if GET_ASSOCIATED_DEVICE:
            if 'FA' in types :
                ip = device['ip_address']
                qstring = 'fixedaddress?ipv4addr=%s&_return_fields=discovered_data' % ip
            elif 'A' in types:
                ip = device['ip_address']
                qstring = 'record:a?ipv4addr=%s&_return_fields=discovered_data' % ip
                
            try:
                os, ld = self.get_os(ip, qstring)
                if ld:
                    last_discovered = datetime.datetime.fromtimestamp(int(ld)).strftime('%Y-%m-%d %H:%M:%S')
                if os:
                    self.data_device.update({'os':os})
            except:
                pass
            
        self.rest.post_ip(self.data_ip, ip)
        self.rest.post_device(self.data_device)
    

    def get_os(self, ip, qstring):
        if not self.session:
            self.connect()
        
        r = self.session.get(BLOX_URL + qstring)
        data = json.loads(r.text)
        
        try:
            ddata = data[0]['discovered_data']
            try:
                name = ddata['netbios_name']
                if IGNORE_DOMAIN:
                    if '.' in name:
                        name = name.split('.')[0]
                self.data_device.update({'name':name})
            except:
                if not 'name' in self.data_device:
                    self.data_device.update({'name':'Unknown'})
            try:
                os = ddata['os']
            except:
                os = None
            try:
                last_discovered = ddata['last_discovered']
            except:
                last_discovered = None
            return os, last_discovered
        except:
            return None, None


class TimeConversion():
    def __init__(self):
        pass
        
    def convert(self):
        if TIMESTAMP:
            modifier = TIMESTAMP[-1]
            value = TIMESTAMP[:-1]

            if modifier in ('m', 'h', 'd'):
                if modifier == 'm':
                    seconds =  int(value)*60
                    ts = int(time.time())-seconds
                    return ts
                elif modifier == 'h':
                    seconds = int(value)*60*60
                    ts = int(time.time())-seconds
                    return ts
                elif modifier == 'd':
                    seconds = int(value)*24*60*60
                    ts = int(time.time())-seconds
                    return ts
            else:
                return False
        else:
            return False


def main():
    if TARGET_NETWORKS in ('', ' ', '\n', None):
        bloxNet = InfobloxNetworks()
        bloxNet.connect()
        print '\n[!] Getting info on networks...\n'
        networks = bloxNet.get_networks()
        print '\n[!] Number of networks returned: %d' % len(networks)
        for network in networks:
            q.put(network)
            while 1:
                if not q.empty():
                    tcount = threading.active_count()
                    if tcount < int(MAX_THREADS):
                        network = q.get()
                        bloxDevice = InfobloxDevices(network)
                        p = threading.Thread(target=bloxDevice.dispatch())
                        p.start()  
                    else:
                        time.sleep(0.5)
                else:
                    tcount = threading.active_count()
                    while tcount > 2:
                        time.sleep(1)
                        tcount = threading.active_count()
                        msg =  '[*] Waiting for threads to finish. Current thread count: %s' % str(tcount)
                        lock.acquire()
                        print msg
                        lock.release()
                    msg =  '\n[!] Done!'
                    break
    else:
        bloxNet = InfobloxNetworks()
        bloxNet.connect()
        

        print '\n[!] Getting info on %d networks...\n' % len(TARGET_NETWORKS)
        for NET in TARGET_NETWORKS:
            print '\n[!] Network %s' % NET
            bloxNet.create_network(NET)
            bloxDevice = InfobloxDevices(NET.strip())
            bloxDevice.dispatch()
        

        

    
if __name__ == '__main__':
    main()
    sys.exit()
