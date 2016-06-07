[Device42](http://www.device42.com/) is a comprehensive data center inventory management and IP Address management software 
that integrates centralized password management, impact charts and applications mappings with IT asset management.

This repository contains sample script to take information from a Infoblox install and send it to Device42 appliance using the REST APIs.
Info gathered from Infoblox:

* Subnets
* Static IP addresses
* MAC addresses
* Device names (if detected by Infoblox)
* Device OS (if detected by Infoblox)
    

## Assumptions
-----------------------------
    * The script assumes that you are running Infoblox with web api (wapi) v 1.2
    * The script gathers data for fixed IP addresses recorded in Infoblox
    * This script works with Device42 5.8.1 and above

    
### Requirements
-----------------------------
    * python 2.7.x
    * requests (you can install it with sudo pip install requests or sudo apt-get install python-requests)

    
### Usage
-----------------------------
    * Copy infoblox2device42.cfg.sample to infoblox2device42.cfg
    * add D42 URL/credentials
    * add Infoblox DB info/credentials
    * Run the script and enjoy!
    * If you have any questions - feel free to reach out to us at support at device42.com

    
### Compatibility
-----------------------------
    * Script runs on Linux and Windows

