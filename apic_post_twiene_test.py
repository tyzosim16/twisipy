# -*- coding: utf-8 -*-
"""
Created on Mon July 15 2019

Version 3
- changed to attach EPG to AEP for L2E rather than via static assignment to vPC on border leafs.

Version 2
- includes prefix length in EPG name
- attach EPG to listed VMM domains

Version 1:

Import legacy VLANs from DCE1-3 from CSV file and build EPG
- Create ANP for each legacy VRF
- Create BD and associate to VRF (VRF=0 -> L2 only)
- Create EPG
- Attach EPG to PHY domain for DCE3 L2E
- Does NOT add VLAN to VLP for L2E to DCE3
- Attach to vPC for L2E to DCE3 with static VLAN

Rollback will delete all of the above.

@author: ERLAW
"""

import sys
import datetime
import ipaddress
import json
import requests
import csv
from apic_config import APIC 
from apic_token import apic_token
#from requests.packages.urllib3.exceptions import InsecureRequestWarning
# disable SSL certificate warning
#requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

def json_post(url, data, cookies):
    try:
        response = requests.post(url, json=data, cookies=cookies, verify=False)
        
    except requests.exceptions.RequestException as e:
        print("Http error: ", e)

def json_delete(url, cookies):

    try:
        response = requests.delete(url, cookies=cookies, verify=False)
        
    except requests.exceptions.RequestException as e:
        print("Http error: ", e)

def main():

    dry_run = False
    deploy_config = True
    roll_back = not deploy_config
 
    apic = APIC
    if not dry_run:
        cookie = apic_token()

    ##input_csv = "input_data_212_v4_INC0033486.csv"
    open(sys.argv[1], mode='r') as csv_file:
    if deploy_config:
        f = open(input_csv, 'rt')
        try:
            reader = csv.DictReader(f, delimiter=';')
            for epg_row in reader:
                print ("Data Input:", epg_row)

                # Create variables:

                # Tenant
                tenant_name = "{}".format(epg_row['tenant_id'])

                # VLAN
                vlan_number = "{}".format(epg_row['vlan_no'])
                vlan_type = "{}".format(epg_row['vlan_type'])

                # Subnet
                prefix = "{}".format(epg_row['prefix_id'])
                subnet = ipaddress.IPv4Network(prefix)
                prefix_len = subnet.prefixlen
                # version 1:
                # if prefix_len == 24:
                #    subnet_name = str(subnet.network_address)[:-2]
                #else:
                #    subnet_name = str(subnet.network_address)
                #
                # version 2:
                subnet_name = str(subnet.network_address)+"_"+str(prefix_len)

                # VRF + ANP
                vrf_number = "{}".format(epg_row['vrf_no'])
                if int(vrf_number) == 0:
                    vrf_name = "BOGUS_L2_ONLY"
                    anp_name = "LEGACY_L2ONLY_ANP"
                elif int(vrf_number) < 10:
                    vrf_name = "VRF000{}".format(vrf_number)
                    anp_name = "LEGACY_{}_ANP".format(vrf_name)
                else:
                    vrf_name = "VRF00{}".format(vrf_number)
                    anp_name = "LEGACY_{}_ANP".format(vrf_name)

                # (Create) ANP
                anp_url = "https://{}/api/node/mo/uni/tn-{}/ap-{}.json".format(apic, tenant_name, anp_name)
                anp_data = {
                    "fvAp": {
                        "attributes": {
                        "dn": "uni/tn-{}/ap-{}".format(tenant_name, anp_name),
                        "name": "{}".format(anp_name),
                        "rn": "ap-{}".format(anp_name),
                        "status": "created"
                        },
                        "children": []
                        }
								}
                if dry_run:
                        print(anp_url)
                        print(json.dumps(anp_data, sort_keys=True, indent=4))
                        
                if not dry_run:
                        json_post(anp_url, anp_data, cookie)                    

                # Create BD
                bd_name = "{}_BD".format(vlan_number)
                bd_alias = "{}".format(vlan_number)
                bd_url = "https://{}/api/node/mo/uni/tn-{}/BD-{}.json".format(apic, tenant_name, bd_name)
                bd_data = {
                    "fvBD": {
                            "attributes": {
                                    "dn": "uni/tn-{}/BD-{}".format(tenant_name, bd_name),
                                    "mac": "00:22:BD:F8:19:FF",
                                    "name": "{}".format(bd_name),
                                    "rn": "BD-{}".format(bd_name),
                                    "status": "created",
                                    "arpFlood": "yes",
                                    "multiDstPktAct": "bd-flood",
                                    "unicastRoute": "no",
                                    "unkMacUcastAct": "flood",
                                    "unkMcastAct": "flood",
                                    "nameAlias": "{}".format(bd_alias),
                            },
                                  "children": [
                                    {
                                            "fvRsCtx": {
                                                    "attributes": {
                                                            "status": "created,modified",
                                                            "tnFvCtxName": "{}_VRF".format(vrf_name)
                                                    },
                                                    "children": []
                                            }
                                    },
                            ]
                    }
                }

                if dry_run:
                        print(bd_url)
                        print(json.dumps(bd_data, sort_keys=True, indent=4))
                        
                if not dry_run:
                        json_post(bd_url, bd_data, cookie)

                # EPG
                epg_name = "{}_{}_EPG".format(vlan_type,subnet_name)
                epg_url = "https://{}/api/node/mo/uni/tn-{}/ap-{}/epg-{}.json".format(apic, tenant_name, anp_name, epg_name)
                epg_data = {
                    "fvAEPg": {
                        "attributes": {
                            "dn": "uni/tn-{}/ap-{}/epg-{}".format(tenant_name, anp_name, epg_name),
                            "name": "{}".format(epg_name),
                            "nameAlias": "{}".format(vlan_number),
                            "prefGrMemb": "include",
                            "rn": "epg-{}".format(epg_name),
                            "status": "created"
                        },
                        "children": [
                            {
                                "fvRsBd": {
                                    "attributes": {
                                        "status": "created,modified",
                                        "tnFvBDName": "{}".format(bd_name)
                                    },
                                    "children": []
                                }
                            }
                        ]
                    }
                }

                if dry_run:
                        print(epg_url)
                        print(json.dumps(epg_data, sort_keys=True, indent=4))
                        
                if not dry_run:
                        json_post(epg_url, epg_data, cookie)                    

                # Attach DCE3 L2E PHY domain to EPG
                phy_data = {
                    "fvRsDomAtt": {
                        "attributes": {
                            "resImedcy": "immediate",
                            "status": "created",
                            "tDn": "uni/phys-DCE_LEGACY_L2E-DOM"
                        },
                        "children": []
                    }
                }

                if dry_run:
                        print(epg_url)
                        print(json.dumps(phy_data, sort_keys=True, indent=4))

                if not dry_run:
                        json_post(epg_url, phy_data, cookie)

                # Version 3:
                # Attach EPG to AEP for DCE1-3 L2E with static VLAN
                aep_url="https://apic-dc3-01/api/node/mo/uni/infra/attentp-DCE_L2E_AEP/gen-default.json"
                aep_data= {
                    "infraRsFuncToEpg": {
                        "attributes": {
                            "encap": "vlan-{}".format(vlan_number),
                            "status": "created,modified",
                            "tDn": "uni/tn-{}/ap-{}/epg-{}".format(tenant_name, anp_name, epg_name),
                        },
                        "children": []
                    }
                }

                if dry_run:
                        print(aep_url)
                        print(json.dumps(aep_data, sort_keys=True, indent=4))

                if not dry_run:
                        json_post(aep_url, aep_data, cookie)

                # Attach VMM domain to EPG with dynamic VLAN

                vmm_doms = epg_row['vmm_doms']
                vmm_list = vmm_doms.split(',')
                #print(vmm_list)
                vmms_supported = {"SBOX01", "TEST01", "PROD01", "OT_PROD01_GP"}

                for vmm_dom in vmm_list:
                    if vmm_dom in vmms_supported:
                        vmm_data = {
                            "fvRsDomAtt": {
                                "attributes": {
                                    "resImedcy": "immediate",
                                    "status": "created",
                                    "tDn": "uni/vmmp-VMware/dom-ACI_vDS_{}_VMM_DOM".format(vmm_dom)
                                },
                                "children": [
                                    {
                                        "vmmSecP": {
                                            "attributes": {
                                                "status": "created"
                                            },
                                            "children": []
                                        }
                                    }
                                ]
                            }
                        }

                        if dry_run:
                            print(epg_url)
                            print(json.dumps(vmm_data, sort_keys=True, indent=4))

                        if not dry_run:
                            json_post(epg_url, vmm_data, cookie)


        finally:
            f.close()

            
    if roll_back:
        f = open(input_csv, 'rt')
        try:
            reader = csv.DictReader(f, delimiter=';')
            for epg_row in reader:
                #print ("Data Input:", epg_row)

                # Create variables:

                # Tenant
                tenant_name = "{}".format(epg_row['tenant_id'])

                # VLAN
                vlan_number = "{}".format(epg_row['vlan_no'])
                vlan_type = "{}".format(epg_row['vlan_type'])

                # Subnet
                prefix = "{}".format(epg_row['prefix_id'])
                subnet = ipaddress.IPv4Network(prefix)
                prefix_len = subnet.prefixlen
                # version 1:
                # if prefix_len == 24:
                #    subnet_name = str(subnet.network_address)[:-2]
                #else:
                #    subnet_name = str(subnet.network_address)
                #
                # version 2:
                subnet_name = str(subnet.network_address)+"_"+str(prefix_len)

                # VRF + ANP
                vrf_number = "{}".format(epg_row['vrf_no'])
                if int(vrf_number) == 0:
                    vrf_name = "BOGUS_L2_ONLY"
                    anp_name = "LEGACY_L2ONLY_ANP"
                elif int(vrf_number) < 10:
                    vrf_name = "VRF000{}".format(vrf_number)
                    anp_name = "LEGACY_{}_ANP".format(vrf_name)
                else:
                    vrf_name = "VRF00{}".format(vrf_number)
                    anp_name = "LEGACY_{}_ANP".format(vrf_name)

                anp_url = "https://{}/api/node/mo/uni/tn-{}/ap-{}.json".format(apic, tenant_name, anp_name)

                # We don't do roll back for EPG attach to PHY DOM  but proceed to deleting EPG
                epg_name = "{}_{}_EPG".format(vlan_type, subnet_name)
                epg_url = anp_url
                epg_data = {
                    "fvAp": {
                        "attributes": {
                            "dn": "uni/tn-{}/ap-{}".format(tenant_name, anp_name),
                            "status": "modified"
                        },
                        "children": [
                            {
                                "fvAEPg": {
                                    "attributes": {
                                        "dn": "uni/tn-{}/ap-{}/epg-{}".format(tenant_name, anp_name, epg_name),
                                        "status": "deleted"
                                    },
                                    "children": []
                                }
                            }
                        ]
                    }
                }
                if dry_run:
                        print(epg_url)
                        print(json.dumps(epg_data, sort_keys=True, indent=4))
                        
                if not dry_run:
                        json_post(epg_url, epg_data, cookie)

                # Version 3: remove EPG from AEP for L2E to DCE1-3:
                aep_url = "https://apic-dc3-01/api/node/mo/uni/infra/attentp-DCE_L2E_AEP/gen-default.json"
                aep_data = {
                    "infraGeneric": {
                        "attributes": {
                            "dn": "uni/infra/attentp-DCE_L2E_AEP/gen-default",
                            "status": "modified"
                        },
                        "children": [
                            {
                                "infraRsFuncToEpg": {
                                    "attributes": {
                                        "dn": "uni/infra/attentp-DCE_L2E_AEP/gen-default/rsfuncToEpg-[uni/tn-{}/ap-{}/epg-{}]".format(tenant_name, anp_name, epg_name),
                                        "status": "deleted"
                                    },
                                    "children": []
                                }
                            }
                        ]
                    }
                }

                if dry_run:
                        print(aep_url)
                        print(json.dumps(aep_data, sort_keys=True, indent=4))

                if not dry_run:
                        json_post(aep_url, aep_data, cookie)


                # Remove BD
                bd_name = "{}_BD".format(vlan_number)
                bd_url = "https://{}/api/node/mo/uni/tn-{}.json".format(apic, tenant_name)

                bd_data = {
                    "fvTenant": {
                        "attributes": {
                            "dn": "uni/tn-{}".format(tenant_name),
                            "status": "modified"
                        },
                        "children": [
                            {
                                "fvBD": {
                                    "attributes": {
                                        "dn": "uni/tn-{}/BD-{}".format(tenant_name, bd_name),
                                        "status": "deleted"
                                    },
                                    "children": []
                                }
                            }
                        ]
                    }
                }

                if dry_run:
                        print(bd_url)
                        print(json.dumps(bd_data, sort_keys=True, indent=4))
                        
                if not dry_run:
                        json_post(bd_url, bd_data, cookie)




        finally:
            f.close()

    #if roll_back:

    #sys.exit(0)    
    
if __name__ == '__main__':
    
    main()
    
